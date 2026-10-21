#!/usr/bin/env python3
"""
Configuration Management for Bongo Cat Application
Handles JSON-based settings persistence and validation
"""

import json
from api_budget import DEFAULTS as API_BUDGET_DEFAULTS, settings as validate_api_budget_settings
import os
import copy
from pathlib import Path
from typing import Dict, Any, Callable, List
from atomic_file import atomic_write

class ConfigManager:
    """Manages application configuration with JSON persistence and validation"""
    
    def __init__(self, config_dir: str = None):
        """Initialize configuration manager"""
        # Set config directory (default: %APPDATA%/BongoCat)
        if config_dir is None:
            self.config_dir = Path.home() / "AppData" / "Roaming" / "BongoCat"
        else:
            self.config_dir = Path(config_dir)
        
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "config.json"
        self.backup_file = self.config_dir / "config_backup.json"
        self._last_config_mtime_ns = 0
        
        # Default configuration
        self.default_config = {
            "version": "1.0",
            "display": {
                "show_cpu": True,
                "show_ram": True,
                "show_wpm": True,
                "show_time": True,
                "time_format_24h": True
            },
            "behavior": {
                "sleep_timeout_minutes": 1,
                "idle_timeout_seconds": 1.0
            },
            "connection": {
                "com_port": "AUTO",
                "baudrate": 230400,
                "auto_reconnect": True,
                "timeout_seconds": 5
            },
            "startup": {
                "start_with_windows": True,
                "start_minimized": True,
                "show_notifications": True
            },
            "spotify": {
                **API_BUDGET_DEFAULTS,
                "client_id": "",
                "api_initial_interval_seconds": 1.0,
                "api_min_interval_seconds": 0.5,
                "api_max_interval_seconds": 30.0,
                "api_idle_interval_seconds": 3.0,
                "artwork_retry_attempts": 5,
            },
            "diagnostics": {
                # Kept off until the user explicitly starts ESP32 CPU sampling.
                "esp32_cpu_meter_enabled": False,
            },
            "app_animations": {
                "enabled": False,
                "poll_seconds": 1.0,
                "rules": [
                    {"match": "code.exe", "animation": "TYPING_NORMAL"},
                    {"match": "spotify.exe", "animation": "HAPPY"}
                ]
            }
        }
        
        # Current configuration
        self.config = copy.deepcopy(self.default_config)
        
        # Change callbacks
        self.change_callbacks: List[Callable[[str, Any], None]] = []
        
        # Load configuration on initialization
        self.load_config()
    
    def add_change_callback(self, callback: Callable[[str, Any], None]):
        """Add a callback to be called when configuration changes"""
        self.change_callbacks.append(callback)
    
    def _notify_change(self, key: str, value: Any):
        """Notify all callbacks of a configuration change"""
        for callback in self.change_callbacks:
            try:
                callback(key, value)
            except Exception as e:
                print(f"❌ Configuration callback error: {e}")
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate configuration structure and values"""
        try:
            # Check required sections
            required_sections = ["version", "display", "behavior", "connection", "startup"]
            for section in required_sections:
                if section not in config:
                    print(f"❌ Missing config section: {section}")
                    return False
            
            # Validate display settings
            display = config["display"]
            for key in ["show_cpu", "show_ram", "show_wpm", "show_time", "time_format_24h"]:
                if key not in display or not isinstance(display[key], bool):
                    print(f"❌ Invalid display setting: {key}")
                    return False
            
            # Validate behavior settings
            behavior = config["behavior"]
            if not (1 <= behavior.get("sleep_timeout_minutes", 0) <= 60):
                print("❌ Invalid sleep_timeout_minutes (1-60)")
                return False

            if not (0.1 <= behavior.get("idle_timeout_seconds", 0) <= 10.0):
                print("❌ Invalid idle_timeout_seconds (0.1-10.0)")
                return False
            
            # Validate connection settings
            connection = config["connection"]
            if connection.get("baudrate", 0) not in (9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600):
                print("❌ Invalid baudrate")
                return False
            if not (1 <= connection.get("timeout_seconds", 0) <= 30):
                print("❌ Invalid timeout_seconds (1-30)")
                return False

            spotify = config.get("spotify", {})
            validate_api_budget_settings(spotify)
            minimum = float(spotify.get("api_min_interval_seconds", 0.5))
            initial = float(spotify.get("api_initial_interval_seconds", 1.0))
            maximum = float(spotify.get("api_max_interval_seconds", 30.0))
            idle = float(spotify.get("api_idle_interval_seconds", 3.0))
            retries = int(spotify.get("artwork_retry_attempts", 5))
            if not (0.5 <= minimum <= initial <= maximum <= 120.0):
                print("Invalid Spotify API polling intervals")
                return False
            if not (initial <= idle <= 300.0) or not (1 <= retries <= 5):
                print("Invalid Spotify idle interval or artwork retry count")
                return False

            diagnostics = config.get("diagnostics", {})
            if diagnostics and not isinstance(
                diagnostics.get("esp32_cpu_meter_enabled", False), bool
            ):
                print("Invalid ESP32 diagnostics setting")
                return False

            app_animations = config.get("app_animations", {})
            valid_animations = {
                "IDLE_1", "IDLE_2", "IDLE_3", "IDLE_4", "BLINK",
                "EAR_TWITCH", "TYPING_SLOW", "TYPING_NORMAL",
                "TYPING_FAST", "HAPPY",
            }
            for rule in app_animations.get("rules", []):
                if not isinstance(rule, dict) or not str(rule.get("match", "")).strip():
                    return False
                if rule.get("animation") not in valid_animations:
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Config validation error: {e}")
            return False
    
    def load_config(self) -> bool:
        """Prefer the active file, then a validated backup; never rewrite damage."""
        for path in (self.config_file, self.backup_file):
            try:
                raw = path.read_bytes()
                loaded = json.loads(raw.decode("utf-8-sig"))
                if not isinstance(loaded, dict) or not self.validate_config(loaded):
                    continue
            except (OSError, UnicodeError, ValueError, RecursionError):
                continue
            self.config = self._merge_defaults(loaded)
            if path == self.backup_file:
                try:
                    atomic_write(self.config_file, raw)
                except OSError as exc:
                    # Still use the validated backup in memory. Do not erase it
                    # if disk/permissions also prevent repairing the active file.
                    print(f"Config backup loaded; active file repair failed: {type(exc).__name__}")
            self._remember_config_mtime()
            print(f"📂 Configuration loaded from {path}")
            return True
        if not self.config_file.exists() and not self.backup_file.exists():
            print("📝 No configuration file found, creating default")
            return self.save_config()
        # On a live reload keep the last working settings, rather than silently
        # replacing them (and later their backup) with defaults.
        print("Invalid configuration and backup; retaining current settings")
        return False
    
    def save_config(self) -> bool:
        """Save current configuration to file"""
        try:
            if not self.validate_config(self.config):
                return False
            payload = json.dumps(self.config, indent=2, ensure_ascii=False,
                                 allow_nan=False).encode("utf-8")
            previous = None
            try:
                raw = self.config_file.read_bytes()
                loaded = json.loads(raw.decode("utf-8-sig"))
                if isinstance(loaded, dict) and self.validate_config(loaded):
                    previous = raw
            except (OSError, UnicodeError, ValueError, RecursionError):
                pass
            # An invalid active file must never replace a known good backup.
            # If backup creation fails, leave the active file untouched too.
            if previous is not None:
                atomic_write(self.backup_file, previous)
            atomic_write(self.config_file, payload)
            self._remember_config_mtime()
            
            print(f"💾 Configuration saved to {self.config_file}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving config: {e}")
            return False

    def _remember_config_mtime(self) -> None:
        try:
            self._last_config_mtime_ns = self.config_file.stat().st_mtime_ns
        except OSError:
            self._last_config_mtime_ns = 0

    def reload_if_changed(self) -> bool:
        """Reload edits made by the detached Windows settings window."""
        try:
            current_mtime = self.config_file.stat().st_mtime_ns
        except OSError:
            return False
        if current_mtime <= self._last_config_mtime_ns:
            return False

        old_config = copy.deepcopy(self.config)
        if not self.load_config():
            return False
        for section, values in self.config.items():
            if not isinstance(values, dict):
                continue
            previous = old_config.get(section, {})
            for key, value in values.items():
                if previous.get(key) != value:
                    self._notify_change(f"{section}.{key}", value)
        return True
    
    def reset_to_defaults(self):
        """Reset configuration to defaults"""
        self.config = copy.deepcopy(self.default_config)
        print("🔄 Configuration reset to defaults")
    
    def get_setting(self, section: str, key: str = None):
        """Get a configuration setting"""
        try:
            if key is None:
                return self.config.get(section, {})
            else:
                return self.config.get(section, {}).get(key)
        except Exception as e:
            print(f"❌ Error getting setting {section}.{key}: {e}")
            return None
    
    def set_setting(self, section: str, key: str, value: Any) -> bool:
        """Set a configuration setting"""
        try:
            if section not in self.config:
                self.config[section] = {}
            
            old_value = self.config[section].get(key)
            self.config[section][key] = value
            
            # Validate the entire config after change
            if self.validate_config(self.config):
                if old_value != value:
                    self._notify_change(f"{section}.{key}", value)
                    print(f"🔧 Setting changed: {section}.{key} = {value}")
                return True
            else:
                # Revert change if validation fails
                if old_value is not None:
                    self.config[section][key] = old_value
                else:
                    del self.config[section][key]
                print(f"❌ Invalid setting: {section}.{key} = {value}")
                return False
                
        except Exception as e:
            print(f"❌ Error setting {section}.{key}: {e}")
            return False
    
    def get_display_settings(self) -> Dict[str, bool]:
        """Get all display settings"""
        return self.get_setting("display")
    
    def get_behavior_settings(self) -> Dict[str, Any]:
        """Get all behavior settings"""
        return self.get_setting("behavior")
    
    def get_connection_settings(self) -> Dict[str, Any]:
        """Get all connection settings"""
        return self.get_setting("connection")
    
    def get_startup_settings(self) -> Dict[str, bool]:
        """Get all startup settings"""
        return self.get_setting("startup")

    def get_app_animation_settings(self) -> Dict[str, Any]:
        return self.get_setting("app_animations")

    def _merge_defaults(self, loaded: Dict[str, Any]) -> Dict[str, Any]:
        merged = copy.deepcopy(self.default_config)
        for section, value in loaded.items():
            if isinstance(value, dict) and isinstance(merged.get(section), dict):
                merged[section].update(value)
            else:
                merged[section] = value
        return merged

if __name__ == "__main__":
    # Test the configuration manager
    print("🧪 Testing ConfigManager...")
    
    config = ConfigManager()
    
    # Test getting settings
    print("Display settings:", config.get_display_settings())
    print("CPU display:", config.get_setting("display", "show_cpu"))
    
    # Test setting values
    config.set_setting("display", "show_cpu", False)
    config.set_setting("behavior", "sleep_timeout_minutes", 10)
    
    # Test validation (should fail)
    config.set_setting("behavior", "sleep_timeout_minutes", 100)  # Invalid
    
    # Save configuration
    config.save_config()
    
    print("✅ ConfigManager test completed")

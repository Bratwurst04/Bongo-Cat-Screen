#!/usr/bin/env python3
"""
Configuration Management for Bongo Cat Application
Handles JSON-based settings persistence and validation
"""

import json
import os
import shutil
import copy
from pathlib import Path
from typing import Dict, Any, Callable, List

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
                "baudrate": 115200,
                "auto_reconnect": True,
                "timeout_seconds": 5
            },
            "startup": {
                "start_with_windows": True,
                "start_minimized": True,
                "show_notifications": True
            },
            "spotify": {
                "client_id": "",
                "api_initial_interval_seconds": 3.0,
                "api_min_interval_seconds": 1.0,
                "api_max_interval_seconds": 30.0,
                "api_idle_interval_seconds": 10.0,
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
            if not (9600 <= connection.get("baudrate", 0) <= 115200):
                print("❌ Invalid baudrate")
                return False
            if not (1 <= connection.get("timeout_seconds", 0) <= 30):
                print("❌ Invalid timeout_seconds (1-30)")
                return False

            spotify = config.get("spotify", {})
            minimum = float(spotify.get("api_min_interval_seconds", 1.0))
            initial = float(spotify.get("api_initial_interval_seconds", 3.0))
            maximum = float(spotify.get("api_max_interval_seconds", 30.0))
            idle = float(spotify.get("api_idle_interval_seconds", 10.0))
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
        """Load configuration from file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                
                if self.validate_config(loaded_config):
                    self.config = self._merge_defaults(loaded_config)
                    self._remember_config_mtime()
                    print(f"📂 Configuration loaded from {self.config_file}")
                    return True
                else:
                    print("⚠️ Invalid configuration file, using defaults")
                    self.reset_to_defaults()
                    return False
            else:
                print("📝 No configuration file found, creating default")
                self.reset_to_defaults()
                self.save_config()
                return True
                
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            print("🔄 Using default configuration")
            self.reset_to_defaults()
            return False
    
    def save_config(self) -> bool:
        """Save current configuration to file"""
        try:
            # Create backup of existing config
            if self.config_file.exists():
                shutil.copy2(self.config_file, self.backup_file)
            
            # Save current configuration
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
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

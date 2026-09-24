#!/usr/bin/env python3
"""
Bongo Cat Monitoring Engine - Based on Proven Original Implementation
Uses the exact working animation logic from the original script with configuration support
"""

import time
import serial
import serial.tools.list_ports
import threading
import queue
from collections import deque
from pynput import keyboard
import sys
import os
import platform
import psutil
import datetime
import unicodedata
import json
from typing import Callable, Optional, Dict, Any

from media_bridge import MediaSnapshot, WindowsMediaBridge
from windows_integration import get_foreground_app

ARTWORK_SIZE = 112
ARTWORK_CHUNK_BYTES = 128
ARTWORK_CHUNK_PAUSE_SECONDS = 0.015

class BongoCatEngine:
    """Bongo Cat engine using proven original implementation with configuration support"""
    
    def __init__(self, config_manager=None):
        """Initialize with exact original parameters plus configuration support"""
        self.config = config_manager
        self.tray = None  # Will be set by main app for connection status updates
        
        # Get connection settings from config or use defaults
        if self.config:
            conn_settings = self.config.get_connection_settings()
            self.port = conn_settings.get('com_port', 'AUTO')
            self.baudrate = conn_settings.get('baudrate', 115200)
            behavior_settings = self.config.get_behavior_settings()
            # CRITICAL FIX: Proper timeout configuration
            # idle_timeout = time to stop typing animation (quick response)
            self.idle_timeout = behavior_settings.get('idle_timeout_seconds', 1.0)
            # sleep_timeout = time to start sleep progression (user-configurable)
            self.sleep_timeout = behavior_settings.get('sleep_timeout_minutes', 1) * 60  # Convert to seconds
            print(f"⏰ Timeouts: Idle={self.idle_timeout}s, Sleep={self.sleep_timeout}s")
            
        else:
            self.port = 'AUTO'
            self.baudrate = 115200
            self.idle_timeout = 1.0  # Original script value
            self.sleep_timeout = 60  # Default 1 minute sleep timeout when no config
            
        self.serial_conn = None
        self.running = False
        self._stop_requested = threading.Event()
        self._lifecycle_lock = threading.RLock()
        self.serial_reader_thread = None
        self.keyboard_listener = None
        spotify_settings = self.config.get_setting("spotify") if self.config else {}
        spotify_settings = spotify_settings or {}
        spotify_token_path = (
            self.config.config_dir / "spotify_tokens.json" if self.config else None
        )
        self.media_bridge = WindowsMediaBridge(
            on_update=self._on_media_update,
            on_error=lambda message: print(f"⚠️ {message}"),
            spotify_client_id=spotify_settings.get("client_id", ""),
            spotify_token_path=spotify_token_path,
            spotify_settings=spotify_settings,
        )
        self._last_media_meta = None
        self._last_media_state = None
        self._last_media_time = None
        self._last_media_full_sync = 0.0
        self._last_media_track_key = ""
        self._artwork_queue = queue.Queue(maxsize=1)
        self._artwork_sender_thread = None
        self._artwork_ack = threading.Event()
        self._app_animation = None
        self._app_animation_last_sent = 0.0
        self._foreground_app_thread = None
        self._foreground_stop = threading.Event()
        
        # EXACT ORIGINAL IMPLEMENTATION - Enhanced animation control with reduced command frequency
        self.last_sent_speed = -1
        self.last_sent_state = ""
        self.last_command_time = 0
        self.min_command_interval = 0.1   # Responsive idle commands without flooding the ESP32
        
        # EXACT ORIGINAL IMPLEMENTATION - Proper keystroke detection and timing
        self.keystroke_buffer = deque(maxlen=50)  # Store recent keystrokes
        self._pressed_typing_keys = set()
        current_time = time.time()
        self.last_keystroke_time = current_time  # Initialize to current time to prevent huge time difference
        self.typing_active = False
        self.idle_start_time = current_time  # Initialize to current time so sleep detection works immediately
        self.sleep_start_time = None  # Track when we entered sleep mode
        
        # EXACT ORIGINAL IMPLEMENTATION - Improved WPM calculation with stability optimizations
        self.typing_sessions = deque(maxlen=10)  # Reduced from 20 for faster response
        self.wpm_history = deque(maxlen=5)       # Reduced history for responsiveness
        self.current_wpm = 0
        self.max_wpm = 200               # Support super-fast typers (professional level)
        
        # EXACT ORIGINAL IMPLEMENTATION - Enhanced state management with better hysteresis
        self.current_state = "IDLE"
        self.state_change_time = time.time()
        self.state_stability_time = 0.15
        
        # EXACT ORIGINAL IMPLEMENTATION - Enhanced timing settings based on research
        self.update_interval = 0.025     # 40 Hz input-to-animation loop
        self.stats_update_interval = 1.0 # System stats every second
        self.last_stats_update = 0
        
        # EXACT ORIGINAL IMPLEMENTATION - Industry-standard WPM calculation (5 characters = 1 word)
        self.chars_per_word = 5.0        # Standard definition
        self.min_wpm = 0
        self.min_animation_speed = 240   # Slow typing still feels responsive
        self.max_animation_speed = 45
        
        # EXACT ORIGINAL IMPLEMENTATION - Refined WPM thresholds based on 2024 typing speed research
        # Research shows: Average 40-45 WPM, Slow <20, Good 50-60, Professional 70+
        self.slow_threshold = 20         # Below average (matches research: <20 WPM is slow)
        self.normal_threshold = 40       # Average range (matches research: 40-45 WPM average)
        self.fast_threshold = 65         # Good/Professional range (matches research: 60+ WPM is good)
        self.streak_threshold = 85       # Excellent range (matches research: 80+ WPM is excellent)
        
        self.last_sent_speed = -1
        self.current_state = "IDLE"
        self.last_state = "IDLE"
        self.last_streak_state = False  # Initialize streak state tracking
        
        # FAST REAL-TIME System monitoring with dedicated thread
        self.cpu_percent = 0
        self.ram_percent = 0
        self.system_memory_available_mib = 0.0
        self.system_memory_total_mib = 0.0
        self.logical_cpu_count = max(1, psutil.cpu_count(logical=True) or 1)
        self.app_cpu_percent = 0.0
        self.app_cpu_percent_one_core = 0.0
        self.app_memory_mib = 0.0
        self.esp32_free_heap_bytes = None
        self.esp32_heap_total_bytes = None
        self.esp32_min_heap_bytes = None
        self.esp32_free_psram_bytes = None
        self.esp32_psram_total_bytes = None
        self.esp32_uptime_seconds = None
        diagnostic_settings = self.config.get_setting("diagnostics") if self.config else {}
        diagnostic_settings = diagnostic_settings or {}
        self.esp32_cpu_meter_enabled = bool(
            diagnostic_settings.get("esp32_cpu_meter_enabled", False)
        )
        self.esp32_cpu_estimate_percent = None
        self.esp32_cpu_sample_ms = None
        self.esp32_status_at = 0.0
        self._process_handle = psutil.Process(os.getpid())
        self._process_handle.cpu_percent(None)
        self._status_path = (
            self.config.config_dir / "desktop_status.json" if self.config else None
        )
        self.system_monitor_running = False
        self.system_monitor_thread = None
        
        # Idle management
        self.idle_start_time = 0
        self.idle_progression_started = False
        
        # EXACT ORIGINAL IMPLEMENTATION - Advanced WPM smoothing for stability
        self.wpm_history = deque(maxlen=3)  # Smaller window for faster response
        self.raw_wpm_history = deque(maxlen=10)  # Track raw WPM for analysis
        
        # ENHANCED THREAD SYNCHRONIZATION - Protect both data and serial communication
        self._data_lock = threading.Lock()  # Protect shared data structures
        self._serial_lock = threading.Lock()  # CRITICAL: Protect serial port from thread conflicts
        
        # Configuration change callbacks
        self.config_callbacks: Dict[str, Callable] = {}
        
        # Setup configuration callbacks if config manager provided
        if self.config:
            self.config.add_change_callback(self._on_config_change)
    
    def set_tray_reference(self, tray):
        """Set reference to system tray for status updates"""
        self.tray = tray
        print("🔗 Engine connected to system tray for status updates")
    
    def _on_config_change(self, key: str, value: Any):
        """Handle configuration changes - NO SERIAL COMMANDS to prevent thread conflicts"""
        print(f"🔧 Engine: Config changed {key} = {value} (will apply on restart)")
        
        # Only update local variables, no serial commands to prevent freezes
        if key == "behavior.idle_timeout_seconds":
            self.idle_timeout = value
        elif key == "behavior.sleep_timeout_minutes":
            self.sleep_timeout = value * 60  # Convert minutes to seconds
            print(f"🔧 Sleep timeout updated: {value} minutes ({self.sleep_timeout}s)")
        elif key.startswith("app_animations."):
            self._app_animation_last_sent = 0.0
        elif key.startswith("spotify.") and hasattr(self, "media_bridge"):
            self.media_bridge.configure_spotify(self.config.get_setting("spotify") or {})
        elif key == "diagnostics.esp32_cpu_meter_enabled":
            self.esp32_cpu_meter_enabled = bool(value)
            # The serial lock keeps this tiny live toggle separate from artwork.
            self.send_command(
                f"DIAG_CPU:{'ON' if self.esp32_cpu_meter_enabled else 'OFF'}"
            )
        
        # NOTE: Display/hardware settings require restart to apply
    
    def save_config_to_arduino(self):
        """Save current configuration to Arduino EEPROM"""
        print("💾 Saving configuration to Arduino EEPROM...")
        self.send_command("SAVE_SETTINGS")
        print("✅ Configuration saved to Arduino EEPROM")

    def apply_all_config_to_arduino(self):
        """Send all current configuration settings to Arduino"""
        if not self.config:
            return
        
        print("📤 Applying all configuration to Arduino...")
        
        # Apply display settings
        display = self.config.get_display_settings()
        self.send_command(f"DISPLAY_CPU:{'ON' if display.get('show_cpu') else 'OFF'}")
        self.send_command(f"DISPLAY_RAM:{'ON' if display.get('show_ram') else 'OFF'}")
        self.send_command(f"DISPLAY_WPM:{'ON' if display.get('show_wpm') else 'OFF'}")
        self.send_command(f"DISPLAY_TIME:{'ON' if display.get('show_time') else 'OFF'}")
        self.send_command(f"TIME_FORMAT:{'24' if display.get('time_format_24h') else '12'}")
        
        # Apply behavior settings  
        behavior = self.config.get_behavior_settings()
        self.send_command(f"SLEEP_TIMEOUT:{behavior.get('sleep_timeout_minutes', 5)}")
        
        # Save settings to Arduino EEPROM
        self.send_command("SAVE_SETTINGS")
        
        print("✅ Configuration applied to Arduino")

    def find_esp32_port(self):
        """Auto-detect ESP32 COM port - EXACT ORIGINAL IMPLEMENTATION"""
        print("🔍 Scanning for ESP32...")
        
        ports = serial.tools.list_ports.comports()
        esp32_ports = []
        
        for port in ports:
            # Common ESP32 identifiers
            esp32_keywords = [
                'CP210',  # Silicon Labs CP2102/CP2104
                'CH340',  # CH340 USB-to-serial chip
                'CH341',  # CH341 USB-to-serial chip  
                'FT232',  # FTDI chip
                'ESP32',  # Direct ESP32 reference
                'Silicon Labs',
                'QinHeng Electronics'
            ]
            
            description = str(port.description).upper()
            manufacturer = str(port.manufacturer).upper() if port.manufacturer else ""
            
            for keyword in esp32_keywords:
                if keyword.upper() in description or keyword.upper() in manufacturer:
                    esp32_ports.append(port)
                    print(f"🎯 Found potential ESP32: {port.device} - {port.description}")
                    break
        
        if not esp32_ports:
            print("❌ No ESP32 found automatically")
            print("📋 Available ports:")
            for port in ports:
                print(f"   {port.device} - {port.description}")
            return None
        
        if len(esp32_ports) == 1:
            selected_port = esp32_ports[0].device
            print(f"✅ Auto-selected: {selected_port}")
            return selected_port
        else:
            print("🤔 Multiple ESP32 devices found:")
            for i, port in enumerate(esp32_ports):
                print(f"   {i+1}: {port.device} - {port.description}")
            
            try:
                choice = input("Enter number (or press Enter for first): ").strip()
                if not choice:
                    selected_port = esp32_ports[0].device
                else:
                    index = int(choice) - 1
                    selected_port = esp32_ports[index].device
                
                print(f"✅ Selected: {selected_port}")
                return selected_port
            except (ValueError, IndexError):
                print("❌ Invalid selection, using first device")
                return esp32_ports[0].device

    def connect_serial(self, retries=3):
        """Connect to ESP32 via serial with retry logic - EXACT ORIGINAL IMPLEMENTATION"""
        if self.port == 'AUTO' or not self.port:
            detected_port = self.find_esp32_port()
            if detected_port:
                self.port = detected_port
            else:
                print("❌ Could not auto-detect ESP32. Please specify port manually.")
                return False
        
        for attempt in range(retries):
            try:
                if attempt > 0:
                    print(f"🔄 Retry attempt {attempt + 1}/{retries}...")
                    time.sleep(2)
                
                print(f"🔌 Connecting to {self.port}...")
                # ESP32-optimized serial configuration to prevent freezes
                # EXACT ORIGINAL: Simple serial connection like the working script
                self.serial_conn = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    timeout=1
                )
                time.sleep(2)  # Wait for ESP32 to restart
                
                # Test connection
                self.send_command("PING")
                time.sleep(0.1)
                
                if self.serial_conn.in_waiting > 0:
                    response = self.serial_conn.readline().decode().strip()
                    if "PONG" in response:
                        print(f"✅ Connected to Bongo Cat on {self.port}")
                        print(f"🐱 ESP32 Response: {response}")
                        # Send initial time sync
                        self.send_initial_sync()
                        # Update tray connection status
                        if self.tray:
                            self.tray.update_connection_status("connected")
                        return True
                
                print(f"✅ Connected to {self.port}")
                # Send initial time sync
                self.send_initial_sync()
                # Update tray connection status
                if self.tray:
                    self.tray.update_connection_status("connected")
                return True
                
            except Exception as e:
                print(f"❌ Connection failed: {e}")
                if attempt < retries - 1:
                    continue
                # Update tray connection status on failure
                if self.tray:
                    self.tray.update_connection_status("error")
                return False
        
        # Update tray connection status on failure
        if self.tray:
            self.tray.update_connection_status("error")
        return False
    
    def send_initial_sync(self):
        """Send initial time and system stats when connection is established - EXACT ORIGINAL IMPLEMENTATION"""
        try:
            # Send current time immediately
            current_time_str = datetime.datetime.now().strftime("%H:%M")
            time_command = f"TIME:{current_time_str}"
            self.send_command(time_command)
            print(f"🕐 Initial time sync: {current_time_str}")
            
            # Send initial system stats
            cpu, ram = self.get_system_stats()
            stats_command = f"STATS:CPU:{cpu},RAM:{ram},WPM:0"
            self.send_command(stats_command)
            print(f"📊 Initial stats: CPU {cpu}%, RAM {ram}%")
            
            # Initialize timing variables
            self.last_stats_sent = time.time()
            self.last_time_sent = time.time()
            
        except Exception as e:
            print(f"⚠️ Initial sync error: {e}")
    
    def disconnect_serial(self):
        """Disconnect from ESP32 - EXACT ORIGINAL IMPLEMENTATION"""
        if self.serial_conn and self.serial_conn.is_open:
            self.send_command("STOP")  # Use explicit stop command
            time.sleep(0.1)
            self.serial_conn.close()
            print("📱 Disconnected from Bongo Cat")
            # Update tray connection status
            if self.tray:
                self.tray.update_connection_status("disconnected")
    
    def send_command(self, command):
        """EXACT ORIGINAL: Simple command sending like the working script"""
        if self.serial_conn and self.serial_conn.is_open:
            try:
                with self._serial_lock:
                    self.serial_conn.write(f"{command}\n".encode())
            except Exception as e:
                print(f"⚠️ Command '{command}' failed: {e}")

    def get_media_status(self):
        """Read local media diagnostics without waking Spotify's API."""
        try:
            status = self.media_bridge.status()
            with self._data_lock:
                status["resources"] = {
                    "app_cpu_percent": self.app_cpu_percent,
                    "app_cpu_percent_one_core": self.app_cpu_percent_one_core,
                    "app_memory_mib": self.app_memory_mib,
                    "system_cpu_percent": self.cpu_percent,
                    "logical_cpu_count": self.logical_cpu_count,
                    "system_ram_percent": self.ram_percent,
                    "system_memory_available_mib": self.system_memory_available_mib,
                    "system_memory_total_mib": self.system_memory_total_mib,
                    "display_connected": bool(
                        self.serial_conn and self.serial_conn.is_open
                    ),
                    "esp32_free_heap_bytes": self.esp32_free_heap_bytes,
                    "esp32_heap_total_bytes": self.esp32_heap_total_bytes,
                    "esp32_min_heap_bytes": self.esp32_min_heap_bytes,
                    "esp32_free_psram_bytes": self.esp32_free_psram_bytes,
                    "esp32_psram_total_bytes": self.esp32_psram_total_bytes,
                    "esp32_cpu_meter_enabled": self.esp32_cpu_meter_enabled,
                    "esp32_cpu_estimate_percent": self.esp32_cpu_estimate_percent,
                    "esp32_cpu_sample_ms": self.esp32_cpu_sample_ms,
                    "esp32_status_age_seconds": max(0.0, time.time() - self.esp32_status_at)
                    if self.esp32_status_at else None,
                }
            return status
        except Exception as exc:
            return {"spotify": {"state": "error", "message": str(exc)}}

    @staticmethod
    def _clean_media_text(value, limit=72):
        value = unicodedata.normalize("NFKD", value or "")
        value = value.encode("ascii", "ignore").decode("ascii")
        value = " ".join(value.replace("|", "/").split())
        return value[:limit]

    def _on_media_update(self, snapshot: MediaSnapshot, artwork):
        """Send Windows now-playing state and optional RGB888 vinyl artwork."""
        if not self.serial_conn or not self.serial_conn.is_open:
            return

        title = self._clean_media_text(snapshot.title) or "Nothing playing"
        artist = self._clean_media_text(snapshot.artist) or "Start Spotify on this PC"
        source = self._clean_media_text(snapshot.source, 12) or "WINDOWS"
        meta = (snapshot.available, source, title, artist)
        state = "PLAYING" if snapshot.playing else ("PAUSED" if snapshot.available else "NONE")
        media_time = (snapshot.position_seconds, snapshot.duration_seconds)
        now = time.monotonic()
        full_sync_due = now - self._last_media_full_sync >= 3.0
        track_changed = bool(
            snapshot.track_key and snapshot.track_key != self._last_media_track_key
        )

        lines = []
        send_meta = meta != self._last_media_meta or full_sync_due
        send_state = state != self._last_media_state or full_sync_due
        send_time = media_time != self._last_media_time or full_sync_due
        if send_meta:
            lines.extend(
                (
                    f"MEDIA_SOURCE:{source}",
                    f"MEDIA_TITLE:{title}",
                    f"MEDIA_ARTIST:{artist}",
                )
            )
        if send_state:
            lines.append(f"MEDIA_STATE:{state}")
        if send_time:
            lines.append(f"MEDIA_TIME:{media_time[0]}:{media_time[1]}")
        if track_changed and artwork is None:
            lines.append("MEDIA_ART_DEFAULT")

        try:
            if lines:
                payload = ("\n".join(lines) + "\n").encode("ascii", "replace")
                # Never stall Spotify polling or touch handling behind a cover
                # upload. A skipped packet is retried on the next snapshot, and
                # the complete state is resent every three seconds.
                if self._serial_lock.acquire(timeout=0.02):
                    try:
                        self.serial_conn.write(payload)
                    finally:
                        self._serial_lock.release()
                    if send_meta:
                        self._last_media_meta = meta
                    if send_state:
                        self._last_media_state = state
                    if send_time:
                        self._last_media_time = media_time
                    if full_sync_due:
                        self._last_media_full_sync = now
                    if track_changed:
                        self._last_media_track_key = snapshot.track_key

            if artwork:
                # Artwork is much larger than state commands. Queue only the
                # newest cover and send it on a dedicated thread so Spotify
                # polling and touch controls never wait for the serial upload.
                try:
                    self._artwork_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self._artwork_queue.put_nowait((artwork, 0))
                except queue.Full:
                    pass
        except Exception as e:
            print(f"⚠️ Media send failed: {e}")

    def _artwork_sender_loop(self):
        """Serialize cover uploads without blocking Spotify API handling."""
        while self.running:
            try:
                artwork, attempt = self._artwork_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if not self.serial_conn or not self.serial_conn.is_open:
                continue
            try:
                header = (
                    f"MEDIA_ART_RGB:{ARTWORK_SIZE}:{ARTWORK_SIZE}:{len(artwork)}\n"
                ).encode("ascii")
                self._artwork_ack.clear()
                with self._serial_lock:
                    self.serial_conn.write(header)
                    # Do not burst 27 KB into the ESP32's UART while LVGL is
                    # flushing the display. A dropped byte offsets every RGB
                    # triplet after it, which looks like a scrambled cover.
                    for offset in range(0, len(artwork), ARTWORK_CHUNK_BYTES):
                        chunk = artwork[offset:offset + ARTWORK_CHUNK_BYTES]
                        written = self.serial_conn.write(chunk)
                        if written != len(chunk):
                            raise serial.SerialTimeoutException(
                                f"Artwork write was partial ({written}/{len(chunk)})"
                            )
                        # Flush every short block, then leave enough wire time
                        # for the ESP32 to drain its UART while LVGL renders.
                        # This prevents a lost RGB byte from scrambling the
                        # lower portion of a cover.
                        self.serial_conn.flush()
                        time.sleep(ARTWORK_CHUNK_PAUSE_SECONDS)
                    self.serial_conn.flush()
                print(f"🎨 Sent album artwork ({len(artwork)} bytes)")
                if not self._artwork_ack.wait(timeout=4.0) and attempt == 0:
                    print("⚠️ Artwork acknowledgement missed; scheduling one retry")
                    try:
                        self._artwork_queue.put_nowait((artwork, 1))
                    except queue.Full:
                        pass
            except Exception as e:
                if self.running:
                    print(f"⚠️ Artwork send failed: {e}")

    def _serial_reader_loop(self):
        """Receive touch media commands and diagnostics from the ESP32."""
        while self.running and self.serial_conn and self.serial_conn.is_open:
            try:
                raw = self.serial_conn.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", "ignore").strip()
                if line == "MEDIA_ART_OK":
                    self._artwork_ack.set()
                elif line.startswith("MEDIA_CMD:"):
                    action = line.split(":", 1)[1]
                    self.media_bridge.control(action)
                    print(f"🎵 Touch control: {action}")
                elif line.startswith("ESP32_STATUS:"):
                    values = {}
                    for item in line.split(":", 1)[1].split(","):
                        key, separator, value = item.partition(":")
                        if not separator:
                            continue
                        try:
                            values[key] = int(value)
                        except ValueError:
                            continue
                    with self._data_lock:
                        self.esp32_free_heap_bytes = values.get("HEAP")
                        self.esp32_heap_total_bytes = values.get("HEAP_TOTAL")
                        self.esp32_min_heap_bytes = values.get("MIN_HEAP")
                        self.esp32_free_psram_bytes = values.get("PSRAM")
                        self.esp32_psram_total_bytes = values.get("PSRAM_TOTAL")
                        self.esp32_uptime_seconds = values.get("UPTIME")
                        self.esp32_cpu_meter_enabled = bool(values.get("CPU_ENABLED", 0))
                        estimate = values.get("CPU_ESTIMATE")
                        self.esp32_cpu_estimate_percent = (
                            estimate if estimate is not None and estimate >= 0 else None
                        )
                        self.esp32_cpu_sample_ms = values.get("CPU_SAMPLE_MS")
                        self.esp32_status_at = time.time()
            except Exception as e:
                if self.running:
                    print(f"⚠️ Serial reader error: {e}")
                time.sleep(0.1)

    def _foreground_app_loop(self):
        """Select an animation from the foreground Windows app at low cost."""
        while self.running and not self._foreground_stop.is_set():
            settings = (
                self.config.get_app_animation_settings() if self.config else {}
            ) or {}
            selected = None
            matched = ""
            if settings.get("enabled", False):
                process_name, window_title = get_foreground_app()
                searchable = f"{process_name} {window_title}"
                for rule in settings.get("rules", []):
                    needle = str(rule.get("match", "")).strip().lower()
                    if needle and needle in searchable:
                        selected = rule.get("animation")
                        matched = needle
                        break

            if selected != self._app_animation:
                self._app_animation = selected
                self._app_animation_last_sent = 0.0
                self.last_sent_state = ""
                if selected:
                    print(f"🖥️ App animation: {matched} -> {selected}")
                else:
                    print("🖥️ App animation: automatic")

            if selected and time.monotonic() - self._app_animation_last_sent >= 2.0:
                self.send_command(f"ANIM:{selected}")
                self._app_animation_last_sent = time.monotonic()

            poll_seconds = max(0.5, float(settings.get("poll_seconds", 1.0)))
            self._foreground_stop.wait(poll_seconds)
    
    def start_system_monitor(self):
        """Start the dedicated system monitoring thread for real-time CPU/RAM updates"""
        if not self.system_monitor_running:
            self.system_monitor_running = True
            self.system_monitor_thread = threading.Thread(target=self._system_monitor_loop, daemon=True)
            self.system_monitor_thread.start()
            print("📊 System monitor thread started for real-time CPU/RAM updates")
    
    def stop_system_monitor(self):
        """Stop the system monitoring thread"""
        self.system_monitor_running = False
        if self.system_monitor_thread:
            self.system_monitor_thread.join(timeout=2.0)
            print("📊 System monitor thread stopped")
    
    def _system_monitor_loop(self):
        """Background thread that continuously monitors CPU and RAM"""
        print("🔍 System monitoring thread started - providing real-time updates")
        
        while self.system_monitor_running:
            try:
                # Get accurate CPU reading with 1-second measurement
                cpu_usage = psutil.cpu_percent(interval=1.0)
                
                # Get current RAM usage (this is instant)
                memory = psutil.virtual_memory()
                ram_usage = memory.percent
                memory_available_mib = memory.available / (1024 * 1024)
                memory_total_mib = memory.total / (1024 * 1024)
                # psutil's per-process percentage is expressed against one
                # logical core and can exceed 100. Normalize it so it uses the
                # same whole-computer 0–100 scale as system_cpu_percent.
                app_cpu_usage_one_core = self._process_handle.cpu_percent(None)
                app_cpu_usage = app_cpu_usage_one_core / self.logical_cpu_count
                app_memory_mib = self._process_handle.memory_info().rss / (1024 * 1024)
                
                # Update shared variables (thread-safe)
                with self._data_lock:
                    # Keep one decimal: idle computers frequently sit below
                    # one percent, where integer truncation looked like 0%.
                    self.cpu_percent = round(cpu_usage, 1)
                    self.ram_percent = int(ram_usage)
                    self.system_memory_available_mib = round(memory_available_mib, 1)
                    self.system_memory_total_mib = round(memory_total_mib, 1)
                    self.app_cpu_percent = round(app_cpu_usage, 1)
                    self.app_cpu_percent_one_core = round(app_cpu_usage_one_core, 1)
                    self.app_memory_mib = round(app_memory_mib, 1)
                if self.config:
                    self.config.reload_if_changed()
                self._write_desktop_status()
                
            except Exception as e:
                print(f"⚠️ System monitor error: {e}")
                # Continue running even with errors
                time.sleep(1.0)

    def _write_desktop_status(self):
        """Expose small read-only diagnostics for the detached settings UI."""
        if not self._status_path:
            return
        try:
            with self._data_lock:
                payload = {
                    "app_cpu_percent": self.app_cpu_percent,
                    "app_cpu_percent_one_core": self.app_cpu_percent_one_core,
                    "app_memory_mib": self.app_memory_mib,
                    "system_cpu_percent": self.cpu_percent,
                    "logical_cpu_count": self.logical_cpu_count,
                    "system_ram_percent": self.ram_percent,
                    "system_memory_available_mib": self.system_memory_available_mib,
                    "system_memory_total_mib": self.system_memory_total_mib,
                    "esp32": {
                        "connected": bool(self.serial_conn and self.serial_conn.is_open),
                        "free_heap_bytes": self.esp32_free_heap_bytes,
                        "heap_total_bytes": self.esp32_heap_total_bytes,
                        "min_heap_bytes": self.esp32_min_heap_bytes,
                        "free_psram_bytes": self.esp32_free_psram_bytes,
                        "psram_total_bytes": self.esp32_psram_total_bytes,
                        "uptime_seconds": self.esp32_uptime_seconds,
                        "cpu_meter_enabled": self.esp32_cpu_meter_enabled,
                        "cpu_estimate_percent": self.esp32_cpu_estimate_percent,
                        "cpu_sample_ms": self.esp32_cpu_sample_ms,
                        "status_age_seconds": max(0.0, time.time() - self.esp32_status_at)
                        if self.esp32_status_at else None,
                    },
                }
            payload["media"] = self.media_bridge.status()
            temporary = self._status_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(payload), encoding="utf-8")
            os.replace(temporary, self._status_path)
        except Exception:
            pass
    
    def get_system_stats(self):
        """Get current CPU and RAM usage - FAST NON-BLOCKING VERSION"""
        try:
            # Simply return the latest values from the monitoring thread
            with self._data_lock:
                return self.cpu_percent, self.ram_percent
        except Exception as e:
            print(f"⚠️ System stats access error: {e}")
            return 0, 0
    
    def send_system_stats(self):
        """Send system stats and current computer time to ESP32 - EXACT ORIGINAL IMPLEMENTATION"""
        cpu, ram = self.get_system_stats()
        wpm = int(self.current_wpm)
        
        # Send system stats
        stats_command = f"STATS:CPU:{cpu},RAM:{ram},WPM:{wpm}"
        self.send_command(stats_command)
        
        # Send current computer time (automatically synced)
        current_time = datetime.datetime.now().strftime("%H:%M")
        time_command = f"TIME:{current_time}"
        self.send_command(time_command)
    
    def update_system_stats(self):
        """Update system stats with fast real-time data from monitoring thread"""
        current_time = time.time()
        
        # Rate limit to prevent overwhelming the serial connection
        if not hasattr(self, 'last_stats_sent'):
            self.last_stats_sent = 0
            self.last_time_sent = 0
        
        # Send system stats every 2 seconds - now with real-time data!
        if current_time - self.last_stats_sent >= 2.0:
            try:
                # Get instant CPU/RAM data from monitoring thread (no blocking!)
                cpu, ram = self.get_system_stats()
                wpm = int(self.current_wpm) if hasattr(self, 'current_wpm') else 0
                stats_command = f"STATS:CPU:{cpu},RAM:{ram},WPM:{wpm}"
                self.send_command(stats_command)
                self.last_stats_sent = current_time
            except Exception as e:
                print(f"⚠️ Stats update error: {e}")
        
        # Send time updates every 30 seconds or on first call
        if current_time - self.last_time_sent >= 30.0 or self.last_time_sent == 0:
            try:
                current_time_str = datetime.datetime.now().strftime("%H:%M")
                time_command = f"TIME:{current_time_str}"
                self.send_command(time_command)
                self.last_time_sent = current_time
                print(f"🕐 Time synced: {current_time_str}")
            except Exception as e:
                print(f"⚠️ Time sync error: {e}")
    
    def calculate_wpm_industry_standard(self):
        """Industry standard WPM calculation with original script responsiveness"""
        now = time.time()
        
        # Cache WPM calculation to reduce CPU load during rapid typing
        if hasattr(self, '_last_wpm_calc_time') and (now - self._last_wpm_calc_time) < 0.05:
            return getattr(self, '_cached_wpm', 0)  # Return cached value if calculated recently
        
        # Thread-safe access to keystroke buffer - simplified approach
        with self._data_lock:
            if len(self.keystroke_buffer) < 2:
                # React to the first key immediately instead of waiting 400-500 ms
                # for a statistically meaningful WPM sample.
                self._cached_wpm = 30 if self.typing_active else 0
                self._last_wpm_calc_time = now
                return self._cached_wpm
            
            # Only use recent keystrokes to avoid expensive deque operations
            recent_keystrokes = list(self.keystroke_buffer)[-8:]  # Last 8 keystrokes only
            
            if len(recent_keystrokes) < 2:
                self._cached_wpm = 30 if self.typing_active else 0
                self._last_wpm_calc_time = now
                return self._cached_wpm
            
            time_span = now - recent_keystrokes[0]
            keystroke_count = len(recent_keystrokes)
        
        if time_span > 0.05:
            # Industry standard WPM calculation: (keystrokes ÷ 5) ÷ time_in_minutes
            raw_wpm = (keystroke_count / self.chars_per_word) * (60 / time_span)
            
            # Simple smoothing: just average with previous value (original script style)
            if hasattr(self, '_cached_wpm') and self._cached_wpm > 0:
                smoothed_wpm = (self._cached_wpm * 0.6) + (raw_wpm * 0.4)  # Original blend
            else:
                smoothed_wpm = raw_wpm
            
            # Cache the result
            self._cached_wpm = min(smoothed_wpm, self.max_wpm)
            self._last_wpm_calc_time = now
            return self._cached_wpm
        
        # A second key arrived almost instantly. Use a responsive baseline until
        # the next sample can calculate a stable WPM value.
        self._cached_wpm = 45 if self.typing_active else 0
        self._last_wpm_calc_time = now
        return self._cached_wpm
    
    def wpm_to_animation_speed(self, wpm):
        """Convert WPM to animation speed - SIMPLIFIED to prevent Arduino confusion with very small values"""
        if wpm <= 0:
            return self.min_animation_speed
        
        # SIMPLIFIED: Linear mapping to prevent Arduino issues with very small values
        # Clamp WPM to reasonable range
        wpm = min(wpm, self.max_wpm)
        
        # Linear interpolation from min_speed to max_speed
        normalized = wpm / self.max_wpm
        speed = self.min_animation_speed - (normalized * (self.min_animation_speed - self.max_animation_speed))
        
        result = int(max(min(speed, self.min_animation_speed), self.max_animation_speed))
        
        return result
    
    def determine_animation_state(self, wpm):
        """Determine animation state with improved hysteresis - EXACT ORIGINAL IMPLEMENTATION"""
        # EXACT ORIGINAL: Simple hysteresis like the working script
        hysteresis = 2  # Reduced for more responsiveness while maintaining stability
        
        if self.current_state == "IDLE":
            if wpm >= 3:  # Very low threshold to start typing animation
                if wpm < self.slow_threshold:
                    return "SLOW"
                elif wpm < self.normal_threshold:
                    return "NORMAL"
                else:
                    return "FAST"
        elif self.current_state == "SLOW":
            if wpm < 2:
                return "IDLE"
            elif wpm >= self.slow_threshold + hysteresis:
                if wpm < self.normal_threshold:
                    return "NORMAL"
                else:
                    return "FAST"
        elif self.current_state == "NORMAL":
            if wpm < self.slow_threshold - hysteresis:
                return "SLOW" if wpm >= 2 else "IDLE"
            elif wpm >= self.normal_threshold + hysteresis:
                return "FAST"
        elif self.current_state == "FAST":
            if wpm < self.normal_threshold - hysteresis:
                if wpm >= self.slow_threshold:
                    return "NORMAL"
                else:
                    return "SLOW" if wpm >= 2 else "IDLE"
        
        return self.current_state  # No change if within hysteresis range
    
    def is_streak_active(self, wpm):
        """Determine if streak mode should be active based on WPM - EXACT ORIGINAL IMPLEMENTATION"""
        return wpm >= self.fast_threshold  # 65+ WPM triggers streak mode
    
    def handle_idle_progression(self, now):
        """Handle controlled idle progression"""
        if not self.typing_active:
            if not self.idle_progression_started:
                if now - self.idle_start_time > 1.5:
                    self.send_command("IDLE_START")
                    self.idle_progression_started = True
                    print("😴 Starting idle progression...")
        else:
            self.idle_start_time = 0
            self.idle_progression_started = False
    
    def on_key_press(self, key):
        """Count physical typing keys once; ignore modifiers and key-repeat."""
        try:
            current_time = time.time()

            # pynput receives repeated press events while a key is held. Count
            # printable characters (and spaces) only once until their release,
            # so holding Shift or any other key cannot create fake WPM.
            character = getattr(key, "char", None)
            is_space = key == keyboard.Key.space
            if not is_space and (not character or not character.isprintable()):
                return
            key_id = "space" if is_space else f"char:{character}"
            
            # Thread-safe keystroke recording
            with self._data_lock:
                if key_id in self._pressed_typing_keys:
                    return
                self._pressed_typing_keys.add(key_id)
                self.keystroke_buffer.append(current_time)
                self.last_keystroke_time = current_time
                
                # Mark as actively typing
                if not self.typing_active:
                    self.typing_active = True
                    self.sleep_start_time = None  # Reset sleep timer when typing resumes
                    print("⌨️ Typing started - keyboard listener working on main thread!")
                    # Update tray typing status
                    if self.tray:
                        self.tray.update_typing_status(True, self.current_wpm)
            
            # NO heavy operations here - everything moved to background thread
                
        except Exception as e:
            print(f"❌ Keystroke detection error: {e}")
            # Continue processing even if there's an error

    def on_key_release(self, key):
        """Allow the next physical press of a counted typing key."""
        try:
            character = getattr(key, "char", None)
            is_space = key == keyboard.Key.space
            if not is_space and (not character or not character.isprintable()):
                return
            key_id = "space" if is_space else f"char:{character}"
            with self._data_lock:
                self._pressed_typing_keys.discard(key_id)
        except Exception:
            pass
    
    def send_animation_command(self, wpm, force_update=False):
        """Send animation command with improved rate limiting and separate streak handling - EXACT ORIGINAL IMPLEMENTATION"""
        current_time = time.time()

        if self._app_animation:
            if force_update or time.monotonic() - self._app_animation_last_sent >= 1.0:
                self.send_command(f"ANIM:{self._app_animation}")
                self._app_animation_last_sent = time.monotonic()
            return
        
        # CRITICAL FIX: During active typing, send commands every second to keep Arduino alive
        # Only apply rate limiting during idle periods
        if not force_update and not self.typing_active and (current_time - self.last_command_time) < self.min_command_interval:
            return  # Skip this update to maintain stable communication during idle only
        
        # Determine animation state and speed
        new_state = self.determine_animation_state(wpm)
        animation_speed = self.wpm_to_animation_speed(wpm)
        is_streak = self.is_streak_active(wpm)
        
        # Track streak state changes
        if not hasattr(self, 'last_streak_state'):
            self.last_streak_state = False
        
        # EXACT ORIGINAL: Simple change detection like the working script
        speed_changed = abs(animation_speed - self.last_sent_speed) > 25  # Filter micro-adjustments: 25ms threshold
        state_changed = new_state != self.last_sent_state
        streak_changed = is_streak != self.last_streak_state
        
        # CRITICAL FIX: More frequent updates during typing to prevent Arduino starvation
        time_since_last_command = current_time - self.last_command_time
        
        if self.typing_active:
            # During typing: send commands every 1 second even if nothing changed
            force_periodic_update = time_since_last_command > 1.0
        else:
            # During idle: less frequent updates are fine
            force_periodic_update = time_since_last_command > 4.0
        
        if state_changed or speed_changed or streak_changed or force_update or force_periodic_update:
            # Update state tracking regardless of serial connection
            self.last_sent_speed = animation_speed
            self.last_sent_state = new_state
            self.last_command_time = current_time
            
            # Handle streak state tracking
            if streak_changed:
                self.last_streak_state = is_streak
            
            # CRITICAL DEBUG: Show when periodic updates happen during consistent typing
            if force_periodic_update and not (state_changed or speed_changed or streak_changed or force_update):
                interval_type = "1s" if self.typing_active else "4s"
                print(f"🔄 Keep-alive ({interval_type}): {new_state} | WPM: {self.current_wpm:.1f} | Speed: {animation_speed}ms | Gap: {time_since_last_command:.1f}s")
            
            # Update current state and print changes
            # Debug output for state changes only
            if state_changed or streak_changed or force_update:
                if self.current_state != new_state or streak_changed:
                    # Emoji based on state and streak
                    base_emoji = {"SLOW": "🐌", "NORMAL": "👐", "FAST": "⚡"}.get(new_state, "")
                    emoji = f"{base_emoji}😊" if is_streak else base_emoji
                    streak_text = " (HAPPY)" if is_streak else ""
                    print(f"🐱 {self.current_state} → {new_state}{streak_text} | WPM: {self.current_wpm:.1f} | Speed: {animation_speed}ms {emoji}")
                    self.current_state = new_state
                    self.state_change_time = current_time
            
            # Send commands to Arduino if connected
            if self.serial_conn and self.serial_conn.is_open:
                try:
                    # Combine commands to reduce serial writes and prevent buffer overflow
                    commands_to_send = []
                    
                    if wpm <= 0:
                        commands_to_send.append("STOP")
                        # Turn off streak when stopping
                        if self.last_streak_state:
                            commands_to_send.append("STREAK_OFF")
                            self.last_streak_state = False
                    else:
                        commands_to_send.append(f"SPEED:{animation_speed}")
                        # Handle streak mode separately
                        if streak_changed:
                            if is_streak:
                                commands_to_send.append("STREAK_ON")
                            else:
                                commands_to_send.append("STREAK_OFF")
                    
                    # EXACT ORIGINAL: Simple command sending like the working script
                    if commands_to_send:
                        combined_command = '\n'.join(commands_to_send) + '\n'
                        with self._serial_lock:
                            self.serial_conn.write(combined_command.encode())
                        
                except serial.SerialTimeoutException:
                    # Non-blocking write timed out - Arduino buffer full, skip this update
                    print("⚠️ Serial buffer full - skipping command")
                except Exception as e:
                    print(f"❌ Command send error: {e}")
    
    def update_animation(self):
        """Enhanced animation update with proper idle progression and thread safety - EXACT ORIGINAL IMPLEMENTATION"""
        try:
            current_time = time.time()
            
            # Handle system stats periodically (moved from keystroke handler)
            try:
                self.update_system_stats()
            except Exception as stats_error:
                print(f"⚠️ Stats update error: {stats_error}")
            
            # Thread-safe access to keystroke data
            with self._data_lock:
                last_keystroke_time = self.last_keystroke_time
                keystroke_buffer_copy = list(self.keystroke_buffer)  # Copy for processing
                typing_active = self.typing_active
            
            # Check for idle timeout
            if current_time - last_keystroke_time > self.idle_timeout:
                # Typing has stopped
                if typing_active:
                    with self._data_lock:
                        self.typing_active = False
                        self.current_wpm = 0
                        self.idle_start_time = current_time
                        # Clear the keystroke buffer
                        self.keystroke_buffer.clear()
                        # Update tray typing status
                        if self.tray:
                            self.tray.update_typing_status(False, 0)
                    
                    # Send final animation command with WPM = 0 to reset display
                    self.send_animation_command(0, force_update=True)
                    print(f"💤 Typing stopped - will sleep after {self.sleep_timeout}s")
                
                # Check if it's time to start sleep progression
                time_idle = current_time - self.idle_start_time
                if time_idle >= self.sleep_timeout and self.sleep_start_time is None:
                    # Time to start sleep progression
                    self.sleep_start_time = current_time
                    if self.serial_conn and self.serial_conn.is_open:
                        self.serial_conn.write(b"IDLE_START\n")
                        print(f"😴 Sleep timeout reached ({self.sleep_timeout}s) - starting sleep progression")
                
                # Don't send any more commands when idle
                return
            
            # Currently typing - calculate WPM
            if keystroke_buffer_copy:
                new_wpm = self.calculate_wpm_industry_standard()
                
                # BALANCED WPM smoothing - responsive but stable
                if self.current_wpm == 0:
                    self.current_wpm = new_wpm  # Initial value
                else:
                    # EXACT ORIGINAL: Adaptive smoothing like the working script
                    wpm_diff = abs(new_wpm - self.current_wpm)
                    if wpm_diff > 15:  # Big change - respond quickly
                        smoothing = 0.7
                    elif wpm_diff > 5:  # Medium change - moderate smoothing  
                        smoothing = 0.4
                    else:  # Small change - heavy smoothing
                        smoothing = 0.2
                    
                    self.current_wpm = (self.current_wpm * (1 - smoothing)) + (new_wpm * smoothing)
                
                # Send animation command with rate limiting
                self.send_animation_command(self.current_wpm)
                        
        except Exception as e:
            print(f"❌ Animation update error: {e}")
    
    def update_animation_loop(self):
        """Background thread with optimized update logic and freeze detection - EXACT ORIGINAL IMPLEMENTATION"""
        print("🎬 Animation thread started")
        while self.running:
            try:
                current_time = time.time()
                
                self.update_animation()  # Use the new optimized method
                self.update_system_stats()  # Send system stats (CPU, RAM, WPM) periodically
                time.sleep(self.update_interval)
                
            except Exception as e:
                print(f"❌ Animation loop error: {e}")
                # Continue running even if there's an error
                time.sleep(0.1)
        print("🛑 Animation thread stopped")
    
    def start_monitoring(self):
        """Start the enhanced typing monitor - EXACT ORIGINAL IMPLEMENTATION with Configuration Support"""
        print("🚀 Bongo Cat Engine v3.1 - SUPER-FAST ANIMATION SUPPORT")
        print("=" * 70)
        print("🔧 CRITICAL FIXES APPLIED:")
        print("   • Threading: Engine runs on MAIN thread (like original script)")
        print("   • First-key response: under 100ms target")
        print("   • Periodic Updates: SILENT watchdog feeding every 4s (like original)")
        print("   • Serial Communication: SIMPLE like original (no buffer management)")
        print("   • Serial Timeout: STANDARD 1s timeout (like original)")
        print("   • Stats Commands: ONLY during IDLE (not during typing like original)")
        print("   • Config Commands: ENABLED for desktop app functionality")
        print("   • Keep-alive Frequency: EVERY 1 SECOND during typing (was 4s)")
        print("   • Rate Limiting: DISABLED during typing (enabled during idle)")
        print("   • Animation Speed: SUPPORTS super-fast typing (30ms-500ms range)")
        print("   • WPM Range: EXTENDED to 200 WPM (was 100 WPM cap)")
        print("   • Settings GUI: Fixed using pystray run_detached() method")
        print("   • Sleep Timeout: PROPERLY implemented (5 minutes default)")
        print("   • Buffer Clearing: REMOVED (was causing issues)")
        print("")
        print("🎯 Enhanced Features:")
        print("   • Industry-standard WPM calculation (5 chars = 1 word)")
        print("   • Automatic computer time synchronization")
        print("   • Configuration management support")
        print("   • Real-time settings updates")
        print("")
        print("📊 Animation States:")
        print(f"   • Slow: < {self.slow_threshold} WPM (4-step paw pattern)")
        print(f"   • Normal: {self.slow_threshold}-{self.normal_threshold-1} WPM (4-step paw pattern)")
        print(f"   • Fast: {self.normal_threshold}+ WPM (4-step paw + click effects)")
        print("")
        print("😊 Happy Face Mode:")
        print(f"   • Activates at {self.fast_threshold}+ WPM")
        print("")
        print("📝 Start typing to see your cat react!")
        print("🛑 Press Ctrl+C to stop")
        print("-" * 65)
        
        if self._stop_requested.is_set():
            return True
        connected = self.connect_serial()
        with self._lifecycle_lock:
            if self._stop_requested.is_set():
                if connected:
                    self.disconnect_serial()
                return True
            if not connected:
                return False
            self.running = True
            # Start real-time system monitoring thread
            self.start_system_monitor()
        
        # CRITICAL FIX: Apply config synchronously to prevent thread conflicts  
        if self.config:
            print("⏳ Applying configuration synchronously...")
            if self._stop_requested.wait(2.0):
                return True
            self.apply_all_config_to_arduino()

        # Keep listener startup and shutdown atomic. Exit can arrive while
        # serial connection or configuration is still in progress.
        listener = None
        try:
            with self._lifecycle_lock:
                if self._stop_requested.is_set():
                    return True
                # Start full-duplex media support after the initial handshake.
                self.serial_reader_thread = threading.Thread(
                    target=self._serial_reader_loop,
                    name="BongoDeskSerialReader",
                    daemon=True,
                )
                self.serial_reader_thread.start()
                self._artwork_sender_thread = threading.Thread(
                    target=self._artwork_sender_loop,
                    name="BongoDeskArtworkSender",
                    daemon=True,
                )
                self._artwork_sender_thread.start()
                self.media_bridge.start()
                print("🎵 Media bridge active (Spotify Connect preferred, Windows fallback)")

                self._foreground_stop.clear()
                self._foreground_app_thread = threading.Thread(
                    target=self._foreground_app_loop,
                    name="BongoDeskForegroundApp",
                    daemon=True,
                )
                self._foreground_app_thread.start()
                update_thread = threading.Thread(target=self.update_animation_loop, daemon=True)
                update_thread.start()

                listener = keyboard.Listener(
                    on_press=self.on_key_press,
                    on_release=self.on_key_release,
                )
                self.keyboard_listener = listener
                listener.start()
            listener.join()
        except KeyboardInterrupt:
            pass
        finally:
            if listener:
                listener.stop()
            with self._lifecycle_lock:
                if self.keyboard_listener is listener:
                    self.keyboard_listener = None
        
        return True
    
    def stop_monitoring(self):
        """Stop the typing monitor - EXACT ORIGINAL IMPLEMENTATION"""
        print("\n🛑 Stopping Bongo Cat monitor...")
        self._stop_requested.set()
        with self._lifecycle_lock:
            self.running = False
            if self.keyboard_listener:
                self.keyboard_listener.stop()
            self._foreground_stop.set()
            self.media_bridge.stop()
            self.disconnect_serial()
            self.stop_system_monitor() # Stop the system monitor thread
        print("👋 Thank you for using Bongo Cat! Keep typing! ⌨️🐱")
    
    def apply_all_config_to_arduino(self):
        """Send all current configuration settings to Arduino with proper spacing"""
        if not self.config:
            return
            
        print("⚙️ Applying configuration to Arduino with command spacing...")
        
        try:
            # Apply display settings with delays to prevent buffer overflow
            display = self.config.get_display_settings()
            self.send_command(f"DISPLAY_CPU:{'ON' if display.get('show_cpu') else 'OFF'}")
            time.sleep(0.1)  # Small delay between commands
            self.send_command(f"DISPLAY_RAM:{'ON' if display.get('show_ram') else 'OFF'}")
            time.sleep(0.1)
            self.send_command(f"DISPLAY_WPM:{'ON' if display.get('show_wpm') else 'OFF'}")
            time.sleep(0.1)
            self.send_command(f"DISPLAY_TIME:{'ON' if display.get('show_time') else 'OFF'}")
            time.sleep(0.1)
            self.send_command(f"TIME_FORMAT:{'24' if display.get('time_format_24h') else '12'}")
            time.sleep(0.2)  # Longer delay before behavior settings
            diagnostics = self.config.get_setting("diagnostics") or {}
            self.send_command(
                f"DIAG_CPU:{'ON' if diagnostics.get('esp32_cpu_meter_enabled') else 'OFF'}"
            )
            time.sleep(0.1)
            
            # Apply behavior settings with delays
            behavior = self.config.get_behavior_settings()
            self.send_command(f"SLEEP_TIMEOUT:{behavior.get('sleep_timeout_minutes', 1)}")
            time.sleep(0.5)  # Longer delay before save
            
            # Save settings to Arduino EEPROM
            self.send_command("SAVE_SETTINGS")
            
            print("✅ Configuration applied to Arduino with proper spacing")
            
        except Exception as e:
            print(f"⚠️ Configuration application error: {e}")
            print("💡 Engine will continue with default settings")

# For backwards compatibility 
BongoCatController = BongoCatEngine

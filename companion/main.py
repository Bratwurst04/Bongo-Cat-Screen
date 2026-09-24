#!/usr/bin/env python3
"""
Bongo Cat Application - Main Entry Point
Fixed threading model - Engine ALWAYS runs on main thread for proper keyboard timing
"""

import sys
import os
import signal
import argparse
import threading
from config import ConfigManager
from engine import BongoCatEngine
from spotify_api import SpotifyApiBridge, SpotifyApiError
from tray import BongoCatSystemTray
from windows_integration import SingleInstanceLock, set_start_with_windows

_instance_lock = SingleInstanceLock()

# A PyInstaller --windowed process has no console streams. Route diagnostic
# output to the null device so logging and argparse never crash the tray app.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
elif hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")
elif hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

class BongoCatApplication:
    """Run the engine on the main thread alongside the system tray."""
    
    def __init__(self, start_minimized=False):
        """Initialize the application"""
        self.start_minimized = start_minimized
        self.config = None
        self.engine = None
        self.tray = None
        self.running = False
        self._shutdown_lock = threading.RLock()
        self._shutdown_started = False
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, sig, frame):
        """Handle shutdown signals gracefully"""
        print('\n🛑 Shutting down gracefully...')
        self.shutdown()
    
    def initialize_components(self):
        """Initialize all application components"""
        try:
            # Initialize configuration manager
            print("📂 Loading configuration...")
            self.config = ConfigManager()
            set_start_with_windows(
                self.config.get_startup_settings().get("start_with_windows", True)
            )
            self.config.add_change_callback(self._on_config_change)
            
            # Initialize engine with configuration
            print("🔧 Initializing Bongo Cat Engine...")
            self.engine = BongoCatEngine(config_manager=self.config)
            
            # Initialize system tray (but don't start it yet)
            print("📱 Setting up system tray...")
            self.tray = BongoCatSystemTray(
                config_manager=self.config,
                engine=self.engine,
                on_exit_callback=self.shutdown
            )
            
            # Connect engine to tray for status updates
            self.engine.set_tray_reference(self.tray)
            
            # Connect tray to config for settings refresh
            self.config.add_change_callback(self.tray.on_config_change)
            
            return True
            
        except Exception as e:
            print(f"❌ Initialization error: {e}")
            return False

    def _on_config_change(self, key, value):
        if key == "startup.start_with_windows":
            try:
                set_start_with_windows(bool(value))
            except OSError as exc:
                print(f"Startup registration failed: {exc}")
    
    def run(self):
        """Run the application and preserve its exit status on failure."""
        print("🐱 Bongo Cat Application v2.1 - FIXED THREADING")
        print("=" * 60)
        
        # Initialize components
        if not self.initialize_components():
            self.shutdown()
            return 1
        
        self.running = True
        
        try:
            # CRITICAL FIX: Use pystray run_detached() method for proper GUI/tray coexistence
            print("📱 Starting system tray with run_detached()...")
            self.tray.start_detached()
            
            # Update initial connection status
            print("🔄 Checking initial connection status...")
            
            if self.start_minimized:
                print("🔕 Running in background mode...")
                print("📱 Look for the cat icon in your system tray")
                print("🖱️ Right-click the tray icon for options")
                print("⌨️ Keyboard monitoring active on main thread")
            else:
                print("🖥️ Running in normal mode...")
                print("📝 Start typing to see your cat react!")
                print("🔄 System tray available in background")
                print("🛑 Press Ctrl+C to stop")
            
            print("✅ System tray started with run_detached()")
            print("💡 Settings window available from tray menu")
            print("🎯 Starting animation engine on MAIN THREAD for optimal responsiveness...")
            
            # CRITICAL FIX: Engine ALWAYS runs on main thread (like original script)  
            # This ensures proper keyboard listener timing regardless of start mode
            if self.engine.start_monitoring() is False:
                return 1
                
        except KeyboardInterrupt:
            print("\n🛑 Interrupted by user")
        except Exception as e:
            print(f"❌ Runtime error: {e}")
            return 1
        finally:
            self.shutdown()
        
        return 0
    

    
    def shutdown(self):
        """Shutdown the application gracefully"""
        with self._shutdown_lock:
            if self._shutdown_started:
                return
            self._shutdown_started = True
            print("🛑 Shutting down components...")
            self.running = False
            if self.engine:
                self.engine.stop_monitoring()
            if self.tray:
                self.tray.stop()
            print("👋 Goodbye!")

def main():
    """Main application entry point"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Bongo Cat Typing Monitor")
    parser.add_argument("--minimized", action="store_true", 
                       help="Start minimized to system tray")
    parser.add_argument("--startup", action="store_true",
                       help="Started automatically with Windows")
    parser.add_argument("--spotify-client-id", default="",
                       help="Save a Spotify developer Client ID")
    parser.add_argument("--link-spotify", action="store_true",
                       help="Open Spotify authorization and save the user token")
    
    args = parser.parse_args()

    if args.spotify_client_id or args.link_spotify:
        config = ConfigManager()
        client_id = args.spotify_client_id.strip()
        if client_id:
            config.set_setting("spotify", "client_id", client_id)
            config.save_config()
        else:
            client_id = (config.get_setting("spotify", "client_id") or "").strip()

        if args.link_spotify:
            if not client_id:
                print("Spotify Client ID is missing")
                return 2
            try:
                spotify = SpotifyApiBridge(
                    client_id, config.config_dir / "spotify_tokens.json"
                )
                spotify.authorize_interactive()
                print("Spotify account linked")
                return 0
            except SpotifyApiError as exc:
                print(f"Spotify setup failed: {exc}")
                return 1

        return 0

    if not _instance_lock.acquire():
        print("BongoDeskSpotify is already running")
        return 0
    
    # Determine start mode
    start_minimized = args.minimized or args.startup
    
    # Create and run application
    app = BongoCatApplication(start_minimized=start_minimized)
    try:
        return app.run()
    finally:
        _instance_lock.close()

if __name__ == "__main__":
    sys.exit(main())

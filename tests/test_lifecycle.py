"""Regression checks for the companion's shutdown path."""

import sys
import unittest
from pathlib import Path
from threading import Event, Lock, Thread
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "companion"))

from engine import BongoCatEngine  # noqa: E402
from main import BongoCatApplication  # noqa: E402


class ApplicationLifecycleTests(unittest.TestCase):
    def make_app(self):
        with patch("main.signal.signal"):
            app = BongoCatApplication()
        app.engine = Mock()
        app.tray = Mock()
        return app

    def test_runtime_failure_keeps_error_exit_status(self):
        app = self.make_app()
        app.initialize_components = Mock(return_value=True)
        app.engine.start_monitoring.side_effect = RuntimeError("test failure")

        self.assertEqual(app.run(), 1)
        app.engine.stop_monitoring.assert_called_once_with()
        app.tray.stop.assert_called_once_with()

    def test_serial_connection_failure_returns_error(self):
        app = self.make_app()
        app.initialize_components = Mock(return_value=True)
        app.engine.start_monitoring.return_value = False

        self.assertEqual(app.run(), 1)
        app.engine.stop_monitoring.assert_called_once_with()

    def test_shutdown_only_stops_components_once(self):
        app = self.make_app()

        app.shutdown()
        app.shutdown()

        app.engine.stop_monitoring.assert_called_once_with()
        app.tray.stop.assert_called_once_with()

    def test_tray_shutdown_allows_normal_return(self):
        app = self.make_app()
        app.initialize_components = Mock(return_value=True)
        app.engine.start_monitoring.side_effect = app.shutdown

        self.assertEqual(app.run(), 0)
        app.engine.stop_monitoring.assert_called_once_with()
        app.tray.stop.assert_called_once_with()

    def test_engine_shutdown_stops_keyboard_listener(self):
        engine = BongoCatEngine.__new__(BongoCatEngine)
        engine.running = True
        engine._stop_requested = Event()
        engine._lifecycle_lock = Lock()
        engine.keyboard_listener = Mock()
        engine._foreground_stop = Event()
        engine.media_bridge = Mock()
        engine.disconnect_serial = Mock()
        engine.stop_system_monitor = Mock()

        engine.stop_monitoring()

        engine.keyboard_listener.stop.assert_called_once_with()
        self.assertFalse(engine.running)
        self.assertTrue(engine._stop_requested.is_set())

    def test_exit_during_connection_does_not_restart_monitoring(self):
        app = self.make_app()
        engine = BongoCatEngine.__new__(BongoCatEngine)
        engine.slow_threshold = 20
        engine.normal_threshold = 40
        engine.fast_threshold = 65
        engine.config = None
        engine.running = False
        engine.keyboard_listener = None
        engine._stop_requested = Event()
        engine._lifecycle_lock = Lock()
        engine._foreground_stop = Event()
        engine.media_bridge = Mock()
        engine.serial_conn = None
        engine._serial_lock = Lock()
        engine.tray = app.tray
        engine.stop_system_monitor = Mock()
        engine.start_system_monitor = Mock()
        serial_conn = Mock()
        serial_conn.is_open = True
        serial_conn.close.side_effect = lambda: setattr(serial_conn, "is_open", False)
        connected = Event()
        release_connection = Event()

        def connect_serial():
            connected.set()
            self.assertTrue(release_connection.wait(timeout=3))
            engine.serial_conn = serial_conn
            return True

        engine.connect_serial = connect_serial
        app.engine = engine
        app.initialize_components = Mock(return_value=True)
        result = []

        with patch("engine.keyboard.Listener") as listener:
            run_thread = Thread(target=lambda: result.append(app.run()), daemon=True)
            run_thread.start()
            self.assertTrue(connected.wait(timeout=3))
            app.shutdown()
            release_connection.set()
            run_thread.join(timeout=3)

        self.assertFalse(run_thread.is_alive())
        self.assertEqual(result, [0])
        self.assertFalse(engine.running)
        serial_conn.close.assert_called_once_with()
        self.assertFalse(serial_conn.is_open)
        listener.assert_not_called()
        engine.media_bridge.stop.assert_called_once_with()
        app.tray.stop.assert_called_once_with()

    def test_exit_after_listener_starts_releases_main_thread(self):
        app = self.make_app()
        engine = BongoCatEngine.__new__(BongoCatEngine)
        engine.slow_threshold = 20
        engine.normal_threshold = 40
        engine.fast_threshold = 65
        engine.config = None
        engine.running = False
        engine.keyboard_listener = None
        engine._stop_requested = Event()
        engine._lifecycle_lock = Lock()
        engine._foreground_stop = Event()
        engine.media_bridge = Mock()
        engine.connect_serial = Mock(return_value=True)
        engine.disconnect_serial = Mock()
        engine.start_system_monitor = Mock()
        engine.stop_system_monitor = Mock()
        engine._serial_reader_loop = Mock()
        engine._artwork_sender_loop = Mock()
        engine._foreground_app_loop = Mock()
        engine.update_animation_loop = Mock()
        app.engine = engine
        app.initialize_components = Mock(return_value=True)
        started = Event()
        stopped = Event()
        listener = Mock()
        listener.start.side_effect = started.set
        listener.join.side_effect = lambda: stopped.wait(timeout=3)
        listener.stop.side_effect = stopped.set
        result = []

        with patch("engine.keyboard.Listener", return_value=listener):
            run_thread = Thread(target=lambda: result.append(app.run()), daemon=True)
            run_thread.start()
            self.assertTrue(started.wait(timeout=3))
            app.shutdown()
            run_thread.join(timeout=3)

        self.assertFalse(run_thread.is_alive())
        self.assertEqual(result, [0])
        self.assertTrue(stopped.is_set())
        self.assertFalse(engine.running)
        engine.media_bridge.stop.assert_called_once_with()
        app.tray.stop.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()

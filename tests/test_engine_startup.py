"""Start without hardware and recover through the existing worker set."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "companion"))

from engine import BongoCatEngine
from main import BongoCatApplication


def port(name):
    return SimpleNamespace(device=name, description="USB CP2102", manufacturer=None)


class EngineStartupTests(unittest.TestCase):
    def make_engine(self):
        with patch("engine.WindowsMediaBridge"), patch("engine.psutil.Process"):
            engine = BongoCatEngine()
        engine.tray = Mock()
        engine.start_system_monitor = Mock()
        engine.stop_system_monitor = Mock()
        engine.send_initial_sync = Mock()
        return engine

    def test_auto_detection_with_no_stdin_never_prompts_or_guesses(self):
        engine = self.make_engine()
        cases = [([], None), ([port("TEST_A")], "TEST_A"),
                 ([port("TEST_A"), port("TEST_B")], None)]
        with patch("sys.stdin", None), patch("builtins.input", side_effect=AssertionError):
            for ports, expected in cases:
                for interactive in (False, True):
                    with self.subTest(count=len(ports), interactive=interactive), \
                         patch("engine.serial.tools.list_ports.comports", return_value=ports):
                        self.assertEqual(engine.find_esp32_port(interactive), expected)

    def test_auto_connect_opens_only_one_unambiguous_device(self):
        for ports, expected in [([], None), ([port("TEST_A")], "TEST_A"),
                                ([port("TEST_A"), port("TEST_B")], None)]:
            engine = self.make_engine()
            connection = Mock(is_open=True, in_waiting=0)
            with self.subTest(count=len(ports)), patch("sys.stdin", None), \
                 patch("builtins.input", side_effect=AssertionError), \
                 patch("engine.serial.tools.list_ports.comports", return_value=ports), \
                 patch("engine.serial.Serial", return_value=connection) as open_port, \
                 patch("engine.time.sleep"):
                self.assertEqual(engine.connect_serial(), expected is not None)
                if expected:
                    self.assertEqual(open_port.call_args.kwargs["port"], expected)
                    self.assertEqual(engine.port, expected)
                else:
                    open_port.assert_not_called()
                    engine.tray.update_connection_status.assert_called_with("disconnected")

    def test_explicit_port_remains_the_users_choice_among_multiple_devices(self):
        engine = self.make_engine()
        engine._auto_port = False
        engine.port = "TEST_B"
        with patch("engine.serial.tools.list_ports.comports", side_effect=AssertionError), \
             patch("engine.serial.Serial", return_value=Mock(is_open=True, in_waiting=0)) as opened, \
             patch("engine.time.sleep"):
            self.assertTrue(engine.connect_serial())
        self.assertEqual(opened.call_args.kwargs["port"], "TEST_B")

    def test_disconnected_start_keeps_tray_settings_and_one_worker_set(self):
        with patch("main.signal.signal"):
            app = BongoCatApplication()
        engine = self.make_engine()
        app.engine = engine
        app.tray = engine.tray
        app.initialize_components = Mock(return_value=True)
        threads = []
        listener = Mock()

        def thread(**kwargs):
            threads.append(kwargs)
            return Mock()

        def while_app_is_active():
            self.assertTrue(engine.running)
            self.assertTrue(app.running)
            app.tray.start_detached.assert_called_once_with()
            app.tray.stop.assert_not_called()
            self.assertIsNone(engine.serial_conn)
            original_workers = len(threads)
            reopened = Mock(is_open=True)
            with patch("engine.time.monotonic", return_value=106), \
                 patch("engine.serial.tools.list_ports.comports", return_value=[port("TEST_A")]), \
                 patch("engine.serial.Serial", return_value=reopened) as opened, \
                 patch("engine.time.sleep"):
                engine._attempt_reconnect()
                engine._attempt_reconnect()
            self.assertIs(engine.serial_conn, reopened)
            opened.assert_called_once()
            engine.send_initial_sync.assert_called_once_with()
            self.assertEqual(len(threads), original_workers)
            app.shutdown()

        listener.join.side_effect = while_app_is_active
        with patch("engine.serial.tools.list_ports.comports", return_value=[]), \
             patch("engine.time.monotonic", return_value=100), \
             patch("engine.threading.Thread", side_effect=thread), \
             patch("engine.keyboard.Listener", return_value=listener), \
             patch("engine.time.sleep"):
            self.assertEqual(app.run(), 0)

        names = [item.get("name") for item in threads]
        self.assertEqual(names.count("BongoDeskSerialReader"), 1)
        self.assertEqual(names.count("BongoDeskArtworkSender"), 1)
        engine.media_bridge.start.assert_called_once_with()
        engine.media_bridge.stop.assert_called_once_with()
        engine.start_system_monitor.assert_called_once_with()
        listener.start.assert_called_once_with()
        app.tray.stop.assert_called_once_with()

    def test_reconnect_respects_five_seconds_and_rejects_ambiguous_old_auto_port(self):
        engine = self.make_engine()
        engine.running = True
        engine.port = "TEST_A"  # Previously detected automatically, not explicit.
        with patch("engine.serial.tools.list_ports.comports", return_value=[port("TEST_A"), port("TEST_B")]) as scan, \
             patch("engine.serial.Serial") as opened, \
             patch("engine.time.monotonic", return_value=10):
            engine._attempt_reconnect()
            engine._attempt_reconnect()
        opened.assert_not_called()
        scan.assert_called_once_with()
        self.assertEqual(engine._next_reconnect_at, 15)
        with patch("engine.serial.tools.list_ports.comports", return_value=[port("TEST_A")]) as scan, \
             patch("engine.serial.Serial", return_value=Mock(is_open=True)) as opened, \
             patch("engine.time.monotonic", return_value=15), patch("engine.time.sleep"):
            engine._attempt_reconnect()
        opened.assert_called_once()
        engine.send_initial_sync.assert_called_once_with()

    def test_stop_during_failed_start_does_not_start_workers(self):
        engine = self.make_engine()

        def fail_after_exit():
            engine._stop_requested.set()
            return False

        engine.connect_serial = Mock(side_effect=fail_after_exit)
        with patch("engine.threading.Thread") as thread, patch("engine.keyboard.Listener") as listener:
            self.assertTrue(engine.start_monitoring())
        self.assertFalse(engine.running)
        thread.assert_not_called()
        listener.assert_not_called()
        engine.media_bridge.start.assert_not_called()
        engine.start_system_monitor.assert_not_called()


if __name__ == "__main__":
    unittest.main()

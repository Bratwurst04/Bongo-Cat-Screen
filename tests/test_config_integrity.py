"""Fault injection against new synthetic profiles, never a real user profile."""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "companion"))
from config import ConfigManager


class ConfigIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.manager = ConfigManager(self.folder.name)
        self.manager.config["connection"].update(com_port="TEST_PORT", baudrate=921600)
        self.manager.config["private_extension"] = {"text": "åäö", "future": [1, 2]}
        self.assertTrue(self.manager.save_config())
        self.original = self.manager.config_file.read_bytes()

    def test_write_flush_or_replace_failure_preserves_active_and_valid_backup(self):
        manager = self.manager
        for target in ("atomic_file.fsync", "atomic_file.os.replace"):
            with self.subTest(target=target):
                manager.config["display"]["show_wpm"] = False
                with patch(target, side_effect=OSError("synthetic disk failure")):
                    self.assertFalse(manager.save_config())
                self.assertEqual(manager.config_file.read_bytes(), self.original)
                restarted = ConfigManager(self.folder.name)
                self.assertEqual(restarted.get_connection_settings()["baudrate"], 921600)
                self.assertEqual(restarted.config["private_extension"], manager.config["private_extension"])
                self.assertEqual(list(Path(self.folder.name).glob(".*.tmp")), [])

    def test_failure_replacing_active_after_backup_is_written_is_safe(self):
        import atomic_file
        replace = atomic_file.os.replace

        def fail_active(source, destination):
            if Path(destination) == self.manager.config_file:
                raise OSError("synthetic active replace failure")
            return replace(source, destination)

        self.manager.config["display"]["show_wpm"] = False
        with patch("atomic_file.os.replace", side_effect=fail_active):
            self.assertFalse(self.manager.save_config())
        self.assertEqual(self.manager.config_file.read_bytes(), self.original)
        self.assertEqual(self.manager.backup_file.read_bytes(), self.original)
        self.assertEqual(list(Path(self.folder.name).glob(".*.tmp")), [])

    def test_partial_active_write_never_truncates_current_or_backup(self):
        import atomic_file
        fdopen = atomic_file.os.fdopen
        calls = 0

        class PartialStream:
            def __init__(self, stream): self.stream = stream
            def __enter__(self): return self
            def __exit__(self, *args): self.stream.close()
            def write(self, data):
                self.stream.write(data[:8])
                raise OSError("synthetic partial write")

        def fail_second_file(fd, mode):
            nonlocal calls
            calls += 1
            stream = fdopen(fd, mode)
            return PartialStream(stream) if calls == 2 else stream

        self.manager.config["display"]["show_wpm"] = False
        with patch("atomic_file.os.fdopen", side_effect=fail_second_file):
            self.assertFalse(self.manager.save_config())
        self.assertEqual(self.manager.config_file.read_bytes(), self.original)
        self.assertEqual(self.manager.backup_file.read_bytes(), self.original)
        self.assertEqual(list(Path(self.folder.name).glob(".*.tmp")), [])

    def test_corrupt_active_recovers_valid_backup_without_destroying_it(self):
        manager = self.manager
        manager.backup_file.write_bytes(self.original)
        for damaged in (b'{"connection":', b'[]', b'{"version":"invalid"}',
                        b'{"metadata":' + b'[' * 1500 + b'0' + b']' * 1500 + b'}'):
            with self.subTest(damaged=damaged):
                manager.config_file.write_bytes(damaged)
                restarted = ConfigManager(self.folder.name)
                self.assertEqual(restarted.config_file.read_bytes(), self.original)
                self.assertEqual(restarted.backup_file.read_bytes(), self.original)
                self.assertEqual(restarted.get_connection_settings()["com_port"], "TEST_PORT")
                self.assertEqual(restarted.config["private_extension"], manager.config["private_extension"])
                self.assertTrue(restarted.save_config())
                self.assertEqual(restarted.backup_file.read_bytes(), self.original)

    def test_missing_active_and_repair_failure_keep_backup_and_values(self):
        self.manager.backup_file.write_bytes(self.original)
        self.manager.config_file.unlink()
        with patch("config.atomic_write", side_effect=OSError("synthetic read-only disk")):
            restarted = ConfigManager(self.folder.name)
        self.assertEqual(restarted.get_connection_settings()["baudrate"], 921600)
        self.assertEqual(restarted.backup_file.read_bytes(), self.original)
        self.assertFalse(restarted.config_file.exists())

    def test_invalid_live_reload_retains_last_working_values(self):
        manager = self.manager
        expected = copy.deepcopy(manager.config)
        manager.config_file.write_bytes(b'corrupt')
        manager.backup_file.write_bytes(b'also corrupt')
        self.assertFalse(manager.load_config())
        self.assertEqual(manager.config, expected)

    def test_invalid_or_unserializable_memory_never_changes_disk(self):
        manager = self.manager
        for value in (float("nan"), object()):
            with self.subTest(value=type(value).__name__):
                manager.config["private_extension"]["invalid"] = value
                self.assertFalse(manager.save_config())
                self.assertEqual(manager.config_file.read_bytes(), self.original)

    def test_valid_save_is_utf8_and_preserves_unknown_fields(self):
        self.assertTrue(self.manager.save_config())
        saved = json.loads(self.manager.config_file.read_text(encoding="utf-8"))
        self.assertEqual(saved["private_extension"]["text"], "åäö")
        self.assertEqual(saved["connection"]["baudrate"], 921600)


if __name__ == "__main__":
    unittest.main()

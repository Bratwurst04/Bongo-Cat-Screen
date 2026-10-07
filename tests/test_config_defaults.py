"""Release baud defaults and preservation of an existing explicit profile."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "companion"))

from config import ConfigManager
from engine import BongoCatEngine


class ConfigDefaultsTests(unittest.TestCase):
    def test_fresh_profile_matches_packaged_baud_and_engine_fallback(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            manager = ConfigManager(folder)
            saved = json.loads(manager.config_file.read_text(encoding="utf-8"))
            packaged = json.loads((Path(__file__).resolve().parents[1] /
                                   "companion/default_config.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["connection"]["baudrate"], 230400)
            self.assertEqual(packaged["connection"]["baudrate"], 230400)
            with patch("engine.WindowsMediaBridge"):
                self.assertEqual(BongoCatEngine(manager).baudrate, 230400)
                self.assertEqual(BongoCatEngine().baudrate, 230400)
                manager.config["connection"].pop("baudrate")
                self.assertEqual(BongoCatEngine(manager).baudrate, 230400)

    def test_existing_explicit_115200_is_preserved_on_load_and_save(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            profile = Path(folder) / "config.json"
            existing = json.loads((Path(__file__).resolve().parents[1] /
                                   "companion/default_config.json").read_text(encoding="utf-8"))
            existing["connection"].update(baudrate=115200, com_port="COM9")
            existing["custom"] = {"keep": 42}
            original = (json.dumps(existing, indent=4) + "\n").encode("utf-8")
            profile.write_bytes(original)
            manager = ConfigManager(folder)
            self.assertEqual(profile.read_bytes(), original)
            self.assertEqual(manager.get_connection_settings()["baudrate"], 115200)
            with patch("engine.WindowsMediaBridge"):
                self.assertEqual(BongoCatEngine(manager).baudrate, 115200)
            manager.config["display"]["show_wpm"] = False
            self.assertTrue(manager.save_config())
            saved = json.loads(profile.read_text(encoding="utf-8"))
            self.assertEqual(saved["connection"]["baudrate"], 115200)
            self.assertEqual(saved["connection"]["com_port"], "COM9")
            self.assertEqual(saved["custom"], {"keep": 42})
            self.assertEqual(manager.backup_file.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()

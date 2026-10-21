"""New JSON guards preserve existing user values; isolated profile fixtures."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'companion'))
from config import ConfigManager
from api_budget import DEFAULTS, settings


class BudgetConfigTests(unittest.TestCase):
    def config(self):
        folder=tempfile.TemporaryDirectory(dir=ROOT);self.addCleanup(folder.cleanup)
        return ConfigManager(folder.name)

    def test_default_json_and_runtime_defaults_match(self):
        cfg=self.config()
        shipped=json.loads((ROOT/'companion/default_config.json').read_text())['spotify']
        self.assertEqual({k:shipped[k] for k in DEFAULTS},DEFAULTS)
        self.assertEqual({k:cfg.default_config['spotify'][k] for k in DEFAULTS},DEFAULTS)

    def test_old_explicit_values_and_tokens_are_not_migrated_on_load(self):
        cfg=self.config();original=copy.deepcopy(cfg.default_config)
        for key in DEFAULTS:original['spotify'].pop(key)
        original['spotify'].update(api_min_interval_seconds=1.5,api_initial_interval_seconds=2,
            api_idle_interval_seconds=15,api_only_poll_interval_seconds=45,custom_keep=17)
        cfg.config_file.write_text(json.dumps(original))
        token=cfg.config_dir/'spotify_tokens.json';token.write_bytes(b'{"refresh_token":"fixture","rate_limit_until":9999999999}')
        before_cfg=cfg.config_file.read_bytes();before_token=token.read_bytes()
        other=ConfigManager(str(cfg.config_dir))
        self.assertEqual(cfg.config_file.read_bytes(),before_cfg);self.assertEqual(token.read_bytes(),before_token)
        for key,value in original['spotify'].items():self.assertEqual(other.config['spotify'][key],value)
        self.assertTrue(other.validate_config(other.config))

    def test_config_and_policy_validation_agree(self):
        cfg=self.config()
        for key,value in [('api_budget_short_total',True),('api_budget_short_auto',24),
                          ('api_budget_day_idle_seconds',10),('api_budget_long_auto',8000),
                          ('api_budget_night_start_hour',8),('api_budget_timezone','invalid/fixture')]:
            candidate=copy.deepcopy(cfg.default_config);candidate['spotify'][key]=value
            self.assertFalse(cfg.validate_config(candidate))
            with self.assertRaises((ValueError,KeyError)):settings(candidate['spotify'])


if __name__=='__main__':unittest.main()

"""Content-free playback evidence; real worker/ledger with simulated HTTP only."""
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
import urllib.error
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'companion'))
from diagnostics import Diagnostics
from spotify_api import SpotifyApiBridge
from test_api_control_confirmation import Clock, Response
import test_manual_api_refresh as manual_tests


class PlaybackDiagnosticsTests(unittest.TestCase):
    def worker(self, **kwargs):
        fixture = manual_tests.ManualRefreshTests()
        self.addCleanup(fixture.doCleanups)
        with patch('diagnostics.diagnostics.event') as event:
            result = fixture.scenario(**kwargs)
        return result, event.call_args_list

    @staticmethod
    def events(calls, name):
        return [call.kwargs for call in calls if call.args == (name,)]

    def test_manual_empty_has_complete_read_only_lifecycle_and_auto_origin(self):
        result, calls = self.worker(empty=True, tap_after_empty=True, burst=True)
        refresh = self.events(calls, 'MEDIA_REFRESH')
        phases = [event.get('phase') for event in refresh]
        self.assertEqual(phases.count('accepted'), 1)
        self.assertEqual(phases.count('started'), 1)
        self.assertEqual(phases.count('completed'), 1)
        self.assertIn('coalesced', phases)
        self.assertEqual(next(event for event in refresh if event.get('phase') == 'completed')['outcome'], 'empty')
        snapshots = self.events(calls, 'MEDIA_API_SNAPSHOT')
        self.assertIn(dict(source='spotify_api', read_origin='manual', outcome='empty'), snapshots)
        self.assertIn(dict(source='spotify_api', read_origin='automatic', outcome='empty'), snapshots)
        self.assertEqual([call[0] for call in result['calls']], ['GET'] * 3)
        self.assertEqual(result['view']['reserved'], 0)
        self.assertEqual(len(self.events(calls, 'SPOTIFY_PLAYBACK_HTTP')), 3)

    def test_cooldown_gesture_tail_is_reported_without_an_extra_read(self):
        result, calls = self.worker(burst=True)
        phases = [event.get('phase') for event in self.events(calls, 'MEDIA_REFRESH')]
        self.assertIn('suppressed', phases)
        self.assertEqual(phases.count('started'), 1)
        self.assertEqual([call[0] for call in result['calls']], ['GET'] * 3)

    def test_manual_available_and_discarded_on_windows_return_are_distinct(self):
        for options, outcome in (({}, 'available'), ({'return_at': 'response'}, 'discarded')):
            with self.subTest(outcome=outcome):
                result, calls = self.worker(**options)
                completed = [event for event in self.events(calls, 'MEDIA_REFRESH')
                             if event.get('phase') == 'completed']
                self.assertEqual(len(completed), 1)
                self.assertEqual(completed[0]['outcome'], outcome)
                self.assertEqual(result['view']['reserved'], 0)

    def test_expiry_before_http_is_not_logged_as_started_or_completed(self):
        result, calls = self.worker(slow_token=4)
        phases = [event.get('phase') for event in self.events(calls, 'MEDIA_REFRESH')]
        self.assertIn('accepted', phases)
        self.assertIn('expired', phases)
        self.assertNotIn('started', phases)
        self.assertNotIn('completed', phases)
        self.assertFalse(result['manual_times'])
        self.assertEqual(result['view']['reserved'], 0)

    def test_401_attempts_share_one_manual_lifecycle_and_release_grant(self):
        result, calls = self.worker(error401=True)
        phases = [event.get('phase') for event in self.events(calls, 'MEDIA_REFRESH')]
        self.assertEqual(phases.count('accepted'), 1)
        self.assertEqual(phases.count('started'), 2)
        self.assertEqual(phases.count('completed'), 1)
        http = self.events(calls, 'SPOTIFY_PLAYBACK_HTTP')
        self.assertEqual([event['http_status'] for event in http], [200, 401, 200, 200])
        self.assertEqual(result['view']['reserved'], 0)

    def test_http_204_null_item_supported_types_and_invalid_json_are_distinct(self):
        cases = [
            (b'', 204, 'empty', 'empty', 'missing', 'missing'),
            (b'{"item":null,"currently_playing_type":"ad"}', 200, 'empty', 'object', 'null', 'ad'),
            (b'{}', 200, 'empty', 'object', 'missing', 'missing'),
            (b'{"item":{"id":"secret-id","type":"episode","name":"private-title"}}',
             200, 'available', 'object', 'present', 'episode'),
            (b'{"item":{"id":"secret-id","type":"track"}}',
             200, 'available', 'object', 'present', 'track'),
            (b'{"item":null,"currently_playing_type":"private-type"}',
             200, 'empty', 'object', 'null', 'unknown'),
            (b'["private-body"]', 200, 'invalid', 'other', 'missing', 'missing'),
            (b'private-body', 200, 'invalid', 'invalid', None, None),
            (b'\xff', 200, 'invalid', 'invalid', None, None),
        ]
        for payload, status, outcome, shape, item, kind in cases:
            with self.subTest(status=status, shape=shape, item=item, kind=kind):
                with tempfile.TemporaryDirectory(dir=ROOT) as folder:
                    clock = Clock()
                    with patch('time.time', new=lambda: clock.now), patch('time.monotonic', new=lambda: clock.mono):
                        api = SpotifyApiBridge('fixture', Path(folder) / 'tokens.json')
                        api._tokens.update(access_token='fixture', refresh_token='fixture', expires_at=clock.now + 86400)
                        with patch('urllib.request.urlopen', return_value=Response(payload, status)) as http, \
                             patch('diagnostics.diagnostics.event') as event:
                            if shape == 'invalid':
                                with self.assertRaises((json.JSONDecodeError, UnicodeDecodeError)):
                                    api.get_playback()
                            elif shape == 'other':
                                with self.assertRaises(AttributeError):
                                    api.get_playback()
                            else:
                                api.get_playback()
                        self.assertEqual(http.call_count, 1)
                        self.assertEqual(api._budget.view()['long_used'], 1)
                        http_event = self.events(event.call_args_list, 'SPOTIFY_PLAYBACK_HTTP')
                        self.assertEqual(http_event[0]['http_status'], status)
                        shape_event = self.events(event.call_args_list, 'SPOTIFY_PLAYBACK_SHAPE')[0]
                        self.assertEqual(shape_event['outcome'], outcome)
                        self.assertEqual(shape_event['body_shape'], shape)
                        if item is not None:
                            self.assertEqual(shape_event['item_state'], item)
                            self.assertEqual(shape_event['playback_type'], kind)
                        self.assertNotIn('private', repr(event.call_args_list))
                        self.assertNotIn('secret-id', repr(event.call_args_list))

    def test_diagnostic_allowlist_rejects_content_even_in_new_fields(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            diag = Diagnostics(Path(folder) / 'logs')
            diag.start()
            self.addCleanup(diag._logger.removeHandler, diag._handler)
            diag.event('SPOTIFY_PLAYBACK_SHAPE', source='spotify_api', body_shape='object',
                       item_state='null', playback_type='ad', outcome='empty',
                       request_kind='playback_poll', title='private', body='private',
                       token='private', headers='private', url='private', device_id='private')
            diag.event('MEDIA_REFRESH', phase='completed', read_origin='manual', outcome='empty')
            diag.event('MEDIA_API_SNAPSHOT', read_origin='automatic', outcome='available')
            diag.event('SPOTIFY_PLAYBACK_SHAPE', body_shape='private', item_state='private',
                       playback_type='private', outcome='private', phase='private', read_origin='private')
            diag._handler.flush()
            log = (Path(folder) / 'logs/events.log').read_text(encoding='utf-8')
            self.assertNotIn('private', log)
            self.assertIn('playback_type=ad', log)
            self.assertIn('phase=completed read_origin=manual outcome=empty', log)
            self.assertIn('read_origin=automatic outcome=available', log)
            diag._handler.close()

    def test_request_trace_and_budget_match_installed_source_without_diagnostics(self):
        frozen = ROOT / 'build/record-flip-2026-10-15-r2/source-frozen/companion'
        modules = {}
        for name in ('spotify_api', 'media_bridge'):
            from frozen_source import load_module
            module = load_module('waiting_baseline_' + name, frozen / (name + '.py'), optional_archive=True)
            modules[name] = module
        for name in ('SpotifyPacingError', 'SpotifyRateLimitError', 'SpotifyApiError', 'SpotifyBudgetError'):
            setattr(modules['media_bridge'], name, getattr(modules['spotify_api'], name))
        for options in ({}, {'empty': True, 'tap_after_empty': True}, {'burst': True},
                        {'slow_token': 4}, {'block': 'retry'}, {'spacing': True},
                        {'error401': True}, {'read_error': 'json'}, {'paused': True, 'play_after': True}):
            with self.subTest(options=options):
                current, _ = self.worker(**options)
                with patch.object(manual_tests, 'SpotifyApiBridge', modules['spotify_api'].SpotifyApiBridge), \
                     patch.object(manual_tests, 'WindowsMediaBridge', modules['media_bridge'].WindowsMediaBridge):
                    baseline, _ = self.worker(**options)
                self.assertEqual(current['calls'], baseline['calls'])
                self.assertEqual(current['manual_times'], baseline['manual_times'])
                for key in ('long_used', 'long_auto_used', 'reserved', 'retry_remaining_seconds'):
                    self.assertEqual(current['view'][key], baseline['view'][key], key)
                # Snapshot classes belong to different module identities.
                self.assertEqual([(t, vars(s), a) for t, s, a in current['published']],
                                 [(t, vars(s), a) for t, s, a in baseline['published']])


if __name__ == '__main__':
    unittest.main()

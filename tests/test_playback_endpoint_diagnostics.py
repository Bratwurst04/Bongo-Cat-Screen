"""One automatic A-B-A opportunity through the real worker and file ledger."""
import asyncio
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'companion'), str(ROOT / 'tests')]
from api_budget import ApiBudget, BudgetWait, _new_state
from diagnostics import Diagnostics
# The retired B diagnostic is checked against its immutable 3EDD snapshot.
from frozen_source import load_module
FROZEN = ROOT / 'build/playback-endpoint-diagnostics-2026-10-16/source-frozen/companion'
_api = load_module('endpoint_frozen_api', FROZEN / 'spotify_api.py', optional_archive=True)
with patch.dict(sys.modules, {'spotify_api': _api}):
    _media = load_module('endpoint_frozen_media', FROZEN / 'media_bridge.py', optional_archive=True)
WindowsMediaBridge, MediaSnapshot = _media.WindowsMediaBridge, _media.MediaSnapshot
SpotifyApiBridge = _api.SpotifyApiBridge
SpotifyBudgetError, SpotifyPacingError = _api.SpotifyBudgetError, _api.SpotifyPacingError
Diagnostics = load_module('endpoint_frozen_diagnostics', FROZEN / 'diagnostics.py', optional_archive=True).Diagnostics
from test_api_control_confirmation import Clock, Response


class EndpointDiagnosticTests(unittest.TestCase):
    def worker(self, script, *, manual_at=None, initial_manual=False, control=False,
               windows_between=False, expire=False, slow_token=False, takeover_token=False,
               manual_token=False, idle15=False):
        folder = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        clock = Clock()
        start = clock.mono
        state = _new_state(clock.now, clock.mono)
        if idle15:state['warm_until'] = 0
        (root / 'budget.json').write_text(json.dumps(state))
        (root / 'tokens.json').write_text(json.dumps(dict(access_token='fixture',
            refresh_token='fixture', expires_at=clock.now + 86400,
            adaptive_interval_seconds=.5, adaptive_safe_interval_seconds=.5)))
        calls, published, errors, oauth, before_b, after_b = [], [], [], [], [], []
        windows = False
        queued = initial_manual
        expired = delayed = False
        index = 0
        api = bridge = None
        real_sleep = asyncio.sleep
        session = Mock(source_app_user_model_id='Spotify.exe')
        data = dict(item=dict(id='private-id', name='private-title', duration_ms=180000,
                             type='track', album=dict(images=[])),
                    is_playing=True, progress_ms=5000)

        def http(request, **kwargs):
            nonlocal index
            if '/api/token' in request.full_url:
                oauth.append(clock.mono)
                clock.advance(.12)
                return Response(b'{"access_token":"refreshed-fixture","expires_in":86400}')
            variant = ('B' if '/currently-playing?' in request.full_url else
                       'A' if request.method == 'GET' else 'control')
            calls.append((variant, request.method, clock.mono))
            if request.method != 'GET':
                clock.advance(.12)
                return Response(b'', 204)
            expected, status, payload = script[index]
            self.assertEqual(variant, expected)
            index += 1
            if variant == 'B':
                before_b.append((api._last_is_playing, bridge._api_only_idle,
                                 bridge._last_api_snapshot_at, len(published)))
            clock.advance(.12)
            if index == len(script) and not takeover_token:bridge._stop.set()
            if status == 0:raise urllib.error.URLError('private-error')
            if status >= 400:
                raise urllib.error.HTTPError('fixture', status, 'private-error',
                    {'Retry-After': '10'}, io.BytesIO(b'private-body'))
            body = b'' if status == 204 else (payload if isinstance(payload, bytes) else
                                              json.dumps(data if payload is None else payload).encode())
            return Response(body, status)

        def publish(snapshot, artwork):
            published.append((snapshot, artwork))
            if takeover_token and snapshot.source == 'SPOTIFY':bridge._stop.set()

        async def sleep(seconds):
            nonlocal windows, queued, expired
            if before_b and not after_b and bridge._endpoint_probe_deadline == 0:
                after_b.append((api._last_is_playing, bridge._api_only_idle,
                                bridge._last_api_snapshot_at, len(published)))
            clock.advance(seconds)
            elapsed = clock.mono - start
            if windows_between:windows = 5 <= elapsed < 35
            if manual_at is not None and not queued and elapsed >= manual_at:
                queued = True
                self.assertTrue(bridge.control('PLAY_PAUSE'))
            if expire and not expired and bridge._endpoint_probe_deadline:
                expired = True
                clock.advance(91)
            if elapsed > 250:bridge._stop.set()
            await real_sleep(0)

        with patch('time.time', new=lambda: clock.now), patch('time.monotonic', new=lambda: clock.mono), \
             patch('urllib.request.urlopen', new=http), patch('media_bridge.asyncio.sleep', new=sleep), \
             patch('diagnostics.diagnostics.event') as event, \
             patch('media_bridge.GlobalSystemMediaTransportControlsSessionManager.request_async',
                   new_callable=AsyncMock, return_value=Mock(get_sessions=lambda: [session] if windows else [])):
            budget = ApiBudget(root / 'budget.json', wall=lambda: clock.now, monotonic=lambda: clock.mono)
            api = SpotifyApiBridge('fixture', root / 'tokens.json', budget=budget)
            bridge = WindowsMediaBridge(on_update=publish, on_error=errors.append)
            bridge._spotify = api
            bridge._try_api_artwork = AsyncMock(return_value=None)
            bridge._windows_api_artwork_due = Mock(return_value=False)
            bridge._read_session = AsyncMock(return_value=(MediaSnapshot(
                available=True, source='SPOTIFY', track_key='windows', title='Windows fixture'), None))
            if initial_manual or control:
                bridge._source_mode = bridge._current_source = 'spotify_api'
                bridge._source_epoch = bridge._api_snapshot_epoch = 1
                bridge._api_waiting = initial_manual
                bridge._next_api_poll_at = clock.mono + 60
                bridge._last_snapshot = MediaSnapshot(available=control, source='SPOTIFY API', track_key='fixture')
                self.assertTrue(bridge.control('PLAY_PAUSE' if initial_manual else 'NEXT'))
            token = api._access_token
            def prepare_token():
                nonlocal delayed, windows
                if bridge._endpoint_probe_deadline and not delayed:
                    delayed = True
                    if slow_token:clock.advance(91)
                    if takeover_token:windows = True
                    if manual_token:self.assertTrue(bridge.control('PLAY_PAUSE'))
                return token()
            api._access_token = prepare_token
            api.begin_operation = Mock(wraps=api.begin_operation)
            asyncio.run(bridge._run())
            view = budget.view(idle=bridge._api_only_idle)
        self.assertEqual(index, len(script), 'Worker did not finish the prescribed opportunities')
        return dict(calls=calls, published=published, errors=errors, oauth=oauth,
                    before_b=before_b, after_b=after_b, bridge=bridge, api=api,
                    view=view, events=event.call_args_list)

    def test_a200_never_arms_or_sends_b(self):
        r = self.worker([('A', 200, None)] * 3)
        self.assertEqual([c[0] for c in r['calls']], ['A'] * 3)
        self.assertFalse(r['bridge']._endpoint_probe_used)
        self.assertTrue(all(b[2] - a[2] >= 5 for a, b in zip(r['calls'], r['calls'][1:])))

    def test_a204_b200_a204_uses_three_slots_and_never_publishes_b(self):
        r = self.worker([('A', 204, None), ('B', 200, None), ('A', 204, None)])
        self.assertEqual([c[0] for c in r['calls']], ['A', 'B', 'A'])
        self.assertEqual(r['before_b'], r['after_b'])
        self.assertFalse(any(s.available for s, a in r['published']))
        self.assertFalse(r['api']._last_is_playing)
        self.assertTrue(r['bridge']._api_only_idle)
        self.assertEqual(r['api']._last_art_key, '')
        self.assertEqual(r['api'].primary_playback_revision, 0)
        self.assertEqual(r['view']['interval_seconds'], 30)
        self.assertEqual((r['view']['long_used'], r['view']['long_auto_used'], r['view']['reserved']), (3, 3, 0))
        r['api'].begin_operation.assert_not_called()
        r['bridge']._try_api_artwork.assert_not_called()
        self.assertTrue(all(b[2] - a[2] >= 30 for a, b in zip(r['calls'], r['calls'][1:])))
        self.assertNotIn('private', repr(r['events']))

    def test_empty_b_does_not_rearm_on_later_empty_a(self):
        r = self.worker([('A', 204, None), ('B', 204, None)] + [('A', 204, None)] * 3)
        self.assertEqual([c[0] for c in r['calls']], ['A', 'B', 'A', 'A', 'A'])
        self.assertEqual(r['view']['long_auto_used'], 5)

    def test_b403_and_bad_json_return_to_a_with_safe_existing_error_policy(self):
        for status, body in ((403, None), (200, b'private-body')):
            with self.subTest(status=status):
                r = self.worker([('A', 204, None), ('B', status, body), ('A', 204, None)])
                self.assertTrue(r['errors'])
                self.assertNotIn('private', repr(r['errors']) + repr(r['events']))
                self.assertGreaterEqual(r['calls'][2][2] - r['calls'][1][2], 60)
                self.assertEqual(r['view']['long_auto_used'], 3)

    def test_b401_retry_is_automatic_paced_bounded_and_not_a_new_grant(self):
        r = self.worker([('A', 204, None), ('B', 401, None), ('B', 200, None), ('A', 204, None)])
        self.assertEqual(len(r['oauth']), 1)
        self.assertEqual([c[0] for c in r['calls']], ['A', 'B', 'B', 'A'])
        self.assertTrue(all(b[2] - a[2] >= 30 for a, b in zip(r['calls'], r['calls'][1:])))
        self.assertEqual(r['view']['long_auto_used'], 4)
        r['api'].begin_operation.assert_not_called()

    def test_b403_or_transport_error_at_idle15_cannot_retry_b_inside_ttl(self):
        for status in (403, 0):
            with self.subTest(status=status):
                r = self.worker([('A', 204, None), ('B', status, None), ('A', 204, None)], idle15=True)
                self.assertEqual([c[0] for c in r['calls']], ['A', 'B', 'A'])
                self.assertGreaterEqual(r['calls'][1][2] - r['calls'][0][2], 15)
                self.assertGreaterEqual(r['calls'][2][2] - r['calls'][1][2], 60)
                self.assertLess(r['calls'][2][2] - r['calls'][0][2], 90)
                self.assertNotIn('private', repr(r['events']) + repr(r['errors']))

    def test_b429_keeps_authoritative_retry_and_returns_to_a(self):
        r = self.worker([('A', 204, None), ('B', 429, None), ('A', 204, None)])
        self.assertEqual([c[0] for c in r['calls']], ['A', 'B', 'A'])
        self.assertGreaterEqual(r['calls'][2][2] - r['calls'][1][2], 10)
        self.assertNotIn('private', repr(r['events']) + repr(r['errors']))

    def test_repeated_b401_cannot_restart_a_third_b_attempt(self):
        r = self.worker([('A', 204, None), ('B', 401, None), ('B', 401, None), ('A', 204, None)])
        self.assertEqual(len(r['oauth']), 1)
        self.assertEqual([c[0] for c in r['calls']].count('B'), 2)
        self.assertFalse(r['bridge']._endpoint_probe_deadline)

    def test_manual_primary_recovery_cancels_pending_b(self):
        r = self.worker([('A', 204, None), ('A', 200, None), ('A', 200, None)], manual_at=5)
        self.assertEqual([c[0] for c in r['calls']], ['A'] * 3)
        self.assertTrue(r['bridge']._endpoint_probe_used)
        self.assertFalse(r['bridge']._endpoint_probe_deadline)
        self.assertEqual((r['view']['long_used'], r['view']['long_auto_used'], r['view']['reserved']), (3, 2, 0))

    def test_manual_and_confirmation_empty_reads_do_not_arm_b(self):
        for initial_manual, control in ((True, False), (False, True)):
            with self.subTest(manual=initial_manual):
                r = self.worker([('A', 204, None)], initial_manual=initial_manual, control=control)
                self.assertFalse(r['bridge']._endpoint_probe_used)
                self.assertNotIn('B', [c[0] for c in r['calls']])
                self.assertEqual(r['view']['reserved'], 0)

    def test_expiry_and_windows_source_switch_cancel_without_late_b(self):
        for options in ({'expire': True}, {'windows_between': True}, {'slow_token': True}):
            with self.subTest(options=options):
                r = self.worker([('A', 204, None), ('A', 204, None)], **options)
                self.assertEqual([c[0] for c in r['calls']], ['A', 'A'])
                self.assertEqual(r['view']['long_auto_used'], 2)
                self.assertFalse(r['bridge']._endpoint_probe_deadline)

    def test_final_guard_handles_windows_or_manual_work_arriving_during_token_preparation(self):
        r = self.worker([('A', 204, None)], takeover_token=True)
        self.assertEqual([c[0] for c in r['calls']], ['A'])
        self.assertEqual(r['bridge']._source_mode, 'windows_spotify')
        self.assertEqual(r['view']['long_used'], 1)
        r = self.worker([('A', 204, None), ('A', 200, None)], manual_token=True)
        self.assertEqual([c[0] for c in r['calls']], ['A', 'A'])
        self.assertTrue(r['published'][-1][0].available)
        self.assertEqual((r['view']['long_used'], r['view']['long_auto_used'], r['view']['reserved']), (2, 1, 0))

    def test_client_guards_refuse_http_and_preserve_conservative_io_accounting(self):
        for block in ('start_guard', 'profile', 'spacing', 'retry', 'clock', 'io'):
            with self.subTest(block=block), tempfile.TemporaryDirectory(dir=ROOT) as folder:
                clock = Clock()
                root = Path(folder)
                with patch('time.time', new=lambda: clock.now), patch('time.monotonic', new=lambda: clock.mono):
                    budget = ApiBudget(root / 'budget.json', wall=lambda: clock.now, monotonic=lambda: clock.mono)
                    api = SpotifyApiBridge('fixture', root / 'tokens.json', budget=budget)
                    api._tokens.update(access_token='fixture', refresh_token='fixture', expires_at=clock.now + 86400)
                    def guard(state):
                        now = state['logical']
                        if block == 'profile':state['last_auto'] = now
                        if block == 'spacing':state['last_start'] = now
                        if block == 'retry':state['retry_until'] = now + 60
                        if block == 'clock':state['clock_guard'] = now + 60
                    budget.store.update(budget._factory, guard)
                    with patch('urllib.request.urlopen') as http:
                        if block == 'io':
                            with patch.object(budget.store, 'save', side_effect=BudgetWait(60, 'history_io')):
                                with self.assertRaises(SpotifyPacingError):
                                    api.diagnose_playback(lambda: True, lambda: True)
                        else:
                            with self.assertRaises((SpotifyPacingError, _api.SpotifyRateLimitError)):
                                api.diagnose_playback(lambda: block != 'start_guard', lambda: True)
                        http.assert_not_called()
                    # A failed durable claim keeps its existing conservative
                    # pending cost; this diagnostic must not erase that guard.
                    self.assertEqual(budget.view()['long_used'], 1 if block == 'io' else 0)
                    self.assertEqual(budget.view()['reserved'], 0)

    def test_windows_artwork_fallback_stays_on_primary_endpoint(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            clock = Clock()
            with patch('time.time', new=lambda: clock.now), patch('time.monotonic', new=lambda: clock.mono):
                api = SpotifyApiBridge('fixture', Path(folder) / 'tokens.json')
                api._tokens.update(access_token='fixture', refresh_token='fixture', expires_at=clock.now + 86400)
                with patch('urllib.request.urlopen', return_value=Response(b'', 204)) as http:
                    self.assertEqual(api.get_playback(artwork_fallback=True), (None, None))
                self.assertEqual(http.call_args.args[0].full_url, 'https://api.spotify.com/v1/me/player?additional_types=track%2Cepisode')

    def test_available_primary_art_response_invalidates_pending_b_even_outside_worker(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            clock = Clock()
            with patch('time.time', new=lambda: clock.now), patch('time.monotonic', new=lambda: clock.mono):
                api = SpotifyApiBridge('fixture', Path(folder) / 'tokens.json')
                api._tokens.update(access_token='fixture', refresh_token='fixture', expires_at=clock.now + 86400)
                bridge = WindowsMediaBridge(on_update=Mock())
                bridge._spotify = api
                bridge._source_mode = 'spotify_api'
                bridge._source_epoch = 1
                payload = b'{"item":{"id":"fixture","name":"fixture","duration_ms":180000},"is_playing":true}'
                with patch('urllib.request.urlopen', side_effect=[Response(b'', 204), Response(payload)]) as http:
                    self.assertEqual(api.get_playback(), (None, None))
                    bridge._observe_primary_playback(None, automatic=True)
                    self.assertTrue(bridge._endpoint_probe_pending())
                    clock.advance(30)
                    api.get_playback(artwork_fallback=True)
                    self.assertFalse(bridge._endpoint_probe_pending())
                    self.assertEqual(http.call_count, 2)
                self.assertEqual(api.primary_playback_revision, 1)
                self.assertTrue(bridge._endpoint_probe_used)

    def test_endpoint_log_enum_cannot_accept_response_content(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            diag = Diagnostics(Path(folder) / 'logs')
            diag.start()
            try:
                for endpoint in ('playback_state', 'currently_playing', 'private-url'):
                    diag.event('SPOTIFY_PLAYBACK_HTTP', endpoint=endpoint, http_status=204,
                               title='private-title', token='private-token', body='private-body')
                diag._handler.flush()
                log = (Path(folder) / 'logs/events.log').read_text(encoding='utf-8')
                self.assertIn('endpoint=playback_state', log)
                self.assertIn('endpoint=currently_playing', log)
                self.assertNotIn('private', log)
            finally:
                diag._logger.removeHandler(diag._handler)
                diag._handler.close()


if __name__ == '__main__':
    unittest.main()

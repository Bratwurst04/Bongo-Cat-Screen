"""One automatic A-devices-A opportunity through the real worker and file ledger."""
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
from media_bridge import WindowsMediaBridge, MediaSnapshot
from spotify_api import SpotifyApiBridge, SpotifyBudgetError, SpotifyPacingError
from test_api_control_confirmation import Clock, Response


class DevicesDiagnosticTests(unittest.TestCase):
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
        calls, published, errors, oauth, before_devices, after_devices = [], [], [], [], [], []
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
            variant = ('devices' if '/devices' in request.full_url else
                       'A' if request.method == 'GET' else 'control')
            calls.append((variant, request.method, clock.mono))
            if request.method != 'GET':
                clock.advance(.12)
                return Response(b'', 204)
            expected, status, payload = script[index]
            self.assertEqual(variant, expected)
            index += 1
            if variant == 'devices':
                before_devices.append((api._last_is_playing, bridge._api_only_idle,
                                 bridge._last_api_snapshot_at, len(published)))
            clock.advance(.12)
            if index == len(script) and not takeover_token:bridge._stop.set()
            if status == 0:raise urllib.error.URLError('private-error')
            if status >= 400:
                raise urllib.error.HTTPError('fixture', status, 'private-error',
                    {'Retry-After': '10'}, io.BytesIO(b'private-body'))
            body = b'' if status == 204 else (payload if isinstance(payload, bytes) else
                                              json.dumps(({'devices': []} if variant == 'devices' else data) if payload is None else payload).encode())
            return Response(body, status)

        def publish(snapshot, artwork):
            published.append((snapshot, artwork))
            if takeover_token and snapshot.source == 'SPOTIFY':bridge._stop.set()

        async def sleep(seconds):
            nonlocal windows, queued, expired
            if before_devices and not after_devices and bridge._devices_probe_deadline == 0:
                after_devices.append((api._last_is_playing, bridge._api_only_idle,
                                bridge._last_api_snapshot_at, len(published)))
            clock.advance(seconds)
            elapsed = clock.mono - start
            if windows_between:windows = 5 <= elapsed < 35
            if manual_at is not None and not queued and elapsed >= manual_at:
                queued = True
                self.assertTrue(bridge.control('PLAY_PAUSE'))
            if expire and not expired and bridge._devices_probe_deadline:
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
                if bridge._devices_probe_deadline and not delayed:
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
                    before_devices=before_devices, after_devices=after_devices, bridge=bridge, api=api,
                    view=view, events=event.call_args_list)

    def test_active_a_never_arms_devices(self):
        r = self.worker([('A', 200, None)] * 3)
        self.assertEqual([c[0] for c in r['calls']], ['A'] * 3)
        self.assertFalse(r['bridge']._devices_probe_used)

    def test_devices_replaces_one_due_slot_and_preserves_primary(self):
        device = dict(type='Smartphone', is_active=True, is_private_session=False,
                      is_restricted=False, name='SECRET-name', id='SECRET-id')
        r = self.worker([('A', 204, None), ('devices', 200, {'devices': [device]}),
                         ('A', 204, None)])
        self.assertEqual([c[0] for c in r['calls']], ['A', 'devices', 'A'])
        self.assertEqual(r['before_devices'], r['after_devices'])
        self.assertTrue(all(b[2] - a[2] >= 30 for a, b in zip(r['calls'], r['calls'][1:])))
        self.assertEqual((r['view']['long_used'], r['view']['long_auto_used'], r['view']['reserved']), (3, 3, 0))
        self.assertFalse(r['api']._last_is_playing)
        self.assertTrue(r['bridge']._api_only_idle)
        self.assertEqual(r['api'].primary_playback_revision, 0)
        self.assertEqual(r['api']._last_art_key, '')
        r['api'].begin_operation.assert_not_called()
        r['bridge']._try_api_artwork.assert_not_called()
        body = [e.kwargs for e in r['events'] if e.args[0] == 'SPOTIFY_DEVICES_BODY'][0]
        self.assertEqual(body['devices_body'], 'valid')
        self.assertEqual((body['devices_total'], body['devices_active_smartphones']), (1, 1))
        self.assertNotIn('SECRET', repr(r['events']))
        self.assertFalse(any(s.available for s, _ in r['published']))

    def test_only_one_devices_even_after_later_empty_a(self):
        r = self.worker([('A', 204, None), ('devices', 200, {'devices': []})] + [('A', 204, None)] * 3)
        self.assertEqual([c[0] for c in r['calls']], ['A', 'devices', 'A', 'A', 'A'])

    def test_401_has_exactly_one_devices_get_and_no_refresh_retry(self):
        r = self.worker([('A', 204, None), ('devices', 401, None), ('A', 204, None)])
        self.assertEqual([c[0] for c in r['calls']], ['A', 'devices', 'A'])
        self.assertEqual(r['oauth'], [])
        self.assertEqual(r['before_devices'], r['after_devices'])
        statuses = [e.kwargs['http_status'] for e in r['events'] if e.args[0] == 'SPOTIFY_DEVICES_HTTP']
        self.assertEqual(statuses, [401])
        self.assertEqual(r['errors'], [])

    def test_error_responses_preserve_primary_and_return_to_normal_a(self):
        for status, payload in ((403, None), (0, None), (200, b'SECRET-malformed'),
                                (204, None), (200, {'devices': 'SECRET-invalid'})):
            with self.subTest(status=status, payload=payload):
                r = self.worker([('A', 204, None), ('devices', status, payload), ('A', 204, None)])
                self.assertEqual([c[0] for c in r['calls']], ['A', 'devices', 'A'])
                self.assertEqual(r['before_devices'], r['after_devices'])
                self.assertEqual(r['errors'], [])
                self.assertGreaterEqual(r['calls'][2][2] - r['calls'][1][2], 30)
                self.assertNotIn('SECRET', repr(r['events']))
                self.assertNotIn('private-body', repr(r['events']))

    def test_429_keeps_global_guard_without_primary_invalidation(self):
        r = self.worker([('A', 204, None), ('devices', 429, None), ('A', 204, None)])
        self.assertEqual(r['before_devices'], r['after_devices'])
        self.assertEqual([c[0] for c in r['calls']], ['A', 'devices', 'A'])
        self.assertGreaterEqual(r['calls'][2][2] - r['calls'][1][2], 30)
        self.assertEqual([e.kwargs['http_status'] for e in r['events']
                          if e.args[0] == 'SPOTIFY_DEVICES_HTTP'], [429])
        self.assertEqual(r['api']._tokens['adaptive_total_429'], 1)

    def test_manual_empty_read_cancels_instead_of_deferring_devices(self):
        r = self.worker([('A', 204, None)] * 3, manual_at=5)
        self.assertEqual([c[0] for c in r['calls']], ['A'] * 3)
        self.assertTrue(r['bridge']._devices_probe_used)
        self.assertFalse(r['bridge']._devices_probe_deadline)

    def test_manual_and_confirmation_reads_never_arm_devices(self):
        for initial_manual, control in ((True, False), (False, True)):
            r = self.worker([('A', 204, None)], initial_manual=initial_manual, control=control)
            self.assertFalse(r['bridge']._devices_probe_used)
            self.assertEqual(r['view']['reserved'], 0)

    def test_ttl_windows_and_slow_token_cancel_before_http(self):
        for options in ({'expire': True}, {'windows_between': True}, {'slow_token': True}):
            r = self.worker([('A', 204, None), ('A', 204, None)], **options)
            self.assertEqual([c[0] for c in r['calls']], ['A', 'A'])
            self.assertFalse(r['bridge']._devices_probe_deadline)

    def test_final_guard_prioritizes_source_and_manual_work(self):
        r = self.worker([('A', 204, None)], takeover_token=True)
        self.assertEqual([c[0] for c in r['calls']], ['A'])
        self.assertEqual(r['bridge']._source_mode, 'windows_spotify')
        r = self.worker([('A', 204, None), ('A', 200, None)], manual_token=True)
        self.assertEqual([c[0] for c in r['calls']], ['A', 'A'])
        self.assertTrue(r['published'][-1][0].available)
        self.assertEqual(r['view']['reserved'], 0)

    def test_pending_commands_confirmation_and_epoch_cancel_opportunity(self):
        for work in ('_pending_spotify_command', '_confirmation_operation', '_pending_control_operation',
                     '_manual_refresh', 'queue', 'epoch'):
            bridge = WindowsMediaBridge(on_update=Mock())
            bridge._spotify = Mock(primary_playback_revision=0)
            bridge._source_mode = 'spotify_api'
            bridge._source_epoch = 1
            bridge._observe_primary_playback(None, automatic=True)
            if work == 'queue': bridge._commands.put(object())
            elif work == 'epoch': bridge._source_epoch += 1
            else: setattr(bridge, work, object())
            self.assertFalse(bridge._start_devices_probe(Mock()))
            self.assertFalse(bridge._devices_probe_deadline)
            self.assertEqual(bridge._devices_probe_attempts, 0)
            self.assertTrue(bridge._devices_probe_used)

    def test_primary_art_recovery_invalidates_probe(self):
        bridge = WindowsMediaBridge(on_update=Mock())
        bridge._spotify = Mock(primary_playback_revision=1)
        bridge._source_mode = 'spotify_api'
        bridge._observe_primary_playback(None, automatic=True)
        bridge._spotify.primary_playback_revision += 1
        self.assertFalse(bridge._devices_probe_pending())
        self.assertFalse(bridge._devices_probe_deadline)

    def test_client_guards_prevent_http_and_preserve_pending_cost(self):
        for block in ('start_guard', 'profile', 'spacing', 'retry', 'clock', 'io'):
            with self.subTest(block=block), tempfile.TemporaryDirectory(dir=ROOT) as folder:
                clock = Clock(); root = Path(folder)
                with patch('time.time', new=lambda: clock.now), patch('time.monotonic', new=lambda: clock.mono):
                    budget = ApiBudget(root / 'budget.json', wall=lambda: clock.now, monotonic=lambda: clock.mono)
                    api = SpotifyApiBridge('fixture', root / 'tokens.json', budget=budget)
                    api._tokens.update(access_token='fixture', refresh_token='fixture', expires_at=clock.now + 86400)
                    def guard(state):
                        now = state['logical']
                        if block == 'profile': state['last_auto'] = now
                        if block == 'spacing': state['last_start'] = now
                        if block == 'retry': state['retry_until'] = now + 60
                        if block == 'clock': state['clock_guard'] = now + 60
                    budget.store.update(budget._factory, guard)
                    with patch('urllib.request.urlopen') as http:
                        if block == 'io':
                            with patch.object(budget.store, 'save', side_effect=BudgetWait(60, 'history_io')):
                                with self.assertRaises(SpotifyPacingError):
                                    api.diagnose_devices(lambda: True)
                        elif block in ('retry',):
                            self.assertFalse(api.diagnose_devices(lambda: True))
                        else:
                            with self.assertRaises(SpotifyPacingError):
                                api.diagnose_devices(lambda: block != 'start_guard')
                        http.assert_not_called()
                    self.assertEqual(budget.view()['long_used'], 1 if block == 'io' else 0)

    def test_valid_empty_list_and_counts_are_distinct_from_malformed(self):
        empty = SpotifyApiBridge._devices_summary({'devices': []})
        self.assertEqual(set(empty.values()), {0})
        device = dict(type='SMARTPHONE', is_active=True, is_private_session=True, is_restricted=False)
        counts = SpotifyApiBridge._devices_summary({'devices': [device, {**device, 'type': 'computer'}]})
        self.assertEqual(list(counts.values()), [2, 2, 1, 1, 2, 0])
        for body in (None, [], {}, {'devices': None}, {'devices': [None]}, {'devices': [device, {}]},
                     *({'devices': [{**device, key: value}]} for key, value in
                       [('type', 3), ('is_active', 1), ('is_private_session', 'SECRET'), ('is_restricted', [])])):
            self.assertIsNone(SpotifyApiBridge._devices_summary(body))

    def test_actual_formatter_hides_hostile_body_fields_and_types(self):
        class Evil(str):
            def __str__(self): return 'SECRET-string-subclass'
        class EvilInt(int):
            def __str__(self): return 'SECRET-int-subclass'
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            diag = Diagnostics(Path(folder) / 'logs'); diag.start()
            try:
                diag.event('SPOTIFY_DEVICES_BODY', endpoint='available_devices', devices_body='valid',
                           devices_total=0, devices_active=True, devices_private=-1,
                           devices_smartphones=1.5, devices_restricted=EvilInt(7),
                           device_name='SECRET-name', id='SECRET-id', token='SECRET-token', body='SECRET-body')
                diag.event('SPOTIFY_DEVICES_BODY', endpoint=Evil('available_devices'),
                           devices_body=Evil('valid'), devices_total='SECRET-count')
                diag.event('SPOTIFY_DEVICES_BODY', devices_body='SECRET-body', endpoint='SECRET-url')
                diag.event(Evil('SPOTIFY_DEVICES_BODY'), devices_total=0)
                diag.event('SPOTIFY_DEVICES_BODY', **{Evil('devices_total'): 8})
                diag._handler.flush(); log = (Path(folder) / 'logs/events.log').read_text(encoding='utf-8')
                self.assertIn('devices_body=valid', log)
                self.assertIn('devices_total=0', log)
                self.assertNotIn('SECRET', log)
                self.assertNotIn('devices_active=', log)
                self.assertNotIn('devices_private=', log)
                self.assertNotIn('devices_restricted=', log)
            finally:
                diag._logger.removeHandler(diag._handler); diag._handler.close()

    def test_http_body_and_malformed_json_use_real_safe_formatter(self):
        bodies = [(b'{"devices":[]}', 'valid'),
                  (b'{"devices":[{"name":"SECRET-name","type":"smartphone","is_active":"SECRET-bool"}]}', 'invalid'),
                  (b'{"SECRET-malformed"', 'invalid'), (b'['*1200+b'0'+b']'*1200, 'invalid')]
        for body, expected in bodies:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory(dir=ROOT) as folder:
                clock = Clock(); root = Path(folder); diag = Diagnostics(root/'logs'); diag.start()
                try:
                    with patch('time.time', new=lambda: clock.now), patch('time.monotonic', new=lambda: clock.mono):
                        api = SpotifyApiBridge('fixture', root/'tokens.json')
                        api._tokens.update(access_token='SECRET-token', refresh_token='fixture', expires_at=clock.now+86400)
                        with patch('spotify_api.diagnostics', diag), \
                             patch('urllib.request.urlopen', return_value=Response(body, 200)) as http:
                            self.assertEqual(api.diagnose_devices(lambda: True), expected == 'valid')
                            self.assertEqual(http.call_count, 1)
                    diag._handler.flush(); log = (root/'logs/events.log').read_text(encoding='utf-8')
                    self.assertIn('SPOTIFY_DEVICES_HTTP', log)
                    self.assertIn('http_status=200', log)
                    self.assertIn('devices_body='+expected, log)
                    self.assertNotIn('SECRET', log)
                    self.assertNotIn('endpoint=playback_state', log)
                    if expected == 'invalid': self.assertNotIn('devices_total=', log)
                finally:
                    diag._logger.removeHandler(diag._handler); diag._handler.close()

    def denied_slot(self, where):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            clock = Clock(); root = Path(folder); publications = []; http_calls = []; waits = []
            with patch('time.time', new=lambda: clock.now), patch('time.monotonic', new=lambda: clock.mono):
                budget = ApiBudget(root/'budget.json', wall=lambda: clock.now, monotonic=lambda: clock.mono)
                api = SpotifyApiBridge('fixture', root/'tokens.json', budget=budget)
                api._tokens.update(access_token='fixture', refresh_token='fixture', expires_at=clock.now+86400)
                api._last_is_playing = True; api._last_art_key = 'sentinel-art'
                bridge = WindowsMediaBridge(on_update=lambda *args: publications.append(args))
                bridge._spotify = api; bridge._source_mode = bridge._current_source = 'spotify_api'
                bridge._source_epoch = bridge._api_snapshot_epoch = 1
                bridge._last_api_snapshot_at = clock.mono-10
                sentinel = MediaSnapshot(available=True, source='SPOTIFY API', track_key='sentinel')
                bridge._last_snapshot = sentinel
                bridge._observe_primary_playback(None, automatic=True)
                interval = api.poll_interval_seconds(idle=False)
                before = (bridge._last_api_snapshot_at, bridge._api_snapshot_epoch, bridge._last_snapshot,
                          bridge._api_only_idle, api._last_is_playing, api._last_art_key,
                          api.primary_playback_revision, bridge._api_waiting)
                real_attempt = budget.http_attempt; real_save = budget.store.save
                def attempt(function, **kwargs):
                    if where == 'before': raise BudgetWait(12, 'history_io')
                    if where == 'guard':
                        kwargs['start_check']()
                        raise BudgetWait(12, 'history_io')
                    return real_attempt(function, **kwargs)
                def save(state):
                    if where == 'after_http' and http_calls: raise BudgetWait(60, 'history_io')
                    if where == 'claim_work' and state.get('pending'):
                        bridge._manual_refresh = object()
                    return real_save(state)
                def http(request, **kwargs):
                    http_calls.append(request.full_url)
                    return Response(b'{"devices":[]}')
                async def wait(delay):
                    waits.append(delay)
                    self.assertGreaterEqual(delay, interval)
                    self.assertGreaterEqual(bridge._next_api_poll_at, clock.mono+interval)
                    self.assertEqual(before, (bridge._last_api_snapshot_at, bridge._api_snapshot_epoch,
                        bridge._last_snapshot, bridge._api_only_idle, api._last_is_playing,
                        api._last_art_key, api.primary_playback_revision, bridge._api_waiting))
                    self.assertEqual(publications, [])
                    bridge._stop.set()
                bridge._wait_for_spotify_work = wait
                with patch.object(budget, 'http_attempt', side_effect=attempt), \
                     patch.object(budget.store, 'save', side_effect=save), \
                     patch('urllib.request.urlopen', side_effect=http), \
                     patch('diagnostics.diagnostics.event') as events, \
                     patch('media_bridge.GlobalSystemMediaTransportControlsSessionManager.request_async',
                           new_callable=AsyncMock, return_value=Mock(get_sessions=lambda: [])):
                    asyncio.run(bridge._run())
                self.assertEqual(len(http_calls), 1 if where == 'after_http' else 0)
                self.assertEqual(bridge._devices_probe_attempts, int(where in ('guard', 'after_http')))
                self.assertTrue(waits)
                if where in ('guard', 'after_http'):
                    self.assertTrue(any(e.kwargs.get('phase') == 'guarded' for e in events.call_args_list))
                    bridge._stop.clear(); bridge._observe_primary_playback(None, automatic=True)
                    self.assertFalse(bridge._devices_probe_pending())
                if where == 'claim_work': self.assertIsNotNone(bridge._manual_refresh)

    def test_budget_wait_before_callback_preserves_primary_and_full_slot_wait(self):
        self.denied_slot('before')

    def test_budget_wait_after_start_guard_consumes_without_an_http_retry(self):
        self.denied_slot('guard')

    def test_durable_io_failure_after_http_preserves_primary_and_publication_count(self):
        self.denied_slot('after_http')

    def test_work_queued_during_durable_claim_has_priority_without_direct_a(self):
        self.denied_slot('claim_work')


if __name__ == '__main__':
    unittest.main()


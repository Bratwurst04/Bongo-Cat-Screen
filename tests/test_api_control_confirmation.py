"""Real file ledger and whole media worker; fake Spotify only, no live profile."""
import asyncio
import datetime as dt
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
import urllib.error
import urllib.parse
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'companion'))
from api_budget import ApiBudget, BudgetWait
from media_bridge import MediaSnapshot, WindowsMediaBridge
from spotify_api import SpotifyApiBridge
from diagnostics import Diagnostics


class Clock:
    def __init__(self):
        self.now = dt.datetime(2026, 10, 15, 9, 45, tzinfo=dt.timezone.utc).timestamp()
        self.mono = 1000.0

    def advance(self, seconds):
        self.now += seconds
        self.mono += seconds


class Response:
    def __init__(self, payload, status=200, headers=None):
        self.payload, self.status, self.headers = payload, status, headers or {}

    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return self.payload


def frozen_client():
    path = ROOT / 'build/api-budget-2026-10-14/source-frozen/companion/spotify_api.py'
    # Compile from bytes so inspecting the frozen source creates no pycache
    # or other files in its protected snapshot directory.
    from frozen_source import load_module
    return load_module('control_fix_frozen_client', path, optional_archive=True).SpotifyApiBridge


class ControlConfirmationTests(unittest.TestCase):
    def worker(self, client=SpotifyApiBridge, payload=b' ', status=204,
               actions=('NEXT',), error=None, success_error=None, commit_failure=False,
               gate=1.0, headers=None):
        folder = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        clock = Clock()
        tokens = dict(access_token='fixture', refresh_token='fixture', expires_at=clock.now + 86400,
                      adaptive_interval_seconds=gate, adaptive_safe_interval_seconds=.5,
                      adaptive_last_limit_reason='quota_exceeded', rate_limit_until=clock.now - 1,
                      adaptive_quota_recovery_until=clock.now + 86399, adaptive_total_429=2)
        token_path = root / 'tokens.json'
        token_path.write_text(json.dumps(tokens))
        calls, snapshots, control_times, confirm_times, oauth, queued_times = [], [], [], [], [], []
        data = dict(item=dict(id='initial', name='fixture', duration_ms=180000),
                    device=dict(id='device'), progress_ms=30000, is_playing=True)
        queued = list(actions)
        real_sleep = asyncio.sleep
        api = bridge = None
        get_sequence=scheduled_sequence=0

        def http(request, **kwargs):
            nonlocal error,get_sequence
            if '/api/token' in request.full_url:
                oauth.append(clock.mono);clock.advance(.12)
                return Response(b'{"access_token":"refreshed-fixture","expires_in":86400}')
            calls.append((request.method, request.full_url, clock.mono))
            clock.advance(.12)
            if request.method != 'GET':
                if error is not None:
                    failure, error = error, None
                    raise failure
                control_times.append(clock.mono)
                if request.full_url.endswith('/next'): data['item']['id'] = 'next'
                if request.full_url.endswith('/pause'): data['is_playing'] = False
                if request.full_url.endswith('/play'): data['is_playing'] = True
                return Response(payload,status,headers if headers is not None else {'Content-Type':'application/json'})
            get_sequence+=1
            if control_times:
                confirm_times.append(clock.mono)
            data['progress_ms'] += 1000
            if not queued and len(control_times)>=len(actions):
                bridge._stop.set()
            return Response(json.dumps(data).encode())

        async def sleep(seconds):
            nonlocal scheduled_sequence
            clock.advance(seconds)
            if queued and bridge._last_snapshot and get_sequence>scheduled_sequence:
                queued_times.append(clock.mono)
                self.assertTrue(bridge.control(queued.pop(0)))
                scheduled_sequence=get_sequence
            if clock.mono > 1185: bridge._stop.set()
            await real_sleep(0)

        with patch('time.time', new=lambda: clock.now), \
             patch('time.monotonic', new=lambda: clock.mono), \
             patch('urllib.request.urlopen', new=http), \
             patch('media_bridge.asyncio.sleep', new=sleep), \
             patch('media_bridge.diagnostics.event') as event, \
             patch('media_bridge.SpotifyApiError',client._api_request_locked.__globals__['SpotifyApiError']), \
             patch('media_bridge.SpotifyPacingError',client._api_request_locked.__globals__['SpotifyPacingError']), \
             patch('media_bridge.SpotifyRateLimitError',client._api_request_locked.__globals__['SpotifyRateLimitError']), \
             patch('media_bridge.SpotifyBudgetError',client._api_request_locked.__globals__['SpotifyBudgetError']), \
             patch('media_bridge.GlobalSystemMediaTransportControlsSessionManager.request_async',
                   new_callable=AsyncMock, return_value=Mock(get_sessions=lambda: [])):
            budget = ApiBudget(root / 'spotify_api_budget.json', wall=lambda: clock.now,
                               monotonic=lambda: clock.mono)
            api = client('fixture', token_path, budget=budget)
            if success_error:
                original_success=api._record_success
                def fail_after_control():
                    if control_times and calls[-1][0]!='GET':raise success_error
                    return original_success()
                api._record_success=fail_after_control
            if commit_failure:
                original_save=budget.store.save
                failed=[]
                def fail_final_commit(state):
                    if control_times and not state['pending'] and not failed:
                        failed.append(True);raise BudgetWait(60,'history_io')
                    return original_save(state)
                budget.store.save=fail_final_commit
            bridge = WindowsMediaBridge(on_update=lambda snapshot, art: snapshots.append(snapshot))
            bridge._spotify = api
            bridge._try_api_artwork = AsyncMock(return_value=None)
            asyncio.run(bridge._run())
            view = budget.view()
        return dict(calls=calls, snapshots=snapshots, control_times=control_times,
                    confirm_times=confirm_times, events=event.call_args_list, view=view,
                    bridge=bridge, api=api, oauth=oauth, queued_times=queued_times)

    def test_frozen_whitespace_204_reproduces_sent_control_lost_confirmation(self):
        result = self.worker(client=frozen_client())
        self.assertEqual(len(result['control_times']), 1)
        failures = [e for e in result['events'] if e.args[0] == 'MEDIA_CONTROL' and
                    e.kwargs.get('reason') == 'api_error']
        self.assertEqual(len(failures), 1)
        self.assertIs(failures[0].kwargs['error_type'],json.JSONDecodeError)
        latency = result['confirm_times'][0] - result['control_times'][0]
        self.assertGreaterEqual(latency, 59)
        self.assertEqual(result['view']['long_used'], 3)
        self.assertEqual(result['view']['long_auto_used'], 2)

    def test_successful_bodyless_controls_confirm_quickly_under_quota_recovery(self):
        forms=[(204,b'',{'Content-Length':'0'}),(204,b' ',{}),
               (200,b'\r\n',{'Content-Type':'application/json'}),
               (202,b'accepted',{'Content-Type':'text/plain'}),
               (200,b'\xff',{}),(200,b'{"ignored":true}',{'Content-Type':'application/json'})]
        for gate in (.5,1.0):
          for status,payload,headers in forms:
            with self.subTest(gate=gate,status=status,payload=payload):
                result = self.worker(status=status, payload=payload,
                                     actions=('NEXT','PLAY_PAUSE','PLAY_PAUSE'),gate=gate,headers=headers)
                self.assertEqual(len(result['control_times']), 3)
                self.assertEqual(len(result['confirm_times']), 3)
                self.assertTrue(all(.5 <= confirmed - control <= 2.0 for control, confirmed in
                                    zip(result['control_times'],result['confirm_times'])))
                self.assertTrue(result['snapshots'][-1].playing)
                self.assertTrue(any(not s.playing for s in result['snapshots']))
                self.assertFalse(any(e.kwargs.get('reason') == 'api_error' for e in result['events']))
                self.assertEqual(result['view']['reserved'],0)
                self.assertEqual(result['view']['long_used'],7)
                self.assertEqual(result['view']['long_auto_used'],1)
                self.assertTrue(result['view']['quota_recovery'])
                self.assertFalse(result['view']['history_complete'])
                self.assertEqual(result['view']['interval_seconds'],5)
                times=[c[2] for c in result['calls']]
                self.assertTrue(all(b-a>=.5 for a,b in zip(times,times[1:])))


    def test_get_metadata_keeps_strict_json_parsing(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            clock=Clock()
            with patch('time.time',new=lambda:clock.now),patch('time.monotonic',new=lambda:clock.mono):
                api=SpotifyApiBridge('fixture',Path(folder)/'tokens.json')
                api._tokens.update(access_token='fixture',refresh_token='fixture',expires_at=clock.now+86400)
                with patch('urllib.request.urlopen',return_value=Response(b'not-json',200)):
                    with self.assertRaises(json.JSONDecodeError):api.get_playback()
                self.assertEqual(api._budget.view()['long_used'],1)

    def test_control_diagnostics_allow_class_and_status_without_content(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            diag=Diagnostics(Path(folder)/'logs');diag.start()
            try:
                diag.event('MEDIA_CONTROL',action='NEXT',result='skipped',reason='api_error',
                           error_type=json.JSONDecodeError,http_status=200,
                           raw_body='private',url='private',token='private',message='private')
                diag._handler.flush()
                log=(Path(folder)/'logs/events.log').read_text(encoding='utf-8')
                self.assertIn('error_type=JSONDecodeError',log)
                self.assertIn('http_status=200',log)
                self.assertNotIn('private',log)
            finally:diag._handler.close()

    def test_401_refresh_retry_and_authoritative_confirm_in_whole_worker(self):
        error=urllib.error.HTTPError('fixture',401,'fixture',{},io.BytesIO(b'{}'))
        result=self.worker(payload=b' ',error=error)
        self.assertEqual(len(result['oauth']),1)
        self.assertEqual([c[0] for c in result['calls']],['GET','POST','POST','GET'])
        self.assertEqual(len(result['control_times']),1)
        self.assertLess(result['confirm_times'][0]-result['control_times'][0],2)
        self.assertEqual(result['view']['long_used'],4)
        self.assertEqual(result['view']['long_auto_used'],1)
        self.assertEqual(result['view']['reserved'],0)

    def test_403_500_and_network_errors_keep_safe_control_diagnostics(self):
        for error in [urllib.error.HTTPError('fixture',403,'fixture',{},io.BytesIO(b'{}')),
                      urllib.error.HTTPError('fixture',500,'fixture',{},io.BytesIO(b'{}')),
                      urllib.error.URLError('fixture')]:
            with self.subTest(error=type(error).__name__,status=getattr(error,'code',None)):
                result=self.worker(error=error)
                failures=[e for e in result['events'] if e.args[0]=='MEDIA_CONTROL' and
                          e.kwargs.get('reason')=='api_error']
                self.assertEqual(len(failures),1)
                self.assertEqual(failures[0].kwargs['http_status'],getattr(error,'code',None))
                self.assertIs(failures[0].kwargs['error_type'],
                              SpotifyApiBridge._api_request_locked.__globals__['SpotifyApiError'])
                self.assertEqual(len(result['control_times']),0)
                self.assertEqual(sum(c[0]!='GET' for c in result['calls']),1)
                self.assertFalse(result['bridge']._control_requests)
                self.assertEqual(result['view']['reserved'],0)
                self.assertEqual(result['api']._tokens['adaptive_total_429'],2)

    def test_429_discards_control_and_preserves_server_retry(self):
        error=urllib.error.HTTPError('fixture',429,'fixture',{'Retry-After':'400'},
                                    io.BytesIO(b'{"error":{"reason":"QUOTA_EXCEEDED"}}'))
        result=self.worker(error=error)
        self.assertEqual([c[0] for c in result['calls']],['GET','POST'])
        self.assertEqual(result['api']._tokens['adaptive_total_429'],3)
        self.assertGreater(result['view']['retry_remaining_seconds'],200)
        self.assertEqual(result['view']['reserved'],0)
        self.assertFalse(result['bridge']._control_requests)

    def test_clean_window_token_save_error_cannot_undo_accepted_control(self):
        result=self.worker(payload=b' ',success_error=OSError('fixture'))
        self.assertLess(result['confirm_times'][0]-result['control_times'][0],2)
        self.assertFalse(any(e.kwargs.get('reason')=='api_error' for e in result['events']))
        self.assertEqual(result['view']['long_used'],3)
        self.assertEqual(result['view']['long_auto_used'],1)

    def test_failed_budget_commit_remains_fail_closed_and_never_replays_control(self):
        result=self.worker(payload=b'',commit_failure=True)
        self.assertEqual(sum(c[0]!='GET' for c in result['calls']),1)
        self.assertTrue(any(e.kwargs.get('reason')=='history_io' for e in result['events']))
        self.assertEqual(result['view']['long_used'],len(result['calls']))
        self.assertEqual(result['view']['reserved'],0)
        self.assertFalse(any(e.kwargs.get('reason')=='api_error' for e in result['events']))


if __name__ == '__main__': unittest.main()

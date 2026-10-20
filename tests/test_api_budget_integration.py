"""Real admission/client/bridge with mocked HTTP; no real Spotify or profiles."""
import asyncio
import datetime as dt
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
from unittest.mock import AsyncMock, Mock, patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'companion'))
from api_budget import ApiBudget, BudgetWait, _new_state
from spotify_api import SpotifyApiBridge, SpotifyApiError, SpotifyBudgetError, SpotifyPacingError, SpotifyRateLimitError
from media_bridge import WindowsMediaBridge, MediaSnapshot


class Clock:
    def __init__(self):
        self.now=dt.datetime(2026,10,14,10,tzinfo=dt.timezone.utc).timestamp();self.mono=1000.0
    def advance(self,seconds):self.now+=seconds;self.mono+=seconds


class Response:
    def __init__(self,data):self.data=data
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self, size=-1):return self.data if size < 0 else self.data[:size]


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory(dir=ROOT);self.addCleanup(folder.cleanup)
        self.path=Path(folder.name);self.clock=Clock();self.calls=[]
        state=_new_state(self.clock.now,self.clock.mono);state['warm_until']=0
        ledger=self.path/'spotify_api_budget.json';ledger.write_text(json.dumps(state))
        self.budget=ApiBudget(ledger,wall=lambda:self.clock.now,monotonic=lambda:self.clock.mono)
        for name,value in [('time.time',lambda:self.clock.now),('time.monotonic',lambda:self.clock.mono),
                           ('spotify_api._spotify_urlopen',self.http)]:
            p=patch(name,new=value);p.start();self.addCleanup(p.stop)
        self.api=SpotifyApiBridge('fixture',self.path/'tokens.json',budget=self.budget)
        self.api._tokens.update(access_token='fixture',refresh_token='fixture',expires_at=self.clock.now+86400)
        self.data={'item':{'id':'same','name':'fixture','duration_ms':180123},'device':{'id':'device'},
                   'progress_ms':30000,'is_playing':False}
        self.next_error=None
        self.snapshot,_=self.api.get_playback()

    def http(self,request,**kwargs):
        self.calls.append((request.method,request.full_url,self.clock.mono))
        if self.next_error:
            error=self.next_error;self.next_error=None;raise error
        if request.method=='GET':return Response(json.dumps(self.data).encode())
        return Response(b'')

    def bridge(self):
        bridge=WindowsMediaBridge(on_update=Mock());bridge._spotify=self.api
        bridge._current_source='spotify_api'
        bridge._last_snapshot=MediaSnapshot(available=True,**self.snapshot)
        return bridge

    def pump(self,bridge):
        for _ in range(30):
            try:return bridge._handle_spotify_commands()
            except SpotifyPacingError as exc:self.clock.advance(exc.wait_seconds)
        self.fail('Explicit operation did not settle')

    def confirm(self,bridge):
        self.clock.advance(0.8)
        for _ in range(5):
            try:
                playback,_=self.api.get_playback(urgent=True,operation=bridge._confirmation_operation)
                self.api.finish_operation(bridge._confirmation_operation);bridge._confirmation_operation=None
                bridge._publish(MediaSnapshot(available=True,**playback),None)
                return
            except SpotifyPacingError as exc:self.clock.advance(exc.wait_seconds)
        self.fail('Confirmation did not settle')

    def test_free_urgent_does_not_bypass_auto_profile(self):
        self.clock.advance(0.5)
        for call in (lambda:self.api.get_playback(urgent=True),):
            with self.assertRaises(SpotifyBudgetError):call()
        self.assertEqual(len(self.calls),1)
        self.assertEqual(self.budget.view(True)['long_auto_used'],1)



    def test_real_401_retry_has_reserved_cost_and_is_charged_before_http(self):
        self.clock.advance(0.5)
        operation=self.api.begin_operation('control')
        self.next_error=urllib.error.HTTPError('fixture',401,'fixture',{},io.BytesIO(b'{}'))
        def refresh():
            self.clock.advance(0.6)
            self.api._tokens['access_token']='refreshed-fixture'
        self.api._refresh=Mock(side_effect=refresh)
        with patch('spotify_api._spotify_urlopen',side_effect=self.http) as http:
            self.api.control('NEXT',operation=operation)
        self.api._refresh.assert_called_once_with()
        self.assertEqual(http.call_count,2)
        self.assertEqual(http.call_args_list[0].args[0].headers['Authorization'],'Bearer fixture')
        self.assertEqual(http.call_args_list[1].args[0].headers['Authorization'],'Bearer refreshed-fixture')
        self.assertEqual(self.api._tokens['adaptive_request_total'],3)
        self.clock.advance(0.5);self.api.get_playback(urgent=True,operation=operation)
        self.api.finish_operation(operation)
        state=json.loads(self.budget.store.path.read_text())
        self.assertEqual(sum(r[1]+r[2] for r in state['minutes']),len(self.calls))
        self.assertEqual(len(self.calls),4)
        self.assertFalse(state['grants'])

    def test_401_refresh_cannot_skip_real_start_spacing(self):
        self.clock.advance(0.5);operation=self.api.begin_operation('control')
        self.next_error=urllib.error.HTTPError('fixture',401,'fixture',{},io.BytesIO(b'{}'))
        self.api._refresh=Mock()
        with self.assertRaises(SpotifyPacingError) as raised:
            self.api.control('NEXT',operation=operation)
        self.assertIs(type(raised.exception),SpotifyPacingError)
        self.api._refresh.assert_called_once_with()
        self.assertEqual(len(self.calls),2)
        self.assertEqual(self.budget.view()['long_used'],2)

    def test_http_quota_and_short_429_keep_classification_event_and_shared_deadline(self):
        for reason,seconds in [('QUOTA_EXCEEDED',49473),('RATE_LIMITED',20)]:
            with self.subTest(reason=reason):
                self.clock.advance(60)
                # Each response gets its own real, isolated FileBudgetStore.
                path=self.path/(reason+'.json')
                state=_new_state(self.clock.now,self.clock.mono);state['warm_until']=0
                path.write_text(json.dumps(state))
                budget=ApiBudget(path,wall=lambda:self.clock.now,monotonic=lambda:self.clock.mono)
                api=SpotifyApiBridge('fixture',self.path/(reason+'-tokens.json'),budget=budget)
                api._tokens.update(access_token='fixture',refresh_token='fixture',expires_at=self.clock.now+86400)
                self.next_error=urllib.error.HTTPError('fixture',429,'fixture',{'Retry-After':str(seconds)},
                    io.BytesIO(json.dumps({'error':{'reason':reason}}).encode()))
                count=len(self.calls)
                with patch('spotify_api.diagnostics.event') as event:
                    with self.assertRaises(SpotifyRateLimitError) as raised:api.get_playback()
                self.assertFalse(raised.exception.cached)
                self.assertEqual(raised.exception.reason,reason.lower())
                self.assertEqual(raised.exception.retry_after_seconds,seconds)
                self.assertEqual(len(self.calls),count+1)
                self.assertEqual(api._tokens['adaptive_total_429'],1)
                self.assertEqual(api._tokens['adaptive_request_total'],1)
                events=[c for c in event.call_args_list if c.args[0]=='SPOTIFY_API_429']
                self.assertEqual(len(events),1)
                self.assertEqual(events[0].kwargs['reason'],reason.lower())
                self.assertEqual(events[0].kwargs['total_429'],1)
                self.assertEqual(events[0].kwargs['playback_poll'],1)
                self.assertEqual(api._tokens['adaptive_interval_seconds'],1)
                self.assertEqual(budget.view()['long_used'],1)
                self.assertEqual(budget.view()['retry_remaining_seconds'],seconds)
                other=SpotifyApiBridge('fixture',api.token_path,budget=ApiBudget(path,
                    wall=lambda:self.clock.now,monotonic=lambda:self.clock.mono))
                with self.assertRaises(SpotifyRateLimitError) as cached:other.get_playback(urgent=True)
                self.assertTrue(cached.exception.cached)
                self.assertEqual(cached.exception.reason,reason.lower())
                self.assertEqual(len(self.calls),count+1)

    def test_429_final_commit_and_token_write_failure_preserve_known_retry(self):
        self.clock.advance(60)
        self.next_error=urllib.error.HTTPError('fixture',429,'fixture',{'Retry-After':'49473'},
            io.BytesIO(b'{"error":{"reason":"QUOTA_EXCEEDED"}}'))
        original_save=self.budget.store.save;save_calls=[]
        def fail_after_pending(state):
            save_calls.append(bool(state['pending']))
            if len(save_calls)==1:return original_save(state)
            raise BudgetWait(60,'history_io')
        with patch.object(self.budget.store,'save',side_effect=fail_after_pending), \
             patch.object(self.api,'_save_tokens',side_effect=OSError('fixture')), \
             patch('spotify_api.diagnostics.event') as event:
            with self.assertRaises(SpotifyRateLimitError) as raised:self.api.get_playback()
        self.assertEqual(raised.exception.reason,'quota_exceeded')
        self.assertFalse(raised.exception.cached)
        self.assertEqual(self.api._tokens['adaptive_total_429'],1)
        self.assertGreaterEqual(self.api._rate_limit_until()-self.clock.now,49473)
        self.assertEqual(len([c for c in event.call_args_list if c.args[0]=='SPOTIFY_API_429']),1)
        self.assertTrue(json.loads(self.budget.store.path.read_text())['pending'])
        self.assertEqual(self.budget.view()['retry_remaining_seconds'],49473)
        count=len(self.calls)
        other=SpotifyApiBridge('fixture',self.path/'other-tokens.json',budget=ApiBudget(self.budget.store.path,
            wall=lambda:self.clock.now,monotonic=lambda:self.clock.mono))
        other._tokens.update(access_token='fixture',refresh_token='fixture',expires_at=self.clock.now+86400)
        with self.assertRaises(SpotifyRateLimitError):other.get_playback(urgent=True)
        # The next transaction flushes the unsaved, shared server protection.
        with self.assertRaises(SpotifyRateLimitError):other.begin_operation('control')
        self.assertEqual(len(self.calls),count)
        saved=json.loads(self.budget.store.path.read_text())
        self.assertFalse(saved['pending']);self.assertEqual(saved['retry_reason'],2)
        self.assertGreaterEqual(saved['retry_until']-saved['logical'],49473)

    @unittest.skipUnless(sys.platform=='win32','Windows lock error path')
    def test_unlock_error_does_not_mask_server_response_and_guards_future_work(self):
        import msvcrt
        self.clock.advance(60)
        self.next_error=urllib.error.HTTPError('fixture',429,'fixture',{'Retry-After':'20'},
            io.BytesIO(b'{"error":{"reason":"RATE_LIMITED"}}'))
        locking=msvcrt.locking
        def unlock_error(fd,mode,count):
            result=locking(fd,mode,count)
            if mode==msvcrt.LK_UNLCK:raise OSError('fixture')
            return result
        with patch('msvcrt.locking',side_effect=unlock_error):
            with self.assertRaises(SpotifyRateLimitError):self.api.get_playback()
        self.clock.advance(21)
        with self.assertRaises(SpotifyBudgetError) as guarded:self.api.get_playback()
        self.assertEqual(guarded.exception.reason,'history_io')
        self.assertEqual(len(self.calls),2)

    def test_http_500_and_url_error_use_media_fallback_with_real_file_store(self):
        for error in [urllib.error.HTTPError('fixture',500,'fixture',{},io.BytesIO(b'{}')),
                      urllib.error.URLError('fixture')]:
            with self.subTest(error=type(error).__name__):
                self.clock.advance(60);bridge=self.bridge();self.next_error=error
                manager=Mock();manager.get_sessions.return_value=[]
                published=[]
                def update(snapshot,art):published.append(snapshot);bridge._stop.set()
                bridge._on_update=update
                async def sleep(seconds):self.clock.advance(seconds)
                with patch('media_bridge.GlobalSystemMediaTransportControlsSessionManager.request_async',
                           new_callable=AsyncMock,return_value=manager), \
                     patch('media_bridge.asyncio.sleep',new=sleep), \
                     patch('media_bridge.diagnostics.event') as event:
                    asyncio.run(bridge._run())
                self.assertEqual(published[-1].title,'Nothing playing')
                self.assertEqual(bridge._current_source,'generic')
                self.assertFalse(bridge._spotify_retry_is_rate_limit)
                self.assertTrue(any(c.args[0]=='SPOTIFY_FALLBACK' and c.kwargs['reason']=='api_error'
                                    for c in event.call_args_list))
                self.assertEqual(self.api._tokens['adaptive_total_429'],0)
                self.assertEqual(self.budget.view()['long_used'],len(self.calls))

    def test_long_real_retry_wins_activity_reset_restart_and_urgent(self):
        self.api._record_rate_limit(49473,'quota_exceeded','playback_poll');self.api._save_tokens()
        count=len(self.calls)
        self.api.notify_local_activity();self.api.configure_pacing({'api_reset_safety_requested_at':self.clock.now+1})
        other=SpotifyApiBridge('fixture',self.path/'tokens.json')
        for api in (self.api,other):
            for call in (lambda:api.get_playback(urgent=True),lambda:api.control('NEXT')):
                with self.assertRaises(SpotifyRateLimitError):call()
            self.assertEqual(api.status()['state'],'rate_limited')
        self.assertEqual(len(self.calls),count)
        self.clock.advance(49474)
        self.assertTrue(self.api.status()['local_budget']['quota_recovery'])
        self.assertGreaterEqual(self.api.poll_interval_seconds(),60)

    def test_cooldown_queue_clear_releases_all_control_slots(self):
        bridge=self.bridge()
        for _ in range(8):self.assertTrue(bridge.control('NEXT'))
        self.assertFalse(bridge.control('NEXT'))
        bridge._publish_no_windows_status()
        self.assertFalse(bridge._control_requests)
        self.assertTrue(bridge._commands.empty())
        bridge._current_source='spotify_api';bridge._last_snapshot=MediaSnapshot(available=True,**self.snapshot)
        self.assertTrue(bridge.control('NEXT'))
        self.assertEqual(len(self.calls),1)

    def test_expired_normal_commands_never_replay(self):
        bridge=self.bridge();bridge.control('NEXT')
        self.clock.advance(6)
        self.assertFalse(self.pump(bridge));self.assertEqual(len(self.calls),1)
        self.assertFalse(bridge._control_requests)

    def test_atomic_write_failure_starts_no_http_and_does_not_clear_history(self):
        self.clock.advance(60);before=self.budget.store.path.read_bytes()
        with patch('api_budget.os.replace',side_effect=OSError('fixture')):
            with self.assertRaises(SpotifyBudgetError):self.api.get_playback()
        self.assertEqual(len(self.calls),1);self.assertEqual(self.budget.store.path.read_bytes(),before)

    def test_windows_controls_use_no_api_grant_or_http(self):
        bridge=self.bridge();bridge._current_source='windows_spotify'
        session=Mock();session.try_skip_next_async=AsyncMock(return_value=True)
        bridge.control('NEXT')
        with patch.object(self.api,'begin_operation',side_effect=AssertionError('No API for Windows')):
            self.assertTrue(asyncio.run(bridge._handle_commands(session)))
        session.try_skip_next_async.assert_awaited_once_with();self.assertEqual(len(self.calls),1)
        self.assertFalse(bridge._control_requests)

    def test_local_budget_wait_does_not_hide_a_new_windows_session(self):
        bridge=self.bridge()
        session=Mock(source_app_user_model_id='Spotify.exe')
        manager=Mock()
        manager.get_sessions.side_effect=[[],[],[session]]
        local=MediaSnapshot(available=True,source='SPOTIFY',track_key='windows',title='fixture')
        bridge._read_session=AsyncMock(return_value=(local,None))
        bridge._windows_api_artwork_due=Mock(return_value=False)
        bridge._on_update=lambda snapshot,art:bridge._stop.set() if snapshot.track_key=='windows' else None
        async def sleep(seconds):self.clock.advance(seconds)
        with patch('media_bridge.GlobalSystemMediaTransportControlsSessionManager.request_async',
                   new_callable=AsyncMock,return_value=manager),patch('media_bridge.asyncio.sleep',new=sleep):
            asyncio.run(bridge._run())
        self.assertEqual(bridge._current_source,'windows_spotify')
        self.assertEqual(len(self.calls),1)
        self.assertLess(self.clock.mono,1002)

    def test_parallel_client_oauth_prep_cannot_advance_final_network_admission(self):
        self.clock.advance(0.5)
        entered=threading.Event();release=threading.Event();errors=[]
        grant_a=self.api.begin_operation('control')
        other_budget=ApiBudget(self.budget.store.path,wall=lambda:self.clock.now,monotonic=lambda:self.clock.mono)
        other=SpotifyApiBridge('fixture',self.path/'tokens2.json',budget=other_budget)
        other._tokens.update(access_token='fixture',refresh_token='fixture',expires_at=self.clock.now+86400)
        grant_b=other.begin_operation('control')
        def slow_access():
            entered.set();release.wait(timeout=2);return 'fixture'
        def a():
            try:self.api.get_playback(urgent=True,operation=grant_a)
            except Exception as exc:errors.append(exc)
        with patch.object(self.api,'_access_token',side_effect=slow_access):
            thread=threading.Thread(target=a);thread.start();self.assertTrue(entered.wait(timeout=1))
            other.get_playback(urgent=True,operation=grant_b)
            self.clock.advance(4);release.set();thread.join(timeout=2)
        self.assertFalse(thread.is_alive());self.assertFalse(errors)
        self.assertGreaterEqual(self.calls[-1][2]-self.calls[-2][2],0.5)
        self.assertEqual(self.budget.view()['long_used'],len(self.calls))

    def test_slow_fsync_is_inside_shared_start_transaction_and_expiry_is_rechecked(self):
        self.clock.advance(0.5);operation=self.api.begin_operation('control')
        def delayed_sync(fd):self.clock.advance(0.6)
        with patch('api_budget.os.fsync',side_effect=delayed_sync):
            self.api.get_playback(urgent=True,operation=operation)
        self.api.finish_operation(operation)
        self.assertGreaterEqual(self.calls[-1][2]-self.calls[-2][2],0.5)
        operation=self.api.begin_operation('control');count=len(self.calls)
        with patch('api_budget.os.fsync',side_effect=lambda fd:self.clock.advance(11)):
            with self.assertRaises(SpotifyBudgetError):self.api.get_playback(urgent=True,operation=operation)
        self.assertEqual(len(self.calls),count)
        self.assertFalse(json.loads(self.budget.store.path.read_text())['pending'])

    def test_long_oauth_preparation_expires_grant_before_any_v1_start(self):
        self.clock.advance(0.5);operation=self.api.begin_operation('control');count=len(self.calls)
        def token():self.clock.advance(11);return 'fixture'
        with patch.object(self.api,'_access_token',side_effect=token):
            with self.assertRaises(SpotifyBudgetError):self.api.get_playback(urgent=True,operation=operation)
        self.assertEqual(len(self.calls),count)

    def test_crash_pending_cost_never_expires_before_a_real_start_window(self):
        state=json.loads(self.budget.store.path.read_text());state['pending']=[[0,0]]
        self.budget.store.path.write_text(json.dumps(state));self.clock.advance(86400)
        other=ApiBudget(self.budget.store.path,wall=lambda:self.clock.now,monotonic=lambda:self.clock.mono)
        with self.assertRaises(BudgetWait):other.http_attempt(lambda:None)
        self.assertGreaterEqual(other.view()['long_used'],1)
        self.assertFalse(json.loads(self.budget.store.path.read_text())['pending'])
        self.assertGreaterEqual(other.view()['clock_guard_remaining_seconds'],86400)

    def test_pre_oauth_debit_ordering_reproduces_zero_gap_then_final_guard_prevents_it(self):
        # Reproduce the reviewed ordering with real shared FileStore debits:
        # A is charged, waits for OAuth; B is charged and starts; A then starts
        # at B's time because its older charge had already passed the guard.
        self.clock.advance(0.5)
        a=self.api.begin_operation('control')
        other=ApiBudget(self.budget.store.path,wall=lambda:self.clock.now,monotonic=lambda:self.clock.mono)
        b=other.begin_operation('control')
        self.budget.admit(operation=a)
        self.clock.advance(0.5);other.admit(operation=b)
        old_starts=[]
        old_starts.append(self.clock.mono) # B
        old_starts.append(self.clock.mono) # OAuth-ready A
        self.assertEqual(old_starts[1]-old_starts[0],0)
        self.api.finish_operation(a);other.finish_operation(b)
        self.clock.advance(0.5)
        a=self.api.begin_operation('control')
        self.api.get_playback(urgent=True,operation=a)
        with self.assertRaises(SpotifyPacingError):self.api.get_playback(urgent=True,operation=a)
        self.assertGreaterEqual(self.calls[-1][2]-self.calls[-2][2],0.5)

    def test_actual_http_windows_hold_with_delayed_disk_and_many_explicit_calls(self):
        def delayed_sync(fd):self.clock.advance(0.07)
        with patch('api_budget.os.fsync',side_effect=delayed_sync):
            for _ in range(20):
                operation=None
                while operation is None:
                    try:operation=self.api.begin_operation('control')
                    except SpotifyPacingError as exc:self.clock.advance(exc.wait_seconds)
                for _ in range(2):
                    expired=False
                    for attempt in range(10):
                        try:self.api.get_playback(urgent=True,operation=operation);break
                        except SpotifyPacingError as exc:
                            if isinstance(exc,SpotifyBudgetError) and exc.reason=='operation_expired':
                                # A bounded synthetic operation may expire
                                # while window capacity is unavailable. It
                                # must never turn into a replay of old work.
                                count=len(self.calls)
                                self.assertEqual(self.budget.view()['reserved'],0)
                                self.clock.advance(.5)
                                with self.assertRaises(SpotifyBudgetError):
                                    self.api.get_playback(urgent=True,operation=operation)
                                self.assertEqual(len(self.calls),count)
                                expired=True;break
                            last_wait=exc;self.clock.advance(exc.wait_seconds)
                    else:self.fail('Actual /v1 admission did not settle: '+
                        repr((type(last_wait).__name__,getattr(last_wait,'reason','classic'),
                              last_wait.wait_seconds,self.budget.view())))
                    if expired:break
                self.api.finish_operation(operation)
        times=[call[2] for call in self.calls]
        self.assertGreater(len(times),24)  # Exercise more than one short window.
        self.assertTrue(all(b-a>=0.499999 for a,b in zip(times,times[1:])))
        self.assertTrue(all(sum(t-30 < at <= t for at in times)<=24 for t in times))

    def test_actual_http_stops_at_shared_long_cap_after_delayed_disk(self):
        self.clock.advance(60)
        state=json.loads(self.budget.store.path.read_text())
        old=int((state['logical']-23*3600)//60)*60
        state['minutes']=[[old,0,7997]];state['short']=[]
        self.budget.store.path.write_text(json.dumps(state))
        count=len(self.calls);operation=self.api.begin_operation('control')
        with patch('api_budget.os.fsync',side_effect=lambda fd:self.clock.advance(0.07)):
            for _ in range(3):
                for attempt in range(5):
                    try:self.api.get_playback(urgent=True,operation=operation);break
                    except SpotifyPacingError as exc:self.clock.advance(exc.wait_seconds)
                else:self.fail('Granted call did not settle')
        self.assertEqual(len(self.calls)-count,3)
        self.assertEqual(self.budget.view()['long_used'],8000)
        other=SpotifyApiBridge('fixture',self.path/'other-tokens.json',budget=ApiBudget(self.budget.store.path,
            wall=lambda:self.clock.now,monotonic=lambda:self.clock.mono))
        other._tokens.update(access_token='fixture',refresh_token='fixture',expires_at=self.clock.now+86400)
        self.clock.advance(60)
        with self.assertRaises(SpotifyBudgetError):other.get_playback(urgent=True)
        with self.assertRaises(SpotifyBudgetError):other.begin_operation('control')
        self.assertEqual(len(self.calls)-count,3)


if __name__=='__main__':unittest.main()

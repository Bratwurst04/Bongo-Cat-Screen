"""Waiting-screen touch through full media worker, real ledger, mocked I/O."""
import asyncio
import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error
import io
from unittest.mock import AsyncMock, Mock, patch
from types import SimpleNamespace as NS

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'companion'))
from api_budget import ApiBudget
from media_bridge import WindowsMediaBridge, MediaSnapshot
from spotify_api import SpotifyApiBridge
from test_api_control_confirmation import Clock, Response


class ManualRefreshTests(unittest.TestCase):
    def scenario(self, *, tap=True, empty=False, paused=False, play_after=False,
                 burst=False, block=None, slow_token=0, return_at=None,
                 repeat=False, error401=False, spacing=False, takeover_during_wait=False,
                 read_error=None, success_io=False, tap_after_empty=False, persistent401=False,
                 day_profile=60):
        folder=tempfile.TemporaryDirectory(dir=ROOT);self.addCleanup(folder.cleanup)
        root=Path(folder.name);clock=Clock();start=clock.mono;real_sleep=asyncio.sleep
        path=root/'tokens.json'
        path.write_text(json.dumps(dict(access_token='fixture',refresh_token='fixture',
            expires_at=clock.now+86400,adaptive_interval_seconds=.5,
            adaptive_safe_interval_seconds=.5,adaptive_last_limit_reason='quota_exceeded',
            rate_limit_until=clock.now-1,adaptive_quota_recovery_until=clock.now+86399,
            adaptive_total_429=2)))
        session=Mock(source_app_user_model_id='Spotify.exe')
        windows=True;returned=False;calls=[];published=[];touches=[];oauth=[]
        manual_times=[];api_gets=[];tap_epochs=set();wait_seen=None;play_queued=False;manual_yields=[]
        api=bridge=None;once401=False;delayed=False
        data=dict(item=dict(id='remote',name='fixture',duration_ms=180000,
                            album=dict(images=[dict(url='https://fixture.invalid/cover')])),
                  device=dict(id='device'),progress_ms=30000,is_playing=not paused)
        windows_snapshot=MediaSnapshot(available=True,source='SPOTIFY',title='Windows fixture',
                                       track_key='windows-old',playing=True,duration_seconds=180)

        def http(request,**kwargs):
            nonlocal windows,returned,once401
            if '/api/token' in request.full_url:
                oauth.append(clock.mono);clock.advance(.12)
                return Response(b'{"access_token":"refreshed-fixture","expires_in":86400}')
            calls.append((request.method,request.full_url,clock.mono))
            if request.method!='GET':
                self.assertTrue(play_after,'Waiting refresh must never control playback')
                self.assertTrue(request.full_url.endswith('/play'))
                data['is_playing']=True
                clock.advance(.12);return Response(b'',204)
            request_slot=bridge._manual_refresh if bridge else None
            if request_slot is not None:
                manual_times.append(clock.mono)
                if burst:
                    for _ in range(12):
                        for action in ('PLAY_PAUSE','NEXT','PREVIOUS','SEEK:+15'):
                            touches.append(bridge.control(action))
                if (error401 and not once401) or persistent401:
                    once401=True
                    raise urllib.error.HTTPError('fixture',401,'fixture',{},io.BytesIO(b'{}'))
                if return_at=='response':windows=returned=True
            clock.advance(.12)
            if len(calls)>1:
                api_gets.append(clock.mono)
            if request_slot is not None and read_error:
                return Response({'json':b'not-json','unicode':b'\xff','shape':b'["bad-shape"]'}[read_error])
            payload={'item':None,'is_playing':False} if empty and len(calls)>1 else data
            if repeat and bridge and bridge._source_epoch>=4:
                payload={**data,'item':{**data['item'],'id':'remote-new-epoch'}}
            return Response(json.dumps(payload).encode())

        def sessions():return [session] if windows else []

        def publish(snapshot,art):
            nonlocal wait_seen
            published.append((clock.mono,snapshot,art))
            if snapshot.title=='Waiting for Spotify' and wait_seen is None:wait_seen=clock.mono
            if returned and not repeat and snapshot.track_key=='windows-old':bridge._stop.set()
            if play_after and snapshot.source=='SPOTIFY API' and snapshot.available and snapshot.playing:
                bridge._stop.set()
            if repeat and snapshot.track_key=='spotify:remote-new-epoch':bridge._stop.set()
            if not repeat and not play_after and return_at is None and len(api_gets)>=2:
                bridge._stop.set()
            if spacing and snapshot.available and snapshot.source=='SPOTIFY API':bridge._stop.set()
            if persistent401 and snapshot.available and snapshot.source=='SPOTIFY API':bridge._stop.set()

        async def sleep(seconds):
            nonlocal windows,returned,play_queued
            clock.advance(seconds)
            elapsed=clock.mono-start
            if elapsed>=1 and not returned:windows=False
            if repeat and 6<=elapsed<10:windows=returned=True
            if repeat and elapsed>=10:windows=False
            if (tap and bridge._api_waiting and bridge._source_mode=='spotify_api' and
                    bridge._source_epoch not in tap_epochs and
                    (not tap_after_empty or bridge._api_snapshot_epoch==bridge._source_epoch)):
                tap_epochs.add(bridge._source_epoch)
                if spacing:
                    def recent_start(state):
                        budget._advance(state);state['last_start']=state['logical']
                    budget.store.update(budget._factory,recent_start)
                    api._tokens['adaptive_next_allowed_at']=clock.now+.5
                accepted=bridge.control('PLAY_PAUSE');touches.append(accepted)
            if bridge._manual_refresh is not None and bridge._manual_refresh.operation is not None:
                manual_yields.append(seconds)
                if takeover_during_wait:windows=returned=True
            if play_after and not play_queued and bridge._last_snapshot and \
                    bridge._last_snapshot.source=='SPOTIFY API' and bridge._last_snapshot.available and \
                    not bridge._last_snapshot.playing and clock.mono>=bridge._manual_quiet_until:
                play_queued=True;self.assertTrue(bridge.control('PLAY_PAUSE'))
            if burst and api_gets and clock.mono<bridge._manual_quiet_until:
                self.assertFalse(bridge.control('NEXT'))
                self.assertFalse(bridge.control('PLAY_PAUSE'))
            if elapsed>185:bridge._stop.set()
            await real_sleep(0)

        with patch('time.time',new=lambda:clock.now),patch('time.monotonic',new=lambda:clock.mono), \
             patch('urllib.request.urlopen',new=http),patch('media_bridge.asyncio.sleep',new=sleep), \
             patch('media_bridge.GlobalSystemMediaTransportControlsSessionManager.request_async',
                   new_callable=AsyncMock,return_value=Mock(get_sessions=sessions)):
            # Keep the manual preemption stress case at an explicit 60s day
            # profile even when the production default becomes 5s.
            budget=ApiBudget(root/'spotify_api_budget.json',{'api_budget_day_playing_seconds':day_profile},
                             wall=lambda:clock.now,monotonic=lambda:clock.mono)
            api=SpotifyApiBridge('fixture',path,budget=budget)
            # Real mock HTTP debit before the Windows session disappears:
            # same prior automatic fallback that caused the observed 60s wait.
            api.get_playback(artwork_fallback=True)
            if block=='retry':api._record_rate_limit(400,'quota_exceeded','playback_poll')
            if block=='clock':
                budget.store.update(budget._factory,lambda state:state.update(clock_guard=state['logical']+400))
            if block=='cap':
                budget.store.update(budget._factory,lambda state:state.update(
                    minutes=[[int(state['logical']//60)*60,4000,0]]))
            if block=='short':
                budget.store.update(budget._factory,lambda state:state.update(
                    short=[[state['logical'],0] for _ in range(22)],
                    minutes=[[int(state['logical']//60)*60,22,0]]))
            api.notify_local_activity=Mock(wraps=api.notify_local_activity)
            api.get_playback=Mock(wraps=api.get_playback)
            api.begin_operation=Mock(wraps=api.begin_operation)
            api.status=Mock(wraps=api.status)
            bridge=WindowsMediaBridge(on_update=publish);bridge._spotify=api
            bridge._read_session=AsyncMock(return_value=(windows_snapshot,None))
            bridge._windows_api_artwork_due=Mock(return_value=False)
            bridge._try_api_artwork=AsyncMock(return_value=b'cover')
            original_token=api._access_token
            def token():
                nonlocal delayed,windows,returned
                if bridge._manual_refresh is not None and not delayed:
                    delayed=True
                    if slow_token:clock.advance(slow_token)
                    if return_at=='token':windows=returned=True
                return original_token()
            api._access_token=token
            if success_io:
                original_success=api._record_success
                def success():
                    if bridge._manual_refresh is not None:raise OSError('fixture')
                    original_success()
                api._record_success=success
            if block=='io':
                original_save=budget.store.save
                def save(state):
                    if bridge._manual_refresh is not None:raise __import__('api_budget').BudgetWait(60,'history_io')
                    original_save(state)
                budget.store.save=save
            asyncio.run(bridge._run())
            view=budget.view();activity=api.notify_local_activity.call_count
        return dict(calls=calls,published=published,touches=touches,manual_times=manual_times,
                    api_gets=api_gets,wait_seen=wait_seen,view=view,bridge=bridge,oauth=oauth,
                    activity=activity,original_windows=windows_snapshot,manual_yields=manual_yields,
                    get_attempts=api.get_playback.call_count,reserve_attempts=api.begin_operation.call_count,
                    status_calls=api.status.call_count)

    def test_waiting_tap_is_one_priority_get_then_one_normal_auto(self):
        r=self.scenario()
        self.assertEqual([c[0] for c in r['calls']],['GET']*3)
        self.assertEqual(len(r['manual_times']),1)
        self.assertLess(r['manual_times'][0]-r['wait_seen'],1)
        self.assertGreaterEqual(r['api_gets'][1]-r['api_gets'][0],60)
        self.assertEqual(r['view']['long_used'],3)
        self.assertEqual(r['view']['long_auto_used'],2)
        self.assertEqual(r['view']['reserved'],0)
        self.assertEqual(r['activity'],0)
        self.assertFalse(r['view']['fast_active'])
        self.assertTrue(any(s.artist=='Tap to check status' for _,s,_ in r['published']))
        self.assertTrue(any(s.artist=='Checking status...' for _,s,_ in r['published']))
        self.assertTrue(any(s.track_key=='spotify:remote' and art==b'cover' for _,s,art in r['published']))

    def test_without_touch_initial_auto_still_waits_sixty_seconds(self):
        r=self.scenario(tap=False)
        self.assertFalse(r['manual_times'])
        self.assertGreaterEqual(r['calls'][1][2]-r['calls'][0][2],60)

    def test_pending_bursts_and_gesture_tail_cannot_play_or_skip(self):
        r=self.scenario(burst=True)
        self.assertEqual(len(r['manual_times']),1)
        self.assertTrue(all(c[0]=='GET' for c in r['calls']))
        self.assertFalse(r['bridge']._control_requests)
        self.assertFalse(r['bridge']._seek_requests)

    def test_empty_snapshot_remains_read_only_waiting(self):
        r=self.scenario(empty=True)
        self.assertTrue(r['bridge']._api_waiting)
        self.assertTrue(all(c[0]=='GET' for c in r['calls']))
        self.assertEqual(len(r['manual_times']),1)
        self.assertFalse(any(s.available and s.source=='SPOTIFY API' for _,s,_ in r['published']))

    def test_already_empty_current_api_snapshot_still_maps_tap_to_get(self):
        r=self.scenario(empty=True,tap_after_empty=True)
        self.assertEqual(len(r['manual_times']),1)
        self.assertEqual([c[0] for c in r['calls']],['GET','GET','GET'])
        self.assertLess(r['manual_times'][0]-r['api_gets'][0],1)
        self.assertTrue(r['bridge']._api_waiting)

    def test_current_paused_api_snapshot_retains_normal_play(self):
        r=self.scenario(paused=True,play_after=True)
        self.assertEqual([c[0] for c in r['calls']],['GET','GET','PUT','GET'])
        self.assertEqual(r['activity'],1)
        self.assertTrue(r['published'][-1][1].playing)
        self.assertEqual(r['view']['reserved'],0)

    def test_expired_read_during_token_preparation_never_starts_http(self):
        r=self.scenario(slow_token=4)
        self.assertFalse(r['manual_times'])
        self.assertTrue(all(c[0]=='GET' for c in r['calls']))
        self.assertGreaterEqual(r['calls'][1][2]-r['calls'][0][2],60)

    def test_returned_windows_before_start_or_response_invalidates_read(self):
        for at in ('token','response'):
            with self.subTest(at=at):
                r=self.scenario(return_at=at)
                self.assertFalse(any(s.source=='SPOTIFY API' and s.available for _,s,_ in r['published']))
                self.assertEqual(r['bridge']._current_source,'windows_spotify')
                self.assertEqual(r['published'][-1][1],r['original_windows'])
                self.assertEqual(r['view']['reserved'],0)

    def test_return_to_api_requires_new_epoch_even_with_stale_api_client_cache(self):
        r=self.scenario(repeat=True)
        self.assertEqual(len(r['manual_times']),2)
        self.assertTrue(all(c[0]=='GET' for c in r['calls']))
        self.assertEqual(r['bridge']._source_epoch,4)
        self.assertEqual(r['published'][-1][1].track_key,'spotify:remote-new-epoch')

    def test_server_retry_clock_io_and_total_cap_win_over_manual_read(self):
        for block in ('retry','clock','cap','short','io'):
            with self.subTest(block=block):
                r=self.scenario(block=block)
                self.assertFalse(r['manual_times'])
                # No manual GET was added; clocks/caps/cooldown may eventually
                # allow ordinary work only after the bounded test horizon.
                if block not in ('io','short'):self.assertEqual(len(r['calls']),1)
                self.assertFalse(any(s.artist=='Checking status...' for _,s,_ in r['published']))
                if block=='retry':
                    self.assertTrue(any(s.title=='Spotify API paused' for _,s,_ in r['published']))

    def test_real_401_refresh_uses_same_bounded_read_operation(self):
        r=self.scenario(error401=True)
        self.assertEqual(len(r['oauth']),1)
        self.assertEqual(len(r['manual_times']),2)
        self.assertTrue(all(c[0]=='GET' for c in r['calls']))
        self.assertEqual(r['view']['long_used'],4)
        self.assertEqual(r['view']['long_auto_used'],2)
        self.assertEqual(r['view']['reserved'],0)

    def test_manual_min_spacing_yields_instead_of_spinning_and_windows_can_take_over(self):
        for takeover in (False,True):
            with self.subTest(takeover=takeover):
                r=self.scenario(spacing=True,takeover_during_wait=takeover)
                self.assertTrue(r['manual_yields'])
                self.assertTrue(all(0 < duration <= .45 for duration in r['manual_yields']))
                self.assertLessEqual(r['get_attempts'],4)
                self.assertEqual(r['reserve_attempts'],1)
                self.assertLess(r['status_calls'],30)
                self.assertEqual(len(r['manual_times']),0 if takeover else 1)
                self.assertEqual(r['view']['reserved'],0)
                if takeover:self.assertEqual(r['bridge']._current_source,'windows_spotify')

    def test_same_windows_track_restores_thumbnail_after_waiting_cleared_engine_cover(self):
        from test_artwork_v2 import ArtworkV2Tests
        engine=ArtworkV2Tests().make_engine()
        bridge=WindowsMediaBridge(on_update=engine._on_media_update)
        bridge._spotify=Mock(is_ready=True)
        bridge._spotify.status.return_value={'state':'ready','local_budget':{
            'profile':'day','short_total_limit':24,'long_total_limit':4000}}
        session=Mock(source_app_user_model_id='Spotify.exe')
        session.try_get_media_properties_async=AsyncMock(return_value=NS(title='fixture',artist='fixture',
            album_artist='',album_title='',track_number=1,thumbnail=object()))
        session.get_playback_info.return_value.playback_status='PAUSED'
        session.get_timeline_properties.return_value=NS(position=dt.timedelta(seconds=3),
            end_time=dt.timedelta(seconds=180))
        with patch.object(bridge,'_read_thumbnail',new_callable=AsyncMock,return_value=b'png') as thumbnail, \
             patch.object(bridge,'_to_vinyl_rgb888',side_effect=[b'first-cover',b'restored-cover']):
            bridge._enter_source_mode('windows_spotify')
            snapshot,art=asyncio.run(bridge._read_session(session));bridge._publish(snapshot,art)
            self.assertEqual(engine._cached_artwork,b'first-cover')
            bridge._enter_source_mode('spotify_api')
            self.assertIsNone(engine._cached_artwork)
            bridge._enter_source_mode('windows_spotify')
            again,art=asyncio.run(bridge._read_session(session));bridge._publish(again,art)
            self.assertEqual(again.track_key,snapshot.track_key)
            self.assertEqual(engine._cached_artwork,b'restored-cover')
            self.assertEqual(thumbnail.await_count,2)
            self.assertFalse(bridge._windows_api_artwork_due(again,session))
        bridge._spotify.get_playback.assert_not_called()

    def test_malformed_manual_get_never_reuses_remaining_grant_for_another_read(self):
        for form in ('json','unicode','shape'):
            with self.subTest(form=form):
                r=self.scenario(read_error=form)
                self.assertEqual(len(r['manual_times']),1)
                self.assertEqual(len(r['calls']),3)
                self.assertGreaterEqual(r['api_gets'][1]-r['api_gets'][0],60)
                self.assertEqual(r['view']['reserved'],0)
                self.assertEqual(r['view']['long_used'],3)

    def test_success_metadata_io_after_read_cleans_single_slot_without_replay(self):
        r=self.scenario(success_io=True)
        self.assertEqual(len(r['manual_times']),1)
        self.assertEqual(len(r['calls']),3)
        self.assertGreaterEqual(r['api_gets'][1]-r['api_gets'][0],60)
        self.assertEqual(r['view']['reserved'],0)
        self.assertEqual(r['view']['long_used'],3)

    def test_old_async_cover_cannot_complete_in_a_new_source_epoch(self):
        bridge=WindowsMediaBridge(on_update=Mock())
        bridge._spotify=Mock()
        bridge._spotify.status.return_value={'state':'ready','local_budget':{}}
        bridge._enter_source_mode('windows_spotify')
        async def download(*args):
            bridge._enter_source_mode('spotify_api')
            return b'old-cover'
        with patch('media_bridge.asyncio.to_thread',new=download), \
             patch.object(bridge,'_to_vinyl_rgb888') as convert:
            self.assertIsNone(asyncio.run(bridge._try_api_artwork('old-track','https://fixture.invalid/cover')))
        convert.assert_not_called()
        self.assertEqual(bridge._api_artwork_complete_key,'')

    def test_persistent_401_with_pacing_can_start_at_most_two_manual_gets(self):
        r=self.scenario(persistent401=True)
        self.assertEqual(len(r['manual_times']),2)
        self.assertEqual(len(r['oauth']),1)
        self.assertGreaterEqual(r['manual_times'][1]-r['manual_times'][0],.5)
        self.assertEqual([c[0] for c in r['calls']],['GET']*4)
        self.assertEqual(r['view']['long_used'],4)
        self.assertEqual(r['view']['reserved'],0)


if __name__=='__main__':unittest.main()

"""Day-playing recovery floors with real file ledger and mock HTTP only."""
import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'companion'))
from api_budget import ApiBudget,_new_state
from spotify_api import SpotifyApiBridge,SpotifyBudgetError,SpotifyRateLimitError
from test_api_control_confirmation import Clock,Response
import test_manual_api_refresh as manual_fixture


class ActiveRecoveryTests(unittest.TestCase):
    def client(self,phase='strong',night=False,playing=True,backoff=1):
        folder=tempfile.TemporaryDirectory(dir=ROOT);self.addCleanup(folder.cleanup)
        root=Path(folder.name);clock=Clock()
        if night:clock.now=dt.datetime(2026,10,15,0,tzinfo=dt.timezone.utc).timestamp()
        state=_new_state(clock.now,clock.mono)
        state['warm_until']=clock.now+86400 if phase=='warm' else 0
        state['quota_strong']=clock.now+86400 if phase=='strong' else 0
        state['quota_soft']=clock.now+3*86400 if phase in ('strong','soft') else 0
        path=root/'spotify_api_budget.json';path.write_text(json.dumps(state))
        budget=ApiBudget(path,wall=lambda:clock.now,monotonic=lambda:clock.mono)
        for name,value in [('time.time',lambda:clock.now),('time.monotonic',lambda:clock.mono)]:
            p=patch(name,new=value);p.start();self.addCleanup(p.stop)
        api=SpotifyApiBridge('fixture',root/'tokens.json',budget=budget)
        api._tokens.update(access_token='fixture',refresh_token='fixture',expires_at=clock.now+86400,
            adaptive_interval_seconds=backoff,adaptive_safe_interval_seconds=backoff,
            adaptive_quota_recovery_until=clock.now+86400 if phase=='strong' else 0)
        calls=[]
        def http(request,**kw):
            calls.append(clock.mono);clock.advance(.12)
            data={'item':{'id':'fixture','name':'fixture','duration_ms':180000},
                  'is_playing':playing,'progress_ms':30000,'device':{'id':'fixture'}}
            return Response(json.dumps(data).encode())
        p=patch('urllib.request.urlopen',new=http);p.start();self.addCleanup(p.stop)
        return api,budget,clock,calls

    def test_active_day_uses_five_seconds_in_all_local_recovery_phases(self):
        for phase,limit in [('warm',4000),('strong',4000),('soft',6000)]:
            with self.subTest(phase=phase):
                api,budget,clock,calls=self.client(phase)
                api.get_playback();api.notify_local_activity()
                self.assertEqual(api.poll_interval_seconds(),5)
                self.assertEqual(budget.view()['long_total_limit'],limit)
                self.assertFalse(budget.view()['fast_active'])
                clock.advance(api.poll_delay_seconds());api.get_playback()
                self.assertAlmostEqual(calls[-1]-calls[-2],5.12,places=5)
                self.assertEqual(budget.view()['long_auto_used'],2)
                self.doCleanups()

    def test_night_and_idle_keep_their_recovery_floors(self):
        for phase,night,playing,expected in [('strong',True,True,60),('strong',False,False,60),
            ('soft',True,True,30),('soft',False,False,30),('warm',True,True,30),('warm',False,False,30)]:
            with self.subTest(phase=phase,night=night,playing=playing):
                api,budget,clock,calls=self.client(phase,night,playing)
                api.get_playback()
                self.assertEqual(api.poll_interval_seconds(idle=not playing),expected)
                self.assertGreaterEqual(api.poll_delay_seconds(idle=not playing),expected-.001)
                self.doCleanups()

    def test_higher_adaptive_start_gate_still_wins(self):
        api,budget,clock,calls=self.client(backoff=20)
        api.get_playback()
        self.assertEqual(api.poll_interval_seconds(),20)
        clock.advance(api.poll_delay_seconds());api.get_playback()
        self.assertGreaterEqual(calls[1]-calls[0],20)

    def test_real_retry_and_reduced_total_auto_caps_cannot_be_bypassed(self):
        api,budget,clock,calls=self.client()
        api.get_playback();api._record_rate_limit(400,'quota_exceeded','playback_poll')
        for request in (api.get_playback,lambda:api.begin_operation('control')):
            with self.assertRaises(SpotifyRateLimitError):request()
        self.assertEqual(len(calls),1)
        clock.advance(401)
        budget.configure({'api_budget_long_total':100,'api_budget_long_auto':90})
        def fill(state,count):
            budget._advance(state)
            state['minutes']=[[int(state['logical']//60)*60,count,0]]
        budget.store.update(budget._factory,lambda s:fill(s,45))
        with self.assertRaises(SpotifyBudgetError):api.get_playback()
        operation=api.begin_operation('control')
        api.get_playback(urgent=True,operation=operation);api.finish_operation(operation)
        self.assertEqual(budget.view()['long_auto_used'],45)
        self.assertEqual(budget.view()['long_used'],46)
        budget.store.update(budget._factory,lambda s:fill(s,50))
        with self.assertRaises(SpotifyBudgetError):api.begin_operation('control')
        self.assertEqual(len(calls),2)

    def test_pressure_and_tail_remain_higher_than_five_seconds(self):
        api,budget,clock,calls=self.client()
        minute=int(clock.now//60)*60
        budget.store.update(budget._factory,lambda s:s.update(minutes=[[minute,1800,0]]))
        self.assertEqual(budget.view()['interval_seconds'],7.5)
        budget.store.update(budget._factory,lambda s:s.update(minutes=[[minute,2880,0]]))
        self.assertGreater(budget.view()['interval_seconds'],15)
        self.assertEqual(budget.view()['long_auto_limit'],3600)

    def test_full_worker_manual_stays_one_shot_and_normal_active_auto_is_five(self):
        case=manual_fixture.ManualRefreshTests()
        try:
            r=case.scenario(day_profile=5)
            self.assertEqual(len(r['manual_times']),1)
            self.assertEqual([c[0] for c in r['calls']],['GET']*3)
            self.assertGreaterEqual(r['api_gets'][1]-r['api_gets'][0],5)
            self.assertLess(r['api_gets'][1]-r['api_gets'][0],6)
            self.assertEqual(r['view']['reserved'],0)
            self.assertEqual(r['activity'],0)
            self.assertFalse(r['view']['fast_active'])
        finally:case.doCleanups()


if __name__=='__main__':unittest.main()

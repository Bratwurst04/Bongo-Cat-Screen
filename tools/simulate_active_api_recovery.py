"""Actual frozen 137 client/policy versus current production on mock 72h traces."""
import bisect
import datetime as dt
import hashlib
import json
from pathlib import Path
import random
import statistics
import sys
import tempfile
import types
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'companion'))
import api_budget as policy
from spotify_api import SpotifyApiBridge,SpotifyPacingError
DAY=86400.0
START=dt.datetime(2026,10,15,10,46,36,tzinfo=dt.timezone.utc).timestamp()
WARM=dt.datetime(2026,10,16,9,39,30,tzinfo=dt.timezone.utc).timestamp()
STRONG=dt.datetime(2026,10,15,13,32,48,tzinfo=dt.timezone.utc).timestamp()
SOFT=dt.datetime(2026,10,17,13,32,48,tzinfo=dt.timezone.utc).timestamp()

def frozen_module(stem):
    path=ROOT/'build/active-api-recovery-2026-10-15/baseline/companion'/(stem+'.py')
    name='active_recovery_frozen_'+stem
    module=types.ModuleType(name);module.__file__=str(path);sys.modules[name]=module
    exec(compile(path.read_bytes(),str(path),'exec'),module.__dict__)
    return module


old_policy=frozen_module('api_budget')
old_client=frozen_module('spotify_api')
old_client.ApiBudget=old_policy.ApiBudget
old_client.BudgetWait=old_policy.BudgetWait
old_client.OperationGrant=old_policy.OperationGrant


class Clock:
    def __init__(self):self.at=0.0
    def wall(self):return START+self.at
    def mono(self):return 1000+self.at
    def advance(self,seconds):self.at+=seconds


class Response:
    def __init__(self,data):self.data=data
    def __enter__(self):return self
    def __exit__(self,*a):return False
    def read(self):return self.data


def summarize(values):
    if not values:return dict(median=None,p95=None,max=None)
    ordered=sorted(values)
    return dict(median=round(statistics.median(values),3),
        p95=round(ordered[min(len(ordered)-1,int(.95*len(ordered)))],3),max=round(max(values),3))


def run(proposed,trace):
    clock=Clock();starts=[];ends=[];previous_mode=None;gaps=[];day_gaps=[];night_gaps=[]
    pressure=full=0.0;max_total=74;max_auto=61;short_max=0;max_interval=0
    rng=random.Random(421);changes=[];event=137.0
    def local_hour(at):return int(((START+at+7200)%DAY)//3600)
    def mode(at):
        hour=local_hour(at)
        if trace=='continuous':return 'playing'
        return 'playing' if 6<=hour<8 or 12<=hour<14 else 'idle' if 2<=hour<6 else 'windows'
    while event<3*DAY:
        if mode(event)=='playing':changes.append(event)
        event+=rng.uniform(151,229)
    policy_module=policy if proposed else old_policy
    state=policy_module._new_state(clock.wall(),clock.mono())
    state.update(warm_until=WARM,quota_strong=STRONG,quota_soft=SOFT,
        minutes=[[int((START-60)//60)*60,61,13]],last_auto=START-60,last_start=START-1)
    budget=policy_module.ApiBudget(Path('unused'),
        {'api_idle_interval_seconds':15},store=policy_module.MemoryBudgetStore(state),
        wall=clock.wall,monotonic=clock.mono)
    def http(request,**kw):
        at=clock.at;starts.append(at);clock.advance(.12);ends.append(clock.at)
        playing=mode(at)=='playing';seq=bisect.bisect_right(changes,at)
        data={'item':{'id':str(seq),'name':'fixture','duration_ms':240000,'artists':[]},
              'device':{'id':'fixture'},'progress_ms':0,'is_playing':playing} if playing else {'item':None,'is_playing':False}
        return Response(json.dumps(data).encode())
    with tempfile.TemporaryDirectory(dir=ROOT) as folder,patch('time.time',new=clock.wall), \
         patch('time.monotonic',new=clock.mono),patch('urllib.request.urlopen',new=http):
        client_class=SpotifyApiBridge if proposed else old_client.SpotifyApiBridge
        pacing_error=SpotifyPacingError if proposed else old_client.SpotifyPacingError
        client=client_class('fixture',Path(folder)/'tokens.json',budget=budget)
        client._save_tokens=lambda:None
        client._tokens.update(access_token='fixture',refresh_token='fixture',expires_at=START+10*DAY,
            adaptive_interval_seconds=1.0,adaptive_safe_interval_seconds=.5,
            adaptive_quota_recovery_until=STRONG,adaptive_last_limit_reason='quota_exceeded')
        next_poll=0.0;last_view={};last_at=0.0
        while clock.at<3*DAY:
            boundary=(int((START+clock.at)//3600)+1)*3600-START
            at=min(max(clock.at,next_poll),boundary,3*DAY)
            elapsed=at-clock.at
            if last_view.get('pressure',0)>=.5:pressure+=elapsed
            if last_view.get('wait_reason')=='long_budget':full+=elapsed
            clock.advance(elapsed)
            if clock.at>=3*DAY:break
            current=mode(clock.at)
            if current=='windows':
                next_poll=boundary;last_view=budget.view();previous_mode=current;continue
            if clock.at+1e-7<next_poll:continue
            before=len(starts)
            try:
                playback,_=client.get_playback();delay=client.poll_delay_seconds(idle=not playback or not playback['playing'])
            except pacing_error as exc:delay=exc.wait_seconds
            if len(starts)>before and len(starts)>1:
                a,b=starts[-2:]
                points=[a,b,*range((int((START+a)//3600)+1)*3600-int(START),int(b)+1,3600)]
                if all(mode(t)=='playing' for t in points):
                    gap=b-a;gaps.append(gap)
                    (night_gaps if local_hour(b)<8 else day_gaps).append(gap)
            next_poll=clock.at+max(.05,delay)
            last_view=budget.view(idle=not client._last_is_playing)
            assert last_view['long_used']<=last_view['long_total_limit']
            assert last_view['long_auto_used']<=last_view['long_auto_limit']
            assert last_view['short_used']<=last_view['short_total_limit']
            assert last_view['short_auto_used']<=last_view['short_auto_limit']
            max_total=max(max_total,last_view['long_used']);max_auto=max(max_auto,last_view['long_auto_used'])
            short_max=max(short_max,last_view['short_used']);max_interval=max(max_interval,last_view['interval_seconds'])
            previous_mode=current
    latency={}
    for event in changes:
        index=bisect.bisect_left(starts,event)
        if index<len(ends):latency.setdefault('night' if local_hour(event)<8 else 'day',[]).append(ends[index]-event)
    return dict(policy='proposal' if proposed else 'current137',trace=trace,hours=72,actual_http=len(starts),
        ledger_max_rolling24h_total=max_total,ledger_max_rolling24h_auto=max_auto,max_short_used=short_max,
        max_actual_playing_http_gap_seconds=round(max(gaps),3),
        max_day_http_gap_seconds=round(max(day_gaps),3),max_night_http_gap_seconds=round(max(night_gaps),3),
        pressure_hours=round(pressure/3600,3),full_budget_hours=round(full/3600,3),
        discovery_seconds={key:summarize(values) for key,values in latency.items()})


if __name__=='__main__':
    rows=[]
    for trace in ('mixed','continuous'):
        for proposed in (False,True):
            row=run(proposed,trace);rows.append(row);print(json.dumps(row),flush=True)
    result=dict(classification='frozen137 versus actual production client/policy; mock HTTP/virtual time; no real profile changes',
        start='2026-10-15 12:46:36 Europe/Stockholm',seed_total=74,seed_auto=61,
        warm_until='2026-10-16 11:39:30 Europe/Stockholm',strong_until='2026-10-15 15:32:48 Europe/Stockholm',
        soft_until='2026-10-17 15:32:48 Europe/Stockholm',
        assumptions='seeded costs in one prior minute; no known per-call real history; mixed local06-08/12-14 playing,02-06 idle,restWindows;120msHTTP',
        source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest().upper()
                       for name in ('companion/api_budget.py','companion/spotify_api.py')},results=rows)
    (ROOT/'build/active-api-recovery-2026-10-15/final-comparison.json').write_text(json.dumps(result,indent=2)+'\n')

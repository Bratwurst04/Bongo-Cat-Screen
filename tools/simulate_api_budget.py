"""Real API client + mocked HTTP on virtual traces; no Spotify/profile access."""
import bisect
import datetime as dt
import importlib.util
import json
from pathlib import Path
import statistics
import random
import sys
import tempfile
from unittest.mock import patch
import urllib.parse

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'companion'))
from api_budget import ApiBudget, MemoryBudgetStore, _new_state
from spotify_api import SpotifyApiBridge, SpotifyPacingError

START=dt.datetime(2026,10,13,22,tzinfo=dt.timezone.utc).timestamp() # Stockholm 14 Oct 00:00
DAY=86400.0


class Clock:
    def __init__(self,offset=0):self.elapsed=0.0;self.origin=START+offset
    def wall(self):return self.origin+self.elapsed
    def mono(self):return 1000+self.elapsed
    def advance(self,seconds):self.elapsed+=seconds


class Response:
    def __init__(self,payload):self.payload=payload
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self):return self.payload


def summary(values):
    if not values:return dict(median=None,p95=None,max=None)
    ordered=sorted(values)
    return dict(median=round(statistics.median(ordered),3),
                p95=round(ordered[min(len(ordered)-1,int(len(ordered)*0.95))],3),max=round(max(ordered),3))


def run(name,policy,*,day_seconds=5,hours=72,typing=False,warm=False):
    clock=Clock(428 if name=='incident_night' else 0);duration=hours*3600
    if name=='incident_night':duration=6067
    def mode(at):
        if name=='incident_night':return 'idle' if at<555 else 'playing'
        hour=(at%DAY)/3600
        if name=='incident_like_daily':
            return 'playing' if hour<2 or 12<=hour<14 else 'idle' if 2<=hour<6 else 'windows'
        if name=='paused':return 'idle'
        if name=='idle_resume':return 'idle' if at<22517 else 'playing'
        return 'playing'
    rng=random.Random(421)
    if name=='incident_night':changes=[555+(5446*i/26) for i in range(27)]
    elif name=='paused':changes=[]
    elif name=='idle_resume':changes=[22517]
    else:
        changes=[];event=137.0
        while event<duration:
            changes.append(event);event+=rng.uniform(151,229)
    changes=[event for event in changes if mode(event)=='playing']
    starts=[];reads=[];seen=[];pressure_seconds=full_seconds=fast_count=0.0
    config={'api_min_interval_seconds':0.5,'api_initial_interval_seconds':1,'api_idle_interval_seconds':15,
            'api_budget_day_playing_seconds':day_seconds}
    budget=None
    if policy=='budget':
        state=_new_state(clock.wall(),clock.mono())
        if not warm:state['warm_until']=0
        budget=ApiBudget(Path('unused'),config,store=MemoryBudgetStore(state),wall=clock.wall,monotonic=clock.mono)
        client_class=SpotifyApiBridge
        pacing_error=SpotifyPacingError
    else:
        spec=importlib.util.spec_from_file_location('budget_sim_legacy',ROOT/'build/api-budget-2026-10-14/baseline/companion/spotify_api.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        client_class=module.SpotifyApiBridge;pacing_error=module.SpotifyPacingError
    def http(request,**kwargs):
        at=clock.elapsed;starts.append(at)
        seq=bisect.bisect_right(changes,at)
        current=mode(at)
        clock.advance(0.12)
        if request.method!='GET':return Response(b'')
        reads.append((clock.elapsed,seq));seen.append(seq)
        if current=='idle':payload={'item':None,'is_playing':False}
        else:payload={'item':{'id':str(seq),'name':'fixture','artists':[],'duration_ms':240000},
                      'device':{'id':'fixture','is_restricted':False},'progress_ms':0,'is_playing':True}
        return Response(json.dumps(payload).encode())
    with tempfile.TemporaryDirectory(dir=ROOT) as folder, \
         patch('time.time',new=clock.wall),patch('time.monotonic',new=clock.mono), \
         patch('urllib.request.urlopen',new=http):
        client=client_class('fixture',Path(folder)/'tokens.json',config,**({'budget':budget} if budget else {}))
        client._save_tokens=lambda:None
        client._tokens.update(access_token='fixture',refresh_token='fixture',expires_at=clock.wall()+10*DAY)
        next_attempt=0.0;next_key=1.0;can_wake=False;last_view={}
        while clock.elapsed<duration:
            next_boundary=(int(clock.elapsed//3600)+1)*3600
            at=min(next_attempt,next_key if typing else duration,next_boundary,duration)
            if at<clock.elapsed:at=clock.elapsed
            gap=at-clock.elapsed
            if last_view.get('pressure',0)>=0.5:pressure_seconds+=gap
            if last_view.get('wait_reason')=='long_budget':full_seconds+=gap
            clock.advance(gap)
            if clock.elapsed>=duration:break
            if typing and clock.elapsed>=next_key-1e-7:
                if budget:client.notify_local_activity()
                next_key=int(clock.elapsed)+1
                if can_wake:next_attempt=min(next_attempt,clock.elapsed)
            if mode(clock.elapsed)=='windows':
                if budget:last_view=budget.view()
                next_attempt=next_boundary
                continue
            if clock.elapsed+1e-7<next_attempt:continue
            try:
                playback,_=client.get_playback()
                delay=client.poll_delay_seconds(idle=not playback or not playback['playing'])
            except pacing_error as exc:
                delay=exc.wait_seconds
            next_attempt=clock.elapsed+max(0.05,delay)
            if budget:
                last_view=budget.view(idle=not client._last_is_playing)
                can_wake=last_view.get('activity_wake_allowed',False)
        if budget:
            fast_count=len(budget.store.state['fast']) # current final-hour history only
    probe_times=[t for t,_ in reads]
    event_latencies=[];pending=[];latencies_by_profile={}
    for event in changes:
        if mode(event)=='windows':continue
        index=bisect.bisect_left(starts,event)
        if index<len(probe_times):
            latency=probe_times[index]-event;event_latencies.append(latency)
            profile='night_playing' if event%DAY<8*3600 else 'day_playing'
            latencies_by_profile.setdefault(profile,[]).append(latency)
        else:pending.append(duration-event)
    latest=[];previous=-1;currently_seen=set()
    for at,seq in reads:
        if seq and seq==bisect.bisect_right(changes,at):currently_seen.add(seq)
        if seq>previous and seq>0:latest.append(at-changes[seq-1])
        previous=seq
    def continuous_playing(a,b):
        points=[a,b,*range((int(a//3600)+1)*3600,int(b)+1,3600)]
        return all(mode(t)=='playing' for t in points)
    gaps=[b-a for a,b in zip(starts,starts[1:]) if continuous_playing(a,b)]
    from collections import deque
    short=deque();long=deque();max30=max24=0
    for at in starts:
        while short and short[0]<=at-30:short.popleft()
        while long and long[0]<=at-DAY:long.popleft()
        short.append(at);long.append(at);max30=max(max30,len(short));max24=max(max24,len(long))
    return dict(trace=name,policy=policy,day_seconds=day_seconds if budget else None,hours=duration/3600,
        startup_history='unknown/warm' if warm and budget else 'synthetic complete/empty',actual_http=len(starts),
        max_rolling30s=max30,max_rolling24h=max24,probe_latency_seconds=summary(event_latencies),
        min_actual_http_start_gap_seconds=round(min(b-a for a,b in zip(starts,starts[1:])),6) if len(starts)>1 else None,
        latest_visible_track_latency_seconds=summary(latest),pending_changes=len(pending),
        probe_latency_by_profile={profile:summary(values) for profile,values in latencies_by_profile.items()},
        observed_current_changes=len(currently_seen),scheduled_mobile_changes=len(changes),
        pending_latency_lower_bound_max=max(pending) if pending else 0,
        superseded_changes=len([e for e in changes if mode(e)!='windows'])-len(set(seen)-{0}),
        pressure_hours=round(pressure_seconds/3600,4),full_budget_hours=round(full_seconds/3600,4),
        max_playing_http_gap_seconds=round(max(gaps),3) if gaps else 0,
        final_hour_fast_calls=fast_count,
        note='Synthetic modes/changes and 120ms HTTP; next-probe latency includes superseded changes; no real Spotify 429 inference')


if __name__=='__main__':
    out=ROOT/'build/api-budget-2026-10-14/simulation-final.json'
    results=[]
    for trace,typing,warm in [('incident_night',False,False),('incident_like_daily',False,False),
                              ('long_mobile',False,False),('long_typing',True,False),
                              ('paused',False,False),('idle_resume',False,False),('warm_start',False,True)]:
        for policy,day in [('legacy',5),('budget',5),('budget',10)]:
            row=run(trace,policy,day_seconds=day,typing=typing,warm=warm)
            results.append(row)
            print(json.dumps({k:row[k] for k in ('trace','policy','day_seconds','actual_http','probe_latency_seconds','pressure_hours','full_budget_hours','max_rolling24h')}),flush=True)
    import hashlib
    sources={str(path.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(path.read_bytes()).hexdigest().upper()
             for path in [ROOT/'companion/api_budget.py',ROOT/'companion/spotify_api.py',Path(__file__)]}
    out.write_text(json.dumps({'classification':'mock HTTP/virtual clock simulation, not runtime evidence',
                              'source_hashes':sources,'results':results},indent=2)+'\n')

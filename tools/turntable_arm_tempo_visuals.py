"""New, immutable preview revisions using C++ timing exports and primitives."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
from turntable_paw_host import load_host, Frame, timings
import turntable_paw_visuals as prior


def export(revision):
    assert re.fullmatch(r'r[1-9][0-9]*',revision)
    out=ROOT/'visuals/turntable-arm-tempo-2026-10-18'/revision
    assert not out.exists(),'Choose a fresh revision; preserve previews'
    out.mkdir(parents=True)
    h=load_host();T=timings(h);step=T['frame_ms']
    albums=[prior.legacy.album(c) for c in ((170,40,110),(30,100,180),(220,120,20))]
    scenarios=['paw-flip','focus-change','complete-change','focus-complete-change','paused-change',
               'late-cover','rapid-skips','play-pause-progress','focus-play-pause']
    all_states={};contact_times={};overview=[]
    for name in scenarios:
        playing=name!='paused-change';compact=name.startswith('focus');full='complete-change' in name
        motion='play-pause' not in name
        prior.warm(h,playing);base=1000;art=albums[0]
        if full:
            spacing=T['normal_ms']+400
            for n in range(4):
                at=1000+n*spacing;h.tt_event(1,n+1,at,True);h.tt_event(2,102+n,at,True)
                for now in range(at,at+T['normal_ms']+201,step):h.tt_frame(now,True,Frame())
                h.tt_event(3,0,at+T['normal_ms']+220,False)
            base=1000+4*spacing
        end=T['full_ms' if full else 'normal_ms'];arrival=end+200 if name=='late-cover' else T['lift_end']+40
        duration=(arrival+T['reveal_ms']+200 if name=='late-cover' else end+400) if motion else 4000
        if motion:h.tt_event(1,9,base,True);h.tt_event(2,106 if full else 102,base,True)
        else:playing=False;h.tt_playback(False,0,200)
        frames=[];states=[];angle=0
        for ms in range(0,duration+1,step):
            now=base+ms;position=0;track_duration=200
            if not motion:
                if ms==100:playing=True
                if ms==1900:playing=False
                if ms==2400:playing=True
                position=0 if ms<1000 else 100 if ms<2400 else 160
                track_duration=0 if ms>=3300 else 200
                h.tt_playback(playing,position,track_duration)
            if name=='rapid-skips':
                if ms in (200,400,600):
                    h.tt_event(1,ms,now,True);h.tt_event(2,102+ms//200,now,True)
                    art=albums[(ms//200)%3]
                if ms==300:playing=False
                if ms==780:playing=True
                h.tt_playback(playing,0,200)
            if motion and ms==arrival:h.tt_event(3,0,now,True)
            f=Frame();h.tt_frame(now,True,f)
            if playing and not f[10]:angle=(angle+2)%360
            frames.append(prior.scene(h,f,art,compact,playing,'Nästa låt' if motion else 'Dö ung',angle,position,track_duration))
            states.append(dict(ms=ms,frame=list(f),playing=playing,compact=compact))
        frames[0].save(out/(name+'.gif'),save_all=True,append_images=frames[1:],duration=step,loop=0,disposal=2)
        lower_begin=T['full_in_end' if full else 'flip_end'];lower_end=T['full_lower_end' if full else 'lower_end']
        selected=([0,100,300,1000,1800,1900,2100,2400,2600,3200,3600,4000] if not motion else
            [0,T['reach_end'],T['grip_end'],(T['grip_end']+T['lift_end'])//2,T['lift_end'],
             T['full_out_end'] if full else (T['lift_end']+T['flip_end'])//2,
             lower_begin,(lower_begin+lower_end)//2,lower_end+20,
             T['full_settle_end' if full else 'settle_end'],T['full_withdraw_end' if full else 'withdraw_end'],duration])
        if name=='late-cover':selected[-3:]=[arrival,arrival+T['reveal_ms']//2,duration]
        indices=[min(len(frames)-1,round(ms/step)) for ms in selected]
        sheet=Image.new('RGB',(720,4*344),(29,34,40))
        for i,index in enumerate(indices):
            x=i%3*240;y=i//3*344
            ImageDraw.Draw(sheet).text((x+4,y+3),f'{name} {index*step} ms',fill='white')
            sheet.paste(frames[index],(x,y+22))
        sheet.save(out/(name+'.png'));overview.append(frames[T['grip_end']//step]);all_states[name]=states
        contact_times[name]=[index*step for index in indices]
    overview_image=Image.new('RGB',(720,3*344),(29,34,40))
    for i,(name,im) in enumerate(zip(scenarios,overview)):
        x=i%3*240;y=i//3*344;ImageDraw.Draw(overview_image).text((x+4,y+3),name,fill='white')
        overview_image.paste(im,(x,y+22))
    overview_image.save(out/'overview.png')
    html='''<!doctype html><meta charset="utf-8"><title>Sammanhängande kattarm och lugnare lyft</title>
<style>body{background:#15191e;color:#eee;font:16px system-ui;margin:24px}main{display:flex;flex-wrap:wrap;gap:20px}section{border:1px solid #46515b;padding:12px}img{image-rendering:pixelated;width:240px}a{color:#7cddd0}strong{color:#ffcf6c}</style>
<h1>Kattarm och lugnare lyft</h1><p><strong>SIMULERAT, EJ SKÄRMPROVAT.</strong> Faktisk C++-state, tider, projektion och ritprimitiver. Hostrasterisering/tempo är inte uppmätt LVGL/TFT.</p><main>'''
    for name in scenarios:html+=f'<section><h2>{name}</h2><img src="{name}.gif"><p><a href="{name}.png">Förloppsbilder</a></p></section>'
    (out/'index.html').write_text(html+'</main>',encoding='utf-8')
    files=['src/media_turntable.h','src/media_record_flip.h','src/bongo_cat_featured.inc',
           'src/focus_countdown_layout.h','src/media_swedish_font.h','tests/turntable_paw_host.cpp',
           'tests/turntable_paw_host.py','tools/turntable_paw_visuals.py','tools/record_flip_visuals.py',
           'tools/turntable_arm_tempo_visuals.py','visuals/sprites/twopawsup.png']
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest().upper()
    manifest=dict(classification='SIMULATED actual native C++ state/disc/primitives; not physical TFT',
        timings_ms=T,contact_times_ms=contact_times,
        source_sha256={n:sha(ROOT/n) for n in files},
        output_sha256={p.name:sha(p) for p in out.iterdir() if p.is_file()},states=all_states,
        limitations=['PIL rasterisation can differ from LVGL by edge pixels.',
            'Prior source-derived UI/glyph composition; scripted playback inputs, not live Spotify.',
            'No hardware timing, touch, power or memory acceptance inferred.'])
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(out),scenarios=len(scenarios),timings=T)))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--revision',default='r1')
    export(parser.parse_args().revision)

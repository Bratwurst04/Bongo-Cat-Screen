"""Source-driven simulation: native scene/disc/primitives + existing source-derived UI/glyphs."""
import argparse
import ctypes
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
from turntable_paw_host import load_host, Frame, Pixels
import record_flip_visuals as legacy

PALETTE=legacy.PALETTE
OVERLAY=(ctypes.c_ushort*5)(*(legacy.rgb565(c) for c in
    ((0,0,0),(255,255,255),(189,198,204),(110,121,131),(255,131,170))))

@lru_cache(maxsize=65536)
def rgba(raw):
    p=((raw&255)<<8)|(raw>>8)
    return (((p>>11)&31)*255//31,((p>>5)&63)*255//63,(p&31)*255//31,0 if raw==PALETTE[0] else 255)

@lru_cache(maxsize=32)
def background(compact,playing,title):
    return legacy.scene(None,Pixels(*([PALETTE[0]]*(112*112))),compact=compact,
                        title=title,artist='Bongo åäö',paused=not playing)

def scene(host,f,art,compact,playing,title,angle,position,duration):
    image=background(compact,playing,title).copy()
    # Immediate metadata/progress uses the same source glyphs and layout; arm
    # easing is deliberately independent from the freshly displayed time.
    source=legacy.v.FIRMWARE.read_text(encoding='utf-8');body=legacy.v.section(source,'createMediaScreen')
    parent=legacy.v.pos(body,'info_panel');card=legacy.v.size(body,'info_panel')
    px,py=legacy.v.pos(body,'media_progress_bar');pw,ph=legacy.v.size(body,'media_progress_bar')
    px+=parent[0]+1;py+=parent[1]+1
    ui=ImageDraw.Draw(image);ui.rounded_rectangle((px,py,px+pw-1,py+ph-1),radius=3,fill=(52,57,64))
    progress=min(position,duration)/duration if duration else 0
    if progress:ui.rounded_rectangle((px,py,px+max(1,int(pw*progress))-1,py+ph-1),radius=3,fill=(30,215,96))
    ui.rectangle((parent[0]+3,parent[1]+70,parent[0]+card[0]-4,parent[1]+85),fill=(21,25,30))
    left=f'{position//60}:{position%60:02d}';right=f'{duration//60}:{duration%60:02d}'
    legacy.media_text(image,(parent[0]+11,parent[1]+73),left,10,(199,204,210))
    legacy.media_text(image,(parent[0]+card[0]-11-legacy.media_width(right,10),parent[1]+73),right,10,(199,204,210))
    pixels=Pixels()
    s=round(math.sin(math.radians(angle))*32768);c=round(math.cos(math.radians(angle))*32768)
    assert host.tt_render(pixels,112*112,art,f,s,c,PALETTE)
    record=Image.new('RGBA',(112,112));record.putdata([rgba(p) for p in pixels])
    g=(ctypes.c_int*10)();host.tt_geometry(f,compact,g)
    zoom=g[2];size=112*zoom//256;record=record.resize((size,size),Image.Resampling.NEAREST)
    # C++ integer division truncates toward zero, including negative lift/x.
    image.paste(record,(g[0]-size//2+int(f[2]*zoom/256),g[1]-size//2+int(f[3]*zoom/256)),record)
    draw=ImageDraw.Draw(image)
    for paw in (False,True):
        primitives=(ctypes.c_int*(64*7))()
        count=host.tt_primitives(f,compact,paw,primitives,OVERLAY)
        for i in range(count):
            shape,x1,y1,x2,y2,color,width=primitives[i*7:i*7+7]
            if shape==0:draw.rectangle((x1,y1,x2,y2),fill=rgba(color)[:3])
            else:draw.line((x1,y1,x2,y2),fill=rgba(color)[:3],width=width)
    return image

def warm(host,playing=True):
    host.tt_reset();host.tt_playback(playing,0,200);host.tt_frame(0,True,Frame())
    host.tt_event(2,101,0,False);host.tt_event(3,0,0,False);host.tt_frame(0,True,Frame())

def export(revision):
    assert re.fullmatch(r'r[1-9][0-9]*',revision)
    out=ROOT/'visuals/turntable-paw-2026-10-18'/revision
    assert not out.exists(),'Preserve existing reviewed previews; choose a new revision'
    out.mkdir(parents=True)
    host=load_host();albums=[legacy.album(c) for c in ((170,40,110),(30,100,180),(220,120,20))]
    scenarios=['play-pause-progress','focus-play-pause','paw-flip','paused-change',
               'complete-change','late-cover','rapid-skips','focus-change']
    all_states={};overview=[]
    for name in scenarios:
        playing=name!='paused-change';compact=name.startswith('focus')
        warm(host,playing);base=1000;duration=1800;art=albums[0]
        if name=='complete-change':
            for n in range(4):
                at=1000+n*2000;host.tt_event(1,n+1,at,True);host.tt_event(2,102+n,at,True)
                for now in range(at,at+1601,20):host.tt_frame(now,True,Frame())
                host.tt_event(3,0,at+1700,False)
            base=10000
        motion=name not in ('play-pause-progress','focus-play-pause')
        if motion:
            host.tt_event(1,9,base,True);host.tt_event(2,106 if name=='complete-change' else 102,base,True)
        else:duration=4000;playing=False;host.tt_playback(False,0,200)
        frames=[];states=[];angle=0
        for ms in range(0,duration+1,20):
            now=base+ms
            position=0;track_duration=200
            if not motion:
                if ms==100:playing=True
                if ms==1900:playing=False
                if ms==2400:playing=True
                position=0 if ms<1000 else 100 if ms<2400 else 160
                track_duration=0 if ms>=3300 else 200
                host.tt_playback(playing,position,track_duration)
            if name=='rapid-skips':
                if ms in (200,400,600):
                    host.tt_event(1,ms,now,True);host.tt_event(2,102+ms//200,now,True)
                    art=albums[(ms//200)%3]
                if ms==300:playing=False
                if ms==780:playing=True
                host.tt_playback(playing,0,200)
            if motion and ms==(1300 if name=='late-cover' else 560):host.tt_event(3,0,now,True)
            f=Frame();host.tt_frame(now,True,f)
            if playing and not f[10]:angle=(angle+2)%360
            image=scene(host,f,art,compact,playing,'Nästa låt' if motion else 'Dö ung',angle,position,track_duration)
            frames.append(image);states.append(dict(ms=ms,frame=list(f),playing=playing,compact=compact))
        frames[0].save(out/(name+'.gif'),save_all=True,append_images=frames[1:],duration=20,loop=0,disposal=2)
        selected=[0,8,15,24,36,50,65,min(len(frames)-1,74),len(frames)-1]
        sheet=Image.new('RGB',(720,3*344),(29,34,40))
        for i,index in enumerate(selected):
            x=(i%3)*240;y=(i//3)*344
            ImageDraw.Draw(sheet).text((x+4,y+3),f'{name} {index*20} ms',fill='white')
            sheet.paste(frames[index],(x,y+22))
        sheet.save(out/(name+'.png'));overview.append(frames[24]);all_states[name]=states
    overview_image=Image.new('RGB',(720,3*344),(29,34,40))
    for i,(name,im) in enumerate(zip(scenarios,overview)):
        x=i%3*240;y=i//3*344;ImageDraw.Draw(overview_image).text((x+4,y+3),name,fill='white');overview_image.paste(im,(x,y+22))
    overview_image.save(out/'overview.png')
    html='''<!doctype html><meta charset="utf-8"><title>Simulerad tonarm och Bongo-tass</title>
<style>body{background:#15191e;color:#eee;font:16px system-ui;margin:24px}main{display:flex;flex-wrap:wrap;gap:20px}section{border:1px solid #46515b;padding:12px}img{image-rendering:pixelated;width:240px}a{color:#7cddd0}strong{color:#ffcf6c}</style>
<h1>Tonarm + Bongo-tass</h1><p><strong>SIMULERAT, EJ SKÄRMPROVAT.</strong> Faktisk C++-state, projektion och ritprimitiver; källstyrd tidigare UI/glyphbakgrund. Hostrasterisering/tempo är inte uppmätt LVGL/TFT.</p><main>'''
    for name in scenarios:html+=f'<section><h2>{name}</h2><img src="{name}.gif"><p><a href="{name}.png">Förloppsbilder</a></p></section>'
    (out/'index.html').write_text(html+'</main>',encoding='utf-8')
    files=['src/media_turntable.h','src/media_record_flip.h','src/bongo_cat_featured.inc',
           'src/focus_countdown_layout.h','src/media_swedish_font.h','tests/turntable_paw_host.cpp',
           'tests/turntable_paw_host.py','tools/turntable_paw_visuals.py','tools/record_flip_visuals.py',
           'visuals/sprites/twopawsup.png']
    manifest=dict(classification='SIMULATED actual native C++ state/disc/primitives; not physical TFT',
                  frame_ms=20,normal_change_ms=1080,full_change_ms=1450,reveal_ms=180,
                  source_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest().upper() for n in files},
                  output_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest().upper() for p in out.iterdir() if p.is_file()},
                  states=all_states,limitations=['UI background/glyph composition reused from source-derived prior fixtures.',
                    'PIL rasterises shared native line/rectangle primitives; LVGL may differ by edge pixels.',
                    'Playback position corrections in preview are scripted actual state inputs, not live Spotify.',
                    'No TFT frame rate, power, touch or hardware acceptance is inferred.'])
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(out),scenarios=len(scenarios),files=len(manifest['output_sha256']))))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--revision',default='r1')
    export(parser.parse_args().revision)

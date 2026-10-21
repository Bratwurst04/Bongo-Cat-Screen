"""Real C++ two-slot receiver/state/render, scripted RGB albums and timings."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools'),str(ROOT/'companion')]
from turntable_face_host import load_host,frame,snapshot,transfer,Frame
import turntable_paw_visuals as prior

def album(color,label):
    image=Image.new('RGB',(112,112),color);draw=ImageDraw.Draw(image)
    for x in range(-112,224,24):draw.polygon([(x,0),(x+9,0),(x+121,112),(x+112,112)],fill=(245,235,220))
    draw.rectangle((13,39,98,72),fill=(10,15,25));draw.text((24,49),label,fill=(255,255,255))
    return image.tobytes()

def export(revision):
    assert re.fullmatch(r'r[1-9][0-9]*',revision)
    out=ROOT/'visuals/turntable-face-2026-10-18'/revision
    assert not out.exists(),'Preserve previews; choose a fresh revision'
    out.mkdir(parents=True);h=load_host();step=20
    albums=[album(c,n) for c,n in [((185,25,40),'OLD A'),((25,80,215),'NEW B'),((225,160,10),'NEW C'),((135,30,185),'NEW D')]]
    scenarios=['early-art','late-art','complete-exchange','rapid-before-edge','rapid-after-edge',
               'focus-early-art','frame-gap','complete-frame-gap']
    states={};events={};contact_times={};overview=[]
    for name in scenarios:
        full=name.startswith('complete');compact=name.startswith('focus')
        h.ca_reset();h.ff_play(True,0,200);frame(h,0);h.ca_context(101,0);transfer(h,albums[0],1,0);frame(h,200)
        base=1000
        if full:
            for n in range(4):
                at=1000+n*2380;h.ca_context(102+n,at);transfer(h,albums[0],10+n,at+200)
                frame(h,at+870);frame(h,at+1880)
            base=1000+4*2380
        h.ff_default();h.ca_context(106 if full else 102,base)
        end=3000 if full else 4200 if name=='rapid-after-edge' else 2600
        frames=[];samples=[];arrivals=[];last=None
        for ms in range(0,end+1,step):
            now=base+ms
            if ms==(2100 if name=='late-art' else 300):
                transfer(h,albums[1],20,now);arrivals.append(dict(ms=ms,event='CRC complete / ACK staging',album='B'))
            if name=='rapid-before-edge' and ms in (200,500):
                key=103 if ms==200 else 104;h.ca_context(key,now);transfer(h,albums[key-101],key,now)
                arrivals.append(dict(ms=ms,event='retarget + ACK staging',album='C' if ms==200 else 'D'))
            if name=='rapid-after-edge' and ms in (1100,1400):
                key=103 if ms==1100 else 104;h.ca_context(key,now);transfer(h,albums[key-101],key,now)
                arrivals.append(dict(ms=ms,event='retarget + ACK staging',album='C' if ms==1100 else 'D'))
            gap=(name=='frame-gap' and 620<=ms<1760) or (name=='complete-frame-gap' and 620<=ms<2520)
            if gap:
                image=last.copy();samples.append(dict(ms=ms,sampled=False,holding_previous_render=True))
            else:
                f=frame(h,now);pixels=snapshot(h)
                image=prior.scene(h,f,pixels,compact,True,'Nästa låt',0,0,200)
                samples.append(dict(ms=ms,sampled=True,frame=list(f),slot=h.ca_active(),
                    visible_pixels_sha256=hashlib.sha256(bytes(pixels)).hexdigest().upper(),acks=h.ca_ok()))
                last=image
            frames.append(image)
        frames[0].save(out/(name+'.gif'),save_all=True,append_images=frames[1:],duration=step,loop=0,disposal=2)
        selected=([0,300,680,1060,1080,1300,1550,1870,2380] if full else
                  [0,300,680,860,880,1060,1380,1880,2600])
        if name=='rapid-after-edge':selected=[0,860,880,1100,1400,1880,2740,2760,3800]
        if name=='late-art':selected=[0,300,860,880,1380,1880,2100,2180,2300]
        if name=='frame-gap':selected=[0,600,1000,1740,1760,1780,1880,1900,2600]
        if name=='complete-frame-gap':selected=[0,600,1060,1080,2380,2500,2520,2540,3000]
        indices=[min(len(frames)-1,round(ms/step)) for ms in selected]
        sheet=Image.new('RGB',(720,3*344),(29,34,40));draw=ImageDraw.Draw(sheet)
        for i,index in enumerate(indices):
            x=i%3*240;y=i//3*344;draw.text((x+4,y+3),f'{name} {index*step} ms',fill='white');sheet.paste(frames[index],(x,y+22))
        sheet.save(out/(name+'.png'));overview.append(frames[15]);states[name]=samples;events[name]=arrivals
        contact_times[name]=[i*step for i in indices]
    overview_image=Image.new('RGB',(960,2*344),(29,34,40));draw=ImageDraw.Draw(overview_image)
    for i,(name,image) in enumerate(zip(scenarios,overview)):
        x=i%4*240;y=i//4*344;draw.text((x+4,y+3),name,fill='white');overview_image.paste(image,(x,y+22))
    overview_image.save(out/'overview.png')
    html='''<!doctype html><meta charset="utf-8"><title>Omslag byts vid dold brytpunkt</title>
<style>body{background:#15191e;color:#eee;font:16px system-ui;margin:24px}main{display:flex;flex-wrap:wrap;gap:20px}section{border:1px solid #46515b;padding:12px}img{image-rendering:pixelated;width:240px}a{color:#7cddd0}strong{color:#ffcf6c}</style>
<h1>Omslagets synliga framsida</h1><p><strong>SIMULERAT, EJ SKÄRMPROVAT.</strong> Röd OLD A hålls kvar till kanten; blå NEW B, gul NEW C och lila NEW D tas emot via verklig C++-parser/CRC/staging. ACK kvitterar mottagningen, visningen väntar avsiktligt. C++-state, projektion och ritprimitiver; hosttempo är inte TFT-mätning.</p><main>'''
    for name in scenarios:html+=f'<section><h2>{name}</h2><img src="{name}.gif"><p><a href="{name}.png">Förloppsbilder</a></p></section>'
    (out/'index.html').write_text(html+'</main>',encoding='utf-8')
    old=json.loads((ROOT/'visuals/turntable-arm-tempo-2026-10-18/r2/manifest.json').read_text())
    files=set(old['source_sha256'])|{'src/media_art_compact.h','src/media_art_v2.h','tests/compact_art_host.py','tests/compact_art_host.cpp',
        'tests/turntable_face_host.py','tests/turntable_face_host.cpp','tests/test_turntable_face.py','tools/turntable_face_visuals.py','companion/artwork_codec.py'}
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest().upper()
    manifest=dict(classification='SIMULATED actual C++ receiver/CRC/two-slot state/disc/primitives, not physical TFT',
        frame_ms=step,face_switch_ms=870,full_switch_ms=1070,normal_ms=1880,full_ms=2380,reveal_ms=180,
        source_sha256={n:sha(ROOT/n) for n in sorted(files)},output_sha256={p.name:sha(p) for p in out.iterdir() if p.is_file()},
        contact_times_ms=contact_times,events=events,states=states,
        limitations=['Synthetic high-contrast RGB inputs; actual compact receiver and pinned-slot pixel selection.',
            'PIL rasterisation of C++ primitives can differ from LVGL by edge pixels.',
            'Frame gaps hold the previous rendered image then require a thin/offscreen sample.',
            'No UART/ACK latency, TFT performance, physical touch/sleep or hardware acceptance inferred.'])
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(out),manifest_sha256=sha(out/'manifest.json'),scenarios=len(scenarios))))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--revision',default='r1');export(parser.parse_args().revision)

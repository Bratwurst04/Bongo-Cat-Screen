"""Real sender packets -> native CRC/notice/slots -> native state and render."""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import re
import sys
from unittest.mock import patch
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build/artwork-refinement-2026-10-19'
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools'),str(ROOT/'companion')]
import compact_art_host,turntable_face_host
compact_art_host.BUILD=BUILD/'native/parser';turntable_face_host.BUILD=BUILD/'native'
from test_artwork_refinement import make_pair,send_primary,until,TOKEN,OTHER
from turntable_face_host import load_host,frame,snapshot,transfer,Pixels
from media_bridge import WindowsMediaBridge
import test_artwork_v2 as legacy
import turntable_paw_visuals as composition

FIXTURE='visuals/artwork-compact80-2026-10-18/r1/fixture-cover.png'

def capture(rgb,mode):
    e,w,reader=make_pair();e._on_media_update(legacy.ArtworkV2Tests.snapshot('song'),rgb)
    try:
        send_primary(e);until(lambda:e._artwork_refinement['shown'])
        job=e._take_artwork_refinement();assert job
        changed=False;skipped=False;full_batches=0
        def retarget(payload):
            nonlocal changed,skipped,full_batches
            if not w.current_compact and payload.startswith(b'MEDIA_ART2_CHUNK:'):
                full_batches+=1
                if full_batches==16 and not changed:
                    changed=True;e._on_media_update(legacy.ArtworkV2Tests.snapshot('next'),OTHER)
            elif mode=='double-skip' and changed and not skipped and payload.startswith(b'MEDIA_ART2_CHUNK:'):
                skipped=True;e._on_media_update(legacy.ArtworkV2Tests.snapshot('latest'),rgb)
        if mode in ('rapid-retarget','double-skip'):w.after_write=retarget
        if mode=='bad-high-crc':w.corrupt_full=True
        with patch('engine.time.sleep'):
            e._send_artwork_v2(w,job['track'],job['artwork'],0,job)
        if mode in ('rapid-retarget','double-skip'):
            send_primary(e)
            if mode=='double-skip':send_primary(e)
            w.after_write=None;w.render(4000);w.render(4880)
            until(lambda:e._artwork_refinement is not None and e._artwork_refinement['shown'])
            latest=e._take_artwork_refinement();assert latest
            with patch('engine.time.sleep'):
                e._send_artwork_v2(w,latest['track'],latest['artwork'],0,latest)
        # Every packet is from the actual current engine, not a hand-written codec.
        groups=[];prefix=[]
        for packet in w.writes:
            if packet.startswith(b'MEDIA_ART2_BEGIN'):
                group=dict(kind='compact' if packet.startswith(b'MEDIA_ART2_BEGIN565:') else 'full',
                           id=int(packet.split(b':')[1]),packets=prefix+[packet])
                prefix=[];groups.append(group)
            elif groups:groups[-1]['packets'].append(packet)
            else:prefix.append(packet)
        return groups
    finally:e.running=False;w.rx.put(b'\n');reader.join(0.5)

def schedule(group,start):
    stride=350/13 if group['kind']=='compact' else 4680/147
    now=start;result=[]
    for packet in group['packets']:
        if packet.startswith(b'MEDIA_ART2_CHUNK:'):now+=stride
        result.append((now,packet))
    return result

def disc(h,pixels,f):
    out=Pixels();assert h.tt_render(out,12544,pixels,f,0,32768,composition.PALETTE)
    image=Image.new('RGBA',(112,112));image.putdata([composition.rgba(p) for p in out]);return image

def export(revision):
    assert re.fullmatch(r'r[1-9][0-9]*',revision)
    out=ROOT/'visuals/artwork-refinement-2026-10-19'/revision
    assert not out.exists(),'Preserve previews; use a fresh revision'
    out.mkdir(parents=True)
    # Test and preview processes must not try to relink the same loaded DLL.
    turntable_face_host.BUILD=BUILD/'preview-native'/revision
    compact_art_host.BUILD=turntable_face_host.BUILD/'parser'
    rgb=WindowsMediaBridge._to_vinyl_rgb888((ROOT/FIXTURE).read_bytes())
    h=load_host();scenarios=['same-cover','focus-refinement','paused-refinement','bad-high-crc','rapid-retarget','double-skip']
    all_states={};wire_hashes={};trace={};comparisons=None;overview=[];metrics={}
    for name in scenarios:
        groups=capture(rgb,name);h.ca_reset();h.ff_generation(TOKEN.encode())
        playing=name!='paused-refinement';compact=name=='focus-refinement'
        h.ff_play(playing,0,200);frame(h,0);h.ca_context(101,0);transfer(h,OTHER,1,0);frame(h,200)
        seen=h.ff_shown();pinned=set();group_index=0;active=None;index=0;last_low_id=None
        frames=[];states=[];events=[];last_finish=0;angle=0;title='Bongo 112';low=None;high=None
        low_ms=None;high_ms=None
        for ms in range(0,12001,20):
            if active is None and group_index<len(groups):
                group=groups[group_index]
                if group['kind']=='compact' or last_low_id in pinned:
                    active=schedule(group,ms);index=0
                    events.append(dict(ms=ms,event='BEGIN '+group['kind'],id=group['id']))
            if active is not None:
                group=groups[group_index]
                while index<len(active) and active[index][0]<=ms:
                    stamp,packet=active[index];index+=1
                    for line in packet.splitlines():
                        now=1000+int(stamp)
                        if line==b'MEDIA_ART_DEFAULT':h.ff_default()
                        elif line.startswith(b'MEDIA_TRACK_CONTEXT:'):h.ca_context(int(line.split(b':')[1]),now)
                        elif line.startswith(b'MEDIA_TITLE:'):title=line.split(b':',1)[1].decode('utf-8')
                        elif line.startswith(b'MEDIA_ART2_'):
                            if name=='bad-high-crc' and group['kind']=='full' and line.startswith(b'MEDIA_ART2_CHUNK:'):
                                fields=line.split(b':',3);fields[3]=(b'A' if fields[3][:1]!=b'A' else b'B')+fields[3][1:];line=b':'.join(fields)
                            ok=h.ca_ok();bad=h.ca_error();h.ca_line(line,now)
                            if h.ca_ok()>ok:
                                events.append(dict(ms=ms,event='CRC/ACK '+group['kind'],id=group['id']))
                                if group['kind']=='compact':last_low_id=group['id']
                                else:high_ms=ms
                            if h.ca_error()>bad:events.append(dict(ms=ms,event='CRC rejected; keep low',id=group['id']))
                if index==len(active):active=None;group_index+=1;last_finish=ms
            position=ms//1000 if playing else 0
            h.ff_play(playing,position,200);f=frame(h,1000+ms)
            if h.ff_shown()!=seen:
                seen=h.ff_shown();pinned.add(h.ff_shown_id())
                events.append(dict(ms=ms,event='slot selected / SHOWN',id=h.ff_shown_id()))
                low=Pixels.from_buffer_copy(bytes(snapshot(h)));low_ms=ms
            if high_ms==ms:high=Pixels.from_buffer_copy(bytes(snapshot(h)))
            if playing and not f[10]:angle=(angle+2)%360
            pixels=snapshot(h)
            image=composition.scene(h,f,pixels,compact,playing,title,angle,position,200)
            frames.append(image);states.append(dict(ms=ms,frame=list(f),slot=h.ca_active(),angle=angle,
                pixel_sha256=hashlib.sha256(bytes(pixels)).hexdigest().upper(),acks=h.ca_ok(),errors=h.ca_error()))
            if group_index==len(groups) and active is None and ms>=max(6400,last_finish+400):break
        assert group_index==len(groups),'All captured groups must be delivered or intentionally cancelled'
        frames[0].save(out/(name+'.gif'),save_all=True,append_images=frames[1:],duration=20,loop=0,disposal=2)
        selected=[0,880,1880,3000,5000,high_ms-20 if high_ms else 5560,high_ms or 5600,high_ms+100 if high_ms else 6000,len(frames)*20-20]
        if name in ('rapid-retarget','double-skip'):selected=[0,880,1400,1880,2760,4000,high_ms-20,high_ms,len(frames)*20-20]
        indices=[min(len(frames)-1,max(0,round(ms/20))) for ms in selected]
        sheet=Image.new('RGB',(720,1032),(29,34,40));draw=ImageDraw.Draw(sheet)
        for i,n in enumerate(indices):
            x=i%3*240;y=i//3*344;draw.text((x+4,y+3),f'{name} {n*20} ms',fill='white');sheet.paste(frames[n],(x,y+22))
        sheet.save(out/(name+'.png'));overview.append(frames[min(len(frames)-1,160)])
        all_states[name]=states;trace[name]=events
        wire_hashes[name]=[dict(kind=g['kind'],id=g['id'],packets=len(g['packets']),
            sha256=hashlib.sha256(b''.join(g['packets'])).hexdigest().upper()) for g in groups]
        metrics[name]=dict(low_selected_ms=low_ms,full_committed_ms=high_ms,
            selected_to_full_ms=high_ms-low_ms if high_ms is not None and low_ms is not None else None)
        if name=='same-cover':
            assert low is not None and high is not None and bytes(low)!=bytes(high)
            expected=Pixels();h.ca_legacy_pixels.argtypes=[ctypes.c_char_p,ctypes.POINTER(ctypes.c_ushort)]
            h.ca_legacy_pixels(rgb,expected)
            chroma=composition.PALETTE[0]
            assert [p==chroma for p in low]==[p==chroma for p in high]
            assert all(a==b for a,b,c in zip(high,expected,low) if b!=chroma and c!=chroma)
            stable=frame(h,1000+states[-1]['ms']);comparisons=[disc(h,p,stable) for p in (low,high)]
            metrics[name].update(full_detail_matches_actual_112_conversion=True,opaque_mask_matches_low=True,
                changed_words=sum(a!=b for a,b in zip(low,high)))
    quality=Image.new('RGB',(896,474),(29,34,40));draw=ImageDraw.Draw(quality)
    for i,image in enumerate(comparisons):
        draw.text((i*448+8,8),'80 -> 112, first image' if i==0 else 'Full 112, same registration',fill='white')
        quality.paste(image.resize((448,448),Image.Resampling.NEAREST),(i*448,26),image.resize((448,448),Image.Resampling.NEAREST))
    quality.save(out/'detail-comparison.png')
    overview_image=Image.new('RGB',(720,688),(29,34,40));draw=ImageDraw.Draw(overview_image)
    for i,(name,image) in enumerate(zip(scenarios,overview)):
        x=i%3*240;y=i//3*344;draw.text((x+4,y+3),name,fill='white');overview_image.paste(image,(x,y+22))
    overview_image.save(out/'overview.png')
    html='''<!doctype html><meta charset="utf-8"><title>Samma omslag, mer detalj</title>
<style>body{background:#15191e;color:#eee;font:16px system-ui;margin:24px}main{display:flex;flex-wrap:wrap;gap:20px}section{border:1px solid #46515b;padding:12px}img{image-rendering:pixelated;width:240px}a{color:#7cddd0}strong{color:#ffcf6c}.detail{width:896px;max-width:100%}</style>
<h1>Samma omslag, mer detalj</h1><p><strong>SIMULERING, INTE FYSISK TIDMÄTNING.</strong> Faktiska sender-paket spelas genom verklig C++-parser/CRC/slots/SHOWN/state/render. Kompakt först; full112 från samma cache efter vald slot. Atomisk skärpning utan ny tass eller ny storlek. Fulltransportens 4,68s bygger på tidigare C2-observation, inte mätning av denna kandidat.</p><img class="detail" src="detail-comparison.png"><main>'''
    for name in scenarios:html+=f'<section><h2>{name}</h2><img src="{name}.gif"><p><a href="{name}.png">Tidsserie</a></p></section>'
    (out/'index.html').write_text(html+'</main>',encoding='utf-8')
    (out/'simulation.json').write_text(json.dumps(dict(events=trace,metrics=metrics,sender_packet_hashes=wire_hashes),indent=2)+'\n',encoding='utf-8')
    old=json.loads((ROOT/'visuals/turntable-face-2026-10-18/r1/manifest.json').read_text())
    files=set(old['source_sha256'])|{FIXTURE,'companion/engine.py','companion/media_bridge.py','src/media_art_refinement.h',
        'tests/test_artwork_refinement.py','tools/artwork_refinement_visuals.py'}
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest().upper()
    manifest=dict(classification='SIMULATED actual sender packets/native receiver/notification/slots/state/render',
        source_sha256={n:sha(ROOT/n) for n in sorted(files)},output_sha256={p.name:sha(p) for p in out.iterdir() if p.is_file()},
        frame_ms=20,assumed_compact_transfer_ms=350,assumed_full_transfer_ms=4680,metrics=metrics,events=trace,states=all_states,
        limitations=['Synthetic accepted prior fixture; same actual 112 RGB888 cache conversion, no image/network fetch.',
            'Full sender uses 2frames/15ms; modeled4.68s comes from older C2 Windows run, not current pair timing.',
            'SHOWN means selected/pinned slot, not a measured LCD-visible timestamp.',
            'PIL rasterisation/scripted rotation/progress may differ from LVGL/TFT scheduling.',
            'No physical latency, touch, sleep, memory headroom or long-run acceptance inferred.'])
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(out),manifest_sha256=sha(out/'manifest.json'),metrics=metrics)))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--revision',default='r1');export(parser.parse_args().revision)

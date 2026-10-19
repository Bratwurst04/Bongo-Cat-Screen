"""Actual encoder -> firmware parser/CRC/expand -> record renderer comparison."""
import base64
import hashlib
import io
import json
from pathlib import Path
import sys
import zlib
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'companion'),str(ROOT/'tools')]
from artwork_codec import pack_compact_rgb565
from media_bridge import WindowsMediaBridge
from compact_art_host import BUILD,Pixels,load_host,snapshot
import compact_art_host
import turntable_paw_host
import turntable_paw_visuals as composition


def export():
    out=ROOT/'visuals/artwork-compact80-2026-10-18/r1';assert not out.exists(),'Preserve preview revisions'
    out.mkdir(parents=True)
    compact_art_host.BUILD=BUILD/'preview-native'
    # Synthetic detail/colour fixture only; no live or private album content.
    cover=Image.new('RGB',(300,300));cover.putdata([(30+x*180//300,25+y*160//300,145+(x+y)%70) for y in range(300) for x in range(300)])
    draw=ImageDraw.Draw(cover);font=ImageFont.load_default(size=28)
    draw.rectangle((30,26,270,90),fill=(16,28,43));draw.text((45,40),'BONGO CAT',font=font,fill=(245,219,103))
    for i in range(12):draw.line((30+i*19,110,270-i*9,230),fill=(220-i*7,225,210),width=1 if i%2 else 2)
    draw.ellipse((120,130,215,225),fill=(220,77,80),outline=(250,220,180),width=2)
    draw.text((45,248),'SMALL DETAILS',font=ImageFont.load_default(size=17),fill='white')
    cover.save(out/'fixture-cover.png');blob=io.BytesIO();cover.save(blob,format='PNG')
    raw=WindowsMediaBridge._to_vinyl_rgb888(blob.getvalue());packed=pack_compact_rgb565(raw)
    native=load_host();native.ca_reset();before=Pixels();native.ca_legacy_pixels(raw,before)
    crc=zlib.crc32(packed)&0xffffffff
    native.ca_line(f'MEDIA_ART2_BEGIN565:7:80:80:12800:{crc:08X}'.encode(),0)
    for offset in range(0,len(packed),128):
        native.ca_line(f'MEDIA_ART2_CHUNK:7:{offset}:'.encode()+base64.b64encode(packed[offset:offset+128]),0)
    native.ca_line(b'MEDIA_ART2_END:7',0);assert native.ca_ok()==1
    after=snapshot(native)
    turntable_paw_host.BUILD=BUILD/'preview-turntable-host';h=turntable_paw_host.load_host();T=turntable_paw_host.timings(h)
    composition.warm(h);base=1000;h.tt_event(1,9,base,True);h.tt_event(2,102,base,True)
    for ms in range(0,T['lower_end']+1,T['frame_ms']):
        if ms==T['lift_end']+40:h.tt_event(3,0,base+ms,True)
        f=turntable_paw_host.Frame();h.tt_frame(base+ms,True,f)
    assert f[0]==1 and f[1]==112
    comparison=Image.new('RGB',(480,688),(29,34,40));sheets=[]
    for row,compact in enumerate((False,True)):
        draw=ImageDraw.Draw(comparison)
        for col,art in enumerate((before,after)):
            label=('112 RGB888' if col==0 else '80 RGB565 -> 112')+(' / Fokus' if compact else ' / Normal')
            draw.text((col*240+4,row*344+4),label,fill='white')
            image=composition.scene(h,f,art,compact,True,'Färg och små detaljer',0,0,200)
            comparison.paste(image,(col*240,row*344+22))
            if not compact:sheets.append(image)
    comparison.save(out/'comparison.png')
    detail=Image.new('RGB',(480,264),(29,34,40))
    for i,im in enumerate(sheets):
        detail.paste(im.crop((60,52,180,172)).resize((240,240),Image.Resampling.NEAREST),(i*240,24))
        ImageDraw.Draw(detail).text((i*240+4,4),'112 reference' if not i else '80 RGB565, actual receiver',fill='white')
    detail.save(out/'detail.png')
    (out/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>Kompakt omslag – simulering</title>
<style>body{background:#15191e;color:#eee;font:16px system-ui;margin:24px}img{image-rendering:pixelated;max-width:100%}</style>
<h1>112 RGB888 / 80 RGB565 uppskalad till 112</h1><p>SIMULERAT, EJ TFT- ELLER FARTPROVAT. Samma pose, layout och syntetiska bildkälla. Faktisk packhjälpare, firmware-parser/CRC/staging/expansion och C++-skivrendering. UI/PIL-komposition kan skilja i kantpixlar från LVGL.</p><img src="comparison.png"><h2>Detalj</h2><img src="detail.png">''',encoding='utf-8')
    files=['companion/artwork_codec.py','companion/media_bridge.py','src/media_art_v2.h','src/media_art_compact.h',
        'src/media_turntable.h','src/bongo_cat_featured.inc','tests/compact_art_host.cpp','tests/compact_art_host.py',
        'tests/turntable_paw_host.cpp','tests/turntable_paw_host.py','tools/turntable_paw_visuals.py',
        'tools/record_flip_visuals.py','tools/artwork_compact_visuals.py',
        '.pio/libdeps/esp32-024r-spotify-artfast921600/lvgl/src/misc/lv_color.h']
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest().upper()
    manifest=dict(classification='SIMULATED actual codec/receiver/renderer; no hardware acceptance',
        source_sha256={n:sha(ROOT/n) for n in files},output_sha256={p.name:sha(p) for p in out.iterdir() if p.is_file()},
        payload_bytes=len(packed),payload_sha256=hashlib.sha256(packed).hexdigest().upper(),
        frame=list(f),timings=T,limitations=['Synthetic fixture, no live album data.',
        'Host String/base64/UI stubs; production parser/CRC/expansion/slot activation and LVGL colour macro executed.',
        'No TFT rate, CH340 throughput, runtime, touch or physical acceptance inferred.'])
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(out),'payload_bytes':len(packed),'manifest_sha256':sha(out/'manifest.json')}))


if __name__=='__main__':export()

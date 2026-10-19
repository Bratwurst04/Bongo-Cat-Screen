"""Authorized local photo -> converter -> real sender/native parser/render, no live I/O."""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build/artwork-crop-2026-10-19'
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools'),str(ROOT/'companion')]
import compact_art_host,turntable_face_host
turntable_face_host.BUILD=BUILD/'preview-native/r1'
compact_art_host.BUILD=turntable_face_host.BUILD/'parser'
from test_artwork_crop import read_fixture,legacy_converter,BOX,FIXTURE
from test_artwork_refinement import make_pair,send_primary,until
from turntable_face_host import snapshot,frame,Pixels
from media_bridge import WindowsMediaBridge
import test_artwork_v2 as legacy
import turntable_paw_visuals as composition
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest().upper()


def native_pair(rgb):
    engine,wire,reader=make_pair()
    try:
        engine._on_media_update(legacy.ArtworkV2Tests.snapshot('song'),rgb)
        send_primary(engine);until(lambda:engine._artwork_refinement['shown'])
        job=engine._take_artwork_refinement();assert job['artwork'] is rgb
        coarse=Pixels.from_buffer_copy(bytes(snapshot(wire.h)));pose=frame(wire.h,4000)
        with patch('engine.time.sleep'):
            engine._send_artwork_v2(wire,job['track'],job['artwork'],0,job)
        fine=snapshot(wire.h);assert bytes(coarse)!=bytes(fine)
        assert [p==composition.PALETTE[0] for p in coarse]==[p==composition.PALETTE[0] for p in fine]
        assert list(frame(wire.h,4000))==list(pose)
        images=[]
        for pixels in (coarse,fine):
            output=Pixels();assert wire.h.tt_render(output,12544,pixels,pose,0,32768,composition.PALETTE)
            image=Image.new('RGBA',(112,112));image.putdata([composition.rgba(p) for p in output]);images.append(image)
        return images,dict(compact_acks=wire.compact_ends,full_acks=wire.full_ends,
            coarse_sha256=hashlib.sha256(bytes(coarse)).hexdigest().upper(),
            refined_sha256=hashlib.sha256(bytes(fine)).hexdigest().upper(),
            coarse_mask_preserved=True,pose_preserved=True,common_cache=True)
    finally:
        engine.running=False;wire.rx.put(b'\n');reader.join(.5)


def export(revision):
    assert revision.startswith('r') and revision[1:].isdigit()
    turntable_face_host.BUILD=BUILD/'preview-native'/revision
    compact_art_host.BUILD=turntable_face_host.BUILD/'parser'
    out=BUILD/'preview'/revision;assert not out.exists(),'Preserve previous preview'
    out.mkdir(parents=True)
    payload,source=read_fixture();album=source.crop(BOX)
    old=legacy_converter()(payload)
    new=WindowsMediaBridge._to_vinyl_rgb888(payload,windows_spotify_thumbnail=True)
    old_images,old_metrics=native_pair(old);new_images,new_metrics=native_pair(new)
    album.save(out/'exact-album-crop.png')
    for label,rgb in (('prior-cache112',old),('cropped-cache112',new)):
        image=Image.frombytes('RGB',(112,112),rgb);image.save(out/(label+'.png'))
    for name,image in zip(('prior-compact','prior-refined','cropped-compact','cropped-refined'),old_images+new_images):
        image.save(out/(name+'.png'))
    sheet=Image.new('RGB',(1200,750),(25,29,35));draw=ImageDraw.Draw(sheet)
    draw.text((12,8),'SIMULERAD lokal bildkedja; ingen TFT- eller tidsmatning',fill='white')
    for index,(label,image) in enumerate((('Windows original 300x300',source),('Exakt album (33,0,267,234)',album))):
        x=index*600+12;draw.text((x,32),label,fill='white')
        enlarged=image.resize((300,300),Image.Resampling.NEAREST);sheet.paste(enlarged,(x,52),enlarged)
    for index,(label,image) in enumerate(zip(('Tidigare kompakt80 ->112','Tidigare full112',
            'Beskuren kompakt80 ->112','Beskuren full112'),old_images+new_images)):
        x=index*300+12;draw.text((x,375),label,fill='white')
        large=image.resize((280,280),Image.Resampling.NEAREST);sheet.paste(large,(x,400),large)
    draw.text((12,710),'Samma crop/cache i snabbild och detalj; exakt coarse-mask och pose bevarad.',fill='white')
    sheet.save(out/'comparison.png')
    fixture='visuals/artwork-compact80-2026-10-18/r1/fixture-cover.png'
    negative=(ROOT/fixture).read_bytes();expected=legacy_converter()(negative)
    actual=WindowsMediaBridge._to_vinyl_rgb888(negative,windows_spotify_thumbnail=True)
    assert actual==expected
    negative_image=Image.frombytes('RGB',(112,112),actual);negative_image.save(out/'unchanged-correct-cover.png')
    (out/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>Selektiv omslagsbeskarning</title>
<style>body{background:#191d23;color:white;font:17px system-ui;margin:24px}img{max-width:100%;image-rendering:pixelated}a{color:#7cddd0}</style>
<h1>Selektiv beskarning av Spotify SMTC-ram</h1><p>SIMULERING. Verklig konverterare, sender, CRC/slots och C++-render.
Ingen fysisk TFT- eller latensacceptans. Originalbilden ar lokal och ingar inte i Git.</p>
<img src="comparison.png"><p><a href="exact-album-crop.png">Exakt albumkvadrat</a> |
<a href="unchanged-correct-cover.png">Tidigare korrekt testomslag, byteidentiskt</a></p>''',encoding='utf-8')
    sources={'companion/artwork_crop.py','companion/media_bridge.py','companion/artwork_codec.py','companion/engine.py',
        'tests/test_artwork_crop.py','tests/fixtures/spotify-smtc-footer-alpha.png','tests/fixtures/vinyl59fc.py',
        'tests/test_artwork_refinement.py','tests/test_artwork_v2.py',
        'tests/compact_art_host.py','tests/compact_art_host.cpp','tests/turntable_face_host.py','tests/turntable_face_host.cpp',
        'src/bongo_cat_featured.inc','src/media_art_v2.h','src/media_art_compact.h','src/media_art_refinement.h',
        'src/media_turntable.h','src/media_record_flip.h','src/media_track_context.h',
        'tools/artwork_crop_visuals.py','tools/turntable_paw_visuals.py','tools/record_flip_visuals.py',fixture,
        str(FIXTURE.relative_to(ROOT))}
    manifest=dict(classification='SIMULATED actual conversion/sender/native parser/CRC/slots/render; no hardware acceptance',
        input_sha256=sha(FIXTURE),crop_box=BOX,album_size=album.size,no_second_inset=True,
        source_sha256={name:sha(ROOT/name) for name in sorted(sources)},
        output_sha256={p.name:sha(p) for p in out.iterdir() if p.is_file()},
        metrics=dict(prior=old_metrics,cropped=new_metrics,correct_cover_byteidentical=True),
        limitations=['One evidenced transparent PNG wrapper family only; opaque/JPEG/unknown layouts keep legacy output.',
            'Actual image and all photo-derived outputs stay in ignored build; nothing fetched.',
            'Native host/PIL pixels are source evidence, not measured TFT pixels, timing or runtime acceptance.'])
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(out),manifest_sha256=sha(out/'manifest.json'),metrics=manifest['metrics'])))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--revision',default='r2');export(parser.parse_args().revision)

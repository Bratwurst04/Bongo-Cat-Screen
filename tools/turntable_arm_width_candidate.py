"""Small arm-width revision; reuse read-only helpers with isolated outputs."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build/turntable-arm-width-2026-10-18'
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest().upper()


def configure():
    import turntable_paw_host as native
    import turntable_arm_tempo_candidate as prior
    native.BUILD=BUILD/'host'
    prior.BUILD=BUILD
    prior.NEW={'tools/turntable_arm_width_candidate.py'}
    return native,prior


def save(name,data):
    (BUILD/name).write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')


def preview():
    configure()
    import turntable_arm_tempo_visuals as visuals
    from PIL import Image,ImageDraw
    visuals.export('r2')
    root=ROOT/'visuals/turntable-arm-tempo-2026-10-18';out=root/'r2'
    image=Image.new('RGB',(760,576),(29,34,40));draw=ImageDraw.Draw(image)
    inputs={}
    for row,name in enumerate(('paw-flip','focus-change')):
        y=row*288;draw.text((8,y+35),'Normal' if row==0 else 'Fokus',fill='white')
        for column,revision in enumerate(('r1','r2')):
            manifest=json.loads((root/revision/'manifest.json').read_text())
            index=manifest['contact_times_ms'][name].index(manifest['timings_ms']['reach_end'])
            source=root/revision/(name+'.png');inputs[str(source.relative_to(ROOT))]=sha(source)
            im=Image.open(source);x=index%3*240;top=index//3*344+22
            grip=im.crop((x,top+90,x+70,top+150)).resize((280,240),Image.Resampling.NEAREST)
            left=170+column*300
            draw.text((left,y+4),'Fore: installerad 627E6B93' if column==0 else 'Efter: tjockare vit underarm',fill='white')
            image.paste(grip,(left,y+26))
        draw.text((8,y+268),'SIMULERAT, EJ TFT',fill=(255,207,108))
    image.save(out/'arm-before-after.png')
    path=out/'manifest.json';manifest=json.loads(path.read_text())
    manifest['comparison_inputs_sha256']=inputs
    manifest['source_sha256']['tools/turntable_arm_width_candidate.py']=sha(Path(__file__))
    manifest['output_sha256']['arm-before-after.png']=sha(out/'arm-before-after.png')
    path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')


def capture():
    cache=ROOT/'.pio/build/esp32-024r-spotify-fastserial'
    for suffix in ('bin','elf'):shutil.copy2(cache/('firmware.'+suffix),BUILD/('firmware.'+suffix))
    print(json.dumps({'bytes':(BUILD/'firmware.bin').stat().st_size,'sha256':sha(BUILD/'firmware.bin')}))


def verify():
    manifest=json.loads((BUILD/'source-frozen.json').read_text())
    for name,digest in manifest.items():
        assert sha(ROOT/name)==sha(BUILD/'source-frozen'/name)==digest,name
        if name.endswith('.py'):compile((ROOT/name).read_bytes(),name,'exec')
    base=json.loads((BUILD/'baseline-source.json').read_text())
    changed={name for name,h in base.items() if sha(ROOT/name)!=h}
    assert changed=={'src/media_turntable.h','00_PROJECT_CONTEXT.md','01_CURRENT_STATE.md','02_DECISIONS.md'},changed
    old=(ROOT/'build/turntable-arm-tempo-2026-10-18/source-frozen/src/media_turntable.h').read_text()
    current=(ROOT/'src/media_turntable.h').read_text()
    for a,b in [('joint = wrist > 8 ? wrist-8 : 0','joint = wrist > 8 ? wrist-8 : -2'),
                ('g.paw_y-6,joint,g.paw_y+5,p.black','g.paw_y-8,joint,g.paw_y+7,p.black'),
                ('g.paw_y-5,end,g.paw_y+4,p.black','g.paw_y-6,end,g.paw_y+5,p.black'),
                ('g.paw_y-4,joint+1,g.paw_y+3,p.white','g.paw_y-6,joint+1,g.paw_y+5,p.white'),
                ('g.paw_y-3,end,g.paw_y+2,p.white','g.paw_y-4,end,g.paw_y+3,p.white')]:
        assert old.count(a)==1;old=old.replace(a,b)
    assert current==old,'Only forearm width and its left clipping joint may change'
    preserved=json.loads((BUILD/'preserved-before.json').read_text())
    for name,v in preserved.items():assert (ROOT/name).stat().st_size==v['bytes'] and sha(ROOT/name)==v['sha256'],name
    out=ROOT/'visuals/turntable-arm-tempo-2026-10-18/r2';preview=json.loads((out/'manifest.json').read_text())
    for name,h in preview['source_sha256'].items():assert sha(ROOT/name)==h,name
    for name,h in preview['comparison_inputs_sha256'].items():assert sha(ROOT/name)==h,name
    for name,h in preview['output_sha256'].items():assert sha(out/name)==h,name
    review=json.loads((BUILD/'ui-review.json').read_text());assert review['preview_manifest_sha256']==sha(out/'manifest.json')
    tests=json.loads((BUILD/'focused-summary.json').read_text())
    assert tests['passed']==23 and not tests['errors'] and not tests['failures'] and not tests['skipped'] and not tests['external_network_attempts']
    log=(BUILD/'firmware-build.log').read_text(encoding='utf-8-sig');assert 'SUCCESS' in log
    info=(BUILD/'image-info.log').read_text(encoding='utf-8-sig');assert re.search(r'Checksum:.*\(valid\)',info)
    binary=BUILD/'firmware.bin';digest=sha(binary);candidate=ROOT/'.pio/candidates'/('turntable-arm-width-2026-10-18-'+digest[:8]+'.bin')
    if candidate.exists():assert sha(candidate)==digest
    else:shutil.copy2(binary,candidate)
    data=dict(status='built, not flashed; width refinement not physically tested',
        firmware=dict(path=str(candidate),sha256=digest,bytes=binary.stat().st_size,elf_sha256=sha(BUILD/'firmware.elf'),
            profile='esp32-024r-spotify-fastserial',app_address='0x10000',runtime_baud=230400,
            static_ram_bytes=int(re.search(r'RAM:.*?used (\d+) bytes',log)[1]),
            program_flash_bytes=int(re.search(r'Flash:.*?used (\d+) bytes',log)[1])),
        changed_existing=sorted(changed),new_sources=['tools/turntable_arm_width_candidate.py'],
        source_count=len(manifest),source_manifest_sha256=sha(BUILD/'source-frozen.json'),
        preserved_files=len(preserved),preservation_mismatches=[],tests=tests,
        preview=str(out.relative_to(ROOT)),preview_manifest_sha256=sha(out/'manifest.json'),ui_review=review,
        installed_companion='687211432857B34424EDA3D203F645C7324C0639D2F2308367D185987BBB5A50',
        installed_firmware='627E6B93F3A4B2CC4E649C5EAF3D4FCA1164EB9989339B6A4AFFEB25B9E6D571',
        build_log_sha256=sha(BUILD/'firmware-build.log'),image_info_sha256=sha(BUILD/'image-info.log'))
    save('candidate.json',data)
    print(json.dumps({'firmware':data['firmware'],'sources':len(manifest),'preserved_files':len(preserved),
        'source_manifest_sha256':data['source_manifest_sha256'],'candidate_manifest_sha256':sha(BUILD/'candidate.json')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['test','preview','capture','freeze','verify']);args=parser.parse_args()
    if args.mode=='test':sys.exit(configure()[1].run_tests(True))
    elif args.mode=='preview':preview()
    elif args.mode=='capture':capture()
    elif args.mode=='freeze':configure()[1].freeze()
    else:verify()

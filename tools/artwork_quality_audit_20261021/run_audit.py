"""Synthetic, isolated audit of the installed C421/EBB image pipeline.

No product import/runtime, profile, COM, Spotify/network request or firmware build.
Only new output files are written. Old freezes and caches are never regenerated.
"""
from __future__ import annotations
import argparse
import ast
import colorsys
import ctypes
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from PIL import Image, ImageCms, ImageDraw, ImageOps, features
import PIL

ROOT=Path(__file__).resolve().parents[2]
APP=ROOT/'build/product-committee-2026-10-20/app-package-r5'
FW=ROOT/'build/artwork-refinement-2026-10-19'
HERE=Path(__file__).resolve().parent
KEY=0x07E0


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest().upper()
def digest(data): return hashlib.sha256(data).hexdigest().upper()
def save_json(path,data): path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


def inputs():
    assert sha(APP/'source-frozen.json')=='1D430C1178BA0F9D62419B13D766C6F23C850F5488B8B9093AF71C69A7F9A5FE'
    assert sha(FW/'source-frozen.json')=='AA5668E97EEAE865C6048C53C2F1633F2C51AB18FE9AD56F0C3DAFA5A710F792'
    app=json.loads((APP/'source-frozen.json').read_text(encoding='utf-8'))['files']
    fw=json.loads((FW/'source-frozen.json').read_text(encoding='utf-8'))
    receipt={}
    for name in ('companion/media_bridge.py','companion/artwork_crop.py','companion/artwork_codec.py',
                 'companion/engine.py','companion/spotify_api.py'):
        path=APP/'source'/name
        assert sha(path)==app[name]['sha256']
        receipt[name]={'installed_source_sha256':sha(path),'current_identical':path.read_bytes()==(ROOT/name).read_bytes()}
    for name in ('src/media_art_compact.h','src/media_turntable.h','src/media_record_flip.h',
                 'src/bongo_cat_featured.inc','User_Setup.h','lv_conf.h'):
        path=FW/'source-frozen'/name
        assert sha(path)==fw[name]
        receipt[name]={'installed_source_sha256':sha(path),'current_identical':path.read_bytes()==(ROOT/name).read_bytes()}
    for name in ('tests/fixtures/lvgl8311-color16.inc','tests/fixtures/spotify-smtc-footer-alpha.png'):
        receipt[name]={'sha256':sha(ROOT/name)}
    copied=ROOT/'build/product-committee-2026-10-20/render-measurement-r2'
    library_pins=json.loads((copied/'libdeps-before.json').read_text(encoding='utf-8'))
    for name in ('TFT_Drivers/ILI9341_Init.h','TFT_Drivers/ILI9341_Rotation.h',
                 'TFT_Drivers/ILI9341_Defines.h','TFT_eSPI.cpp'):
        key='libdeps/esp32-024r-spotify-compact80/TFT_eSPI/'+name
        assert sha(copied/key)==library_pins[key]
        current=ROOT/'.pio/libdeps/esp32-024r-spotify-fastserial/TFT_eSPI'/name
        assert sha(current)==library_pins[key]
        receipt[str(current.relative_to(ROOT)).replace('\\','/')]={'sha256':sha(current)}
    assert receipt['tests/fixtures/lvgl8311-color16.inc']['sha256']=='B3B96C036E3238ED6A11040703150C5414E993026EE149C28F68960C2905C5A1'
    assert receipt['tests/fixtures/spotify-smtc-footer-alpha.png']['sha256']=='F516F11E9F0D5D08BAC8791A5EECA3A64A7E8DFF5A9E766EC2A21565A255BEDB'
    return receipt


def converter():
    namespace={}
    exec(compile((APP/'source/companion/artwork_crop.py').read_text(encoding='utf-8'),
                 'frozen-C421-artwork_crop.py','exec'),namespace)
    source=ast.parse((APP/'source/companion/media_bridge.py').read_text(encoding='utf-8'))
    cls=next(n for n in source.body if isinstance(n,ast.ClassDef) and n.name=='WindowsMediaBridge')
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_to_vinyl_rgb888')
    method.decorator_list=[]
    namespace.update(Image=Image,ImageDraw=ImageDraw,ImageOps=ImageOps,io=io,ART_SIZE=112)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),
                 'frozen-C421-static-converter.py','exec'),namespace)
    codecs={}
    exec(compile((APP/'source/companion/artwork_codec.py').read_text(encoding='utf-8'),
                 'frozen-C421-artwork_codec.py','exec'),codecs)
    return namespace['_to_vinyl_rgb888'],namespace['spotify_smtc_album_box'],codecs


def traced(function,payload,spotify=False):
    seen={}
    def trace(frame,event,arg):
        if frame.f_code is function.__code__ and event=='return':
            for name in ('source_rgb','label','vinyl'):
                seen[name]=frame.f_locals[name].copy()
            for name in ('album_box','label_size','label_xy'):
                seen[name]=frame.f_locals[name]
        return trace
    previous=sys.gettrace()
    try:
        sys.settrace(trace)
        rgb=function(payload,windows_spotify_thumbnail=spotify)
    finally: sys.settrace(previous)
    assert len(rgb)==37632 and seen['label_size']==81
    return rgb,seen


def host(out):
    native=out/'native';native.mkdir()
    shutil.copyfile(ROOT/'tests/fixtures/lvgl8311-color16.inc',native/'lvgl_color16.inc')
    shutil.copyfile(FW/'source-frozen/src/media_art_compact.h',native/'media_art_compact.h')
    compiler=sorted(Path('C:/Program Files/Microsoft Visual Studio').glob(
        '*/*/VC/Tools/MSVC/*/bin/Hostx64/x64/cl.exe'))[-1]
    command=[str(compiler),'/nologo','/std:c++14','/O2','/GS-','/GR-','/Zl','/LD',
        '/I'+str(native),str(HERE/'native_reference.cpp'),'/Fo'+str(native/'reference.obj'),
        '/link','/NODEFAULTLIB','/NOENTRY','/OUT:'+str(native/'reference.dll')]
    env=dict(os.environ,PATH=str(compiler.parent)+os.pathsep+os.environ.get('PATH',''))
    result=subprocess.run(command,cwd=native,env=env,capture_output=True,text=True)
    (native/'compile.log').write_text(result.stdout+result.stderr,encoding='utf-8')
    assert result.returncode==0,result.stdout+result.stderr
    dll=ctypes.CDLL(str(native/'reference.dll'))
    dll.quality_color.argtypes=[ctypes.c_uint]*3;dll.quality_color.restype=ctypes.c_uint
    dll.quality_full.argtypes=[ctypes.c_char_p,ctypes.POINTER(ctypes.c_uint16)]
    dll.quality_expand.argtypes=[ctypes.POINTER(ctypes.c_uint16)]
    return dll


def full565(host,rgb):
    words=(ctypes.c_uint16*(112*112))()
    host.quality_full(rgb,words)
    return bytes(words)


def expand(host,packed):
    words=(ctypes.c_uint16*(112*112)).from_buffer_copy(packed+bytes(112*112*2-len(packed)))
    assert host.quality_expand(words)==1
    return bytes(words)


def decode(packed,edge):
    # Digital preview: replicate bits to full-range RGB, not a calibrated panel.
    pixels=[]
    for value, in struct.iter_unpack('>H',packed):
        r=(value>>11)&31;g=(value>>5)&63;b=value&31
        pixels.append(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)))
    image=Image.new('RGB',(edge,edge));image.putdata(pixels);return image


def keyed(packed):
    rgb=decode(packed,112);output=Image.new('RGB',(112,112))
    words=struct.unpack('>'+str(112*112)+'H',packed)
    output.putdata([((36,36,36) if (x//8+y//8)%2 else (60,60,60)) if words[y*112+x]==KEY
                    else rgb.getpixel((x,y)) for y in range(112) for x in range(112)])
    return output


def encoded(image,**kwargs):
    stream=io.BytesIO();image.save(stream,**kwargs);return stream.getvalue()


def profiles():
    srgb=bytearray(ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes())
    srgb[24:36]=struct.pack('>6H',2026,1,1,0,0,0);srgb[84:100]=bytes(16)
    linear=bytearray(srgb)
    for i in range(struct.unpack_from('>I',linear,128)[0]):
        tag,offset,size=struct.unpack_from('>4sII',linear,132+i*12)
        if tag in (b'rTRC',b'gTRC',b'bTRC'):
            assert size>=16
            linear[offset:offset+size]=b'para'+bytes(4)+struct.pack('>HHI',0,0,65536)+bytes(size-16)
    return bytes(srgb),bytes(linear)


def patterns():
    swatches=[(255,0,0),(0,255,0),(0,0,255),(0,255,255),(255,0,255),(255,255,0),
              (0,0,0),(255,255,255),(128,128,128),(3,253,5),(32,64,128),(224,192,128),
              (24,24,24),(64,64,64),(192,192,192),(248,248,248)]
    image=Image.new('RGB',(512,512));draw=ImageDraw.Draw(image)
    for i,color in enumerate(swatches):
        x=i%4*128;y=i//4*128;draw.rectangle((x,y,x+127,y+127),fill=color)
    result={'swatches':(image,False),'deliberately-muted':(Image.blend(image,Image.new('RGB',image.size,(128,128,128)),.85),False)}
    for name,lo,hi in (('neutral-gray',0,255),('dark-steps',0,63),('bright-steps',192,255)):
        gray=Image.new('RGB',(512,512))
        gray.putdata([(lo+(x*(hi-lo)//511),)*3 for y in range(512) for x in range(512)])
        result[name]=(gray,False)
    detail=Image.new('RGB',(512,512));detail.putdata([((255,255,255) if (x//3+y//3)%2 else (0,0,0)) for y in range(512) for x in range(512)])
    result['fine-detail']=(detail,False)
    alpha=Image.new('RGBA',(512,512));alpha.putdata([(255,32,16,x*255//511) for y in range(512) for x in range(512)])
    result['alpha-gradient']=(alpha,False)
    wrapper=Image.new('RGBA',(300,300));wrapper.paste(image.resize((234,234)),(33,0))
    footer=Image.new('RGBA',(192,53),'white')
    with Image.open(ROOT/'tests/fixtures/spotify-smtc-footer-alpha.png') as mask:footer.putalpha(mask)
    wrapper.paste(footer,(54,247));result['recognized-smtc-wrapper']=(wrapper,True)
    return result


def roi_stats(image):
    pixels=[image.getpixel((x,y))[:3] for y in range(112) for x in range(112)
            if 8*8<(x-55)**2+(y-55)**2<33*33]
    luma=sorted(.2126*r+.7152*g+.0722*b for r,g,b in pixels)
    saturation=[colorsys.rgb_to_hsv(r/255,g/255,b/255)[1] for r,g,b in pixels]
    return {'encoded_rgb_luma_proxy_mean':sum(luma)/len(luma),'proxy_p95_minus_p05':luma[int(.95*len(luma))]-luma[int(.05*len(luma))],
            'mean_hsv_saturation':sum(saturation)/len(saturation),'not_physical_contrast':True}


def sheet(path,rows):
    canvas=Image.new('RGB',(1000,54+len(rows)*204),(244,244,244));draw=ImageDraw.Draw(canvas)
    draw.text((10,6),'SIMULERING / synthetic host images - NOT a photographed TFT',fill='black')
    for i,title in enumerate(('Source / alpha composite','actual RGB888 vinyl','80 RGB565 -> 112','112 refinement','168px nearest zoom model')):
        draw.text((i*200+8,30),title,fill='black')
    for row,(name,images) in enumerate(rows):
        for col,image in enumerate(images):
            if col==0 and image.mode=='RGBA':
                background=Image.new('RGBA',image.size)
                background.putdata([((112,112,112,255) if (x//24+y//24)%2 else (192,192,192,255))
                                    for y in range(image.height) for x in range(image.width)])
                image=Image.alpha_composite(background,image)
            image=ImageOps.contain(image.convert('RGB'),(168,168),Image.Resampling.NEAREST)
            x=col*200+16;y=54+row*204
            canvas.paste(image,(x,y));draw.text((col*200+8,y+174),name,fill='black')
    canvas.save(path)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    out=args.output.resolve()
    if not out.is_relative_to(ROOT) or out==ROOT:parser.error('Output must be a NEW directory inside the repository')
    out.mkdir(parents=True,exist_ok=False)
    pins=inputs();save_json(out/'source-inputs.json',pins)
    function,detect,codec=converter();native=host(out);rows=[];metrics={};checks=[]
    cases=patterns()
    for name,(source,spotify) in cases.items():
        folder=out/name;folder.mkdir();payload=encoded(source,format='PNG')
        (folder/'source.png').write_bytes(payload)
        rgb,trace=traced(function,payload,spotify)
        packed=codec['pack_compact_rgb565'](rgb);coarse=expand(native,packed)
        refinement=codec['refinement_rgb888'](rgb,packed);refined=full565(native,refinement)
        assert [v==KEY for v, in struct.iter_unpack('>H',coarse)]==[v==KEY for v, in struct.iter_unpack('>H',refined)]
        assert (trace['album_box'] is not None)==spotify
        (folder/'vinyl.rgb888').write_bytes(rgb);(folder/'compact.rgb565-be').write_bytes(packed)
        (folder/'refinement.rgb888').write_bytes(refinement)
        trace['source_rgb'].save(folder/'cropped-rgb.png');trace['label'].save(folder/'label81.png')
        vinyl=Image.frombytes('RGB',(112,112),rgb);vinyl.save(folder/'vinyl112.png')
        decode(packed,80).save(folder/'compact80.png');keyed(coarse).save(folder/'expanded112-key-simulation.png')
        view=keyed(refined);view.save(folder/'refined112-key-simulation.png')
        zoom=view.resize((168,168),Image.Resampling.NEAREST);zoom.save(folder/'normal168-zoom-model.png')
        metrics[name]={'source_size':source.size,'source_mode':source.mode,'recognized_album_box':trace['album_box'],
            'generic_inset':(source.width-trace['source_rgb'].width)//2 if trace['album_box'] is None else 0,
            'cropped_size':trace['source_rgb'].size,
            'label_size':trace['label_size'],'coarse':roi_stats(decode(coarse,112)),'refined':roi_stats(decode(refined,112)),
            'inner_label_key_pixels':sum(v==KEY and 8*8<(i%112-55)**2+(i//112-55)**2<33*33
                                      for i,(v,) in enumerate(struct.iter_unpack('>H',refined)))}
        rows.append((name,[source,vinyl,keyed(coarse),view,zoom]))
        checks.append(name+': actual codec/native expansion/refine mask PASS')
    sheet(out/'pipeline-contact-sheet.png',rows)
    sheet(out/'pipeline-overview.png',rows[:3])
    # Constant sources must retain exact label RGB, including muted and gray.
    colors=[(255,0,0),(0,255,0),(0,0,255),(0,255,255),(255,0,255),(255,255,0),
            (0,0,0),(255,255,255),(128,128,128),(130,125,120),(3,253,5)]
    constant=[]
    for color in colors:
        rgb,trace=traced(function,encoded(Image.new('RGB',(300,300),color),format='PNG'))
        assert set(trace['label'].get_flattened_data())=={color}
        raw_color=native.quality_color(*color);logical=((raw_color&255)<<8)|(raw_color>>8)
        constant.append({'source_rgb':color,'label_rgb_unchanged':True,'logical565':f'{logical:04X}','keys_out':logical==KEY})
    metrics['constant_colors']=constant;checks.append('11 solid RGB labels unchanged PASS')
    # Three 256-value ramps through the real codec and real LVGL macro.
    maxima=[]
    for channel in range(3):
        rgb=bytes(value if c==channel else 0 for i in range(112*112) for c in range(3) for value in [i%256])
        packed=codec['pack_compact_rgb565'](rgb);decoded=decode(packed,80);error=[];visited=set()
        for y in range(80):
            for x in range(80):
                sx=((2*x+1)*112)//160;sy=((2*y+1)*112)//160;value=(sy*112+sx)%256;visited.add(value)
                color=[0,0,0];color[channel]=value
                raw=native.quality_color(*color)
                assert packed[(y*80+x)*2:(y*80+x)*2+2]==bytes((raw&255,raw>>8))
                error.append(abs(decoded.getpixel((x,y))[channel]-value))
        assert len(visited)==256;maxima.append(max(error))
    assert maxima==[7,3,7];metrics['quantization_max_code_error']=maxima
    checks.append('768 channel codes: Python packing = native LVGL bytes; error7/3/7 PASS')
    # Metadata does not change this converter; special-profile correction does.
    srgb,linear=profiles();source=Image.new('RGB',(300,300),(64,128,192))
    plain=function(encoded(source,format='PNG'));tagged=function(encoded(source,format='PNG',icc_profile=srgb))
    linear_result=function(encoded(source,format='PNG',icc_profile=linear))
    assert plain==tagged==linear_result
    corrected=ImageCms.profileToProfile(source,ImageCms.ImageCmsProfile(io.BytesIO(linear)),
                                      ImageCms.ImageCmsProfile(io.BytesIO(srgb)),outputMode='RGB')
    assert corrected.getpixel((0,0))!=source.getpixel((0,0))
    source.save(out/'icc-linear-stored-codes.png',icc_profile=linear);corrected.save(out/'icc-linear-to-srgb-reference.png',icc_profile=srgb)
    metrics['icc']={'stored_codes':source.getpixel((0,0)),'explicit_linear_to_srgb':corrected.getpixel((0,0)),
                    'product_untagged_srgb_and_linear_identical':True,'synthetic_special_profile_not_normal_srgb':True}
    checks.append('sRGB tag no change; linear-TRC profile ignored; explicit CMS reference differs PASS')
    from PIL.PngImagePlugin import PngInfo
    info=PngInfo();info.add(b'gAMA',struct.pack('>I',100000))
    assert function(encoded(source,format='PNG',pnginfo=info))==plain
    checks.append('PNG gamma1.0 metadata ignored PASS')
    alpha=Image.new('RGBA',(300,300),(255,32,16,0))
    alpha_rgb,trace=traced(function,encoded(alpha,format='PNG'))
    assert trace['label'].getpixel((40,40))==(255,32,16)
    metrics['alpha']={'fully_transparent_stored_rgb':(255,32,16),'actual_visible_label':trace['label'].getpixel((40,40)),
                      'explicit_composite_on_gray':Image.alpha_composite(Image.new('RGBA',alpha.size,(128,128,128,255)),alpha).convert('RGB').getpixel((0,0)),
                      'straight_png_no_generic_unpremultiply_required':True}
    checks.append('encoded PNG alpha dropped without compositing PASS')
    exif=Image.Exif();exif[274]=6
    image=cases['swatches'][0]
    assert function(encoded(image,format='JPEG',quality=95))==function(encoded(image,format='JPEG',quality=95,exif=exif))
    checks.append('JPEG EXIF orientation6 ignored PASS')
    save_json(out/'metrics.json',metrics)
    save_json(out/'checks.json',{'classification':'Synthetic host quality checks only; no TFT/COM/app/firmware execution',
        'checks':checks,'checks_passed':len(checks),'python':sys.version,'pillow':PIL.__version__,
        'lcms':features.version('littlecms2'),'firmware_source_only':True,'physical_acceptance':False})
    for name,item in pins.items():
        base=APP/'source' if name.startswith('companion/') else FW/'source-frozen'
        path=ROOT/name if name.startswith(('tests/','.pio/')) else base/name
        expected=item.get('installed_source_sha256',item.get('sha256'));assert sha(path)==expected
    outputs={str(p.relative_to(out)).replace('\\','/'):sha(p) for p in sorted(out.rglob('*')) if p.is_file()}
    save_json(out/'manifest.json',{'synthetic':True,'tft_measured':False,'files':outputs,
        'audit_script_sha256':sha(Path(__file__)),'native_reference_sha256':sha(HERE/'native_reference.cpp')})
    print(json.dumps({'output':str(out),'checks_passed':len(checks),'metrics_sha256':sha(out/'metrics.json'),
                      'manifest_sha256':sha(out/'manifest.json'),'quantization_error':maxima,'icc':metrics['icc'],
                      'alpha':metrics['alpha']},ensure_ascii=False,indent=2))


if __name__=='__main__':main()

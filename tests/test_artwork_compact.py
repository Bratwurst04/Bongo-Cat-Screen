"""Compact codec, actual firmware parser/slots and explicitly conservative models."""
import base64
import configparser
import ctypes
import io
from pathlib import Path
import unittest
from unittest.mock import Mock,patch
import zlib
from PIL import Image

import test_artwork_v2 as legacy
import artwork_fast_host as queue_host
from compact_art_host import BUILD,ROOT,Pixels,load_host,snapshot
from artwork_codec import COMPACT_BYTES,pack_compact_rgb565
from engine import ARTWORK_V2_FRAME_BYTES

# All old host helpers are redirected before any compilation, including standalone discovery.
queue_host.BUILD=BUILD/'queue-host'
MODEL_RESULTS=[]
CHALLENGE='0123456789ABCDEF'
RGB=bytes((i*37+11)&255 for i in range(ARTWORK_V2_FRAME_BYTES))


def expected_words(rgb):
    # Independent image-library nearest sampling, followed by direct RGB565 math.
    im=Image.frombytes('RGB',(112,112),rgb).resize((80,80),Image.Resampling.NEAREST).resize((112,112),Image.Resampling.NEAREST)
    words=[]
    for r,g,b in im.getdata():
        value=((r>>3)<<11)|((g>>2)<<5)|(b>>3)
        words.append(((value&255)<<8)|(value>>8))
    return words


class CompactModel(queue_host.WireModel):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.receiver=load_host();self.receiver.ca_reset()
        self.parse_us=500 # explicitly more conservative than C's 80us; still not a benchmark

    def handle_line(self,line):
        if line.startswith(b'MEDIA_ART2_'):
            ok=self.receiver.ca_ok();bad=self.receiver.ca_error()
            self.receiver.ca_line(line,int(self.now/1000))
            if self.receiver.ca_ok()>ok:
                self.committed=bytes(snapshot(self.receiver));self.reply(True)
            elif self.receiver.ca_error()>bad:self.reply(False)
        else:
            if line.startswith(b'MEDIA_TRACK_CONTEXT:'):
                self.receiver.ca_context(int(line.split(b':')[1]),int(self.now/1000))
            self.metadata.append((self.now,line))


class ArtworkCompactTests(unittest.TestCase):
    def setUp(self):self.h=load_host();self.h.ca_reset()

    def engine(self,baud=921600,cap=True):
        e=legacy.ArtworkV2Tests().make_engine();e.baudrate=baud;e._artwork_v2_supported=True
        e._artwork_v2_challenge=CHALLENGE;e._artwork_v2_fast_challenge=''
        e._artwork_v2_compact_challenge=CHALLENGE if cap else ''
        e._on_media_update(legacy.ArtworkV2Tests.snapshot('song'),None)
        return e

    def feed(self,payload,crc=None,ident=7,header='MEDIA_ART2_BEGIN565'):
        if crc is None:crc=zlib.crc32(payload)&0xffffffff
        edge=80 if header.endswith('565') else 112
        self.h.ca_line(f'{header}:{ident}:{edge}:{edge}:{len(payload)}:{crc:08X}'.encode(),1)
        for offset in range(0,len(payload),128):
            self.h.ca_line(f'MEDIA_ART2_CHUNK:{ident}:{offset}:'.encode()+base64.b64encode(payload[offset:offset+128]),2)
        self.h.ca_line(f'MEDIA_ART2_END:{ident}'.encode(),3)

    def send(self,e,attempt=0,mutate=None):
        writes=[]
        def write(p):
            writes.append(p)
            for line in p.splitlines():self.h.ca_line(line,10)
            if mutate:mutate(p)
            if self.h.ca_error() or self.h.ca_ok():
                e._artwork_v2_ack_result=bool(self.h.ca_ok());e._artwork_ack.set()
            return len(p)
        e.serial_conn.write.side_effect=write
        with patch('engine.time.sleep') as sleep,patch('engine.diagnostics.event'):
            e._send_artwork_v2(e.serial_conn,'song',RGB,attempt)
        return writes,sleep

    def test_codec_size_exact_chroma_and_lvgl_byte_order(self):
        for rgb,wire,native in [((255,0,0),b'\xf8\x00',0x00f8),((0,255,0),b'\x07\xe0',0xe007),
                              ((0,0,255),b'\x00\x1f',0x1f00),((255,255,255),b'\xff\xff',0xffff)]:
            raw=bytes(rgb)*(112*112);packed=pack_compact_rgb565(raw)
            self.assertEqual(len(packed),12800);self.assertEqual(packed,wire*6400)
            self.assertEqual(self.h.ca_color(*rgb),native)
        with self.assertRaises(ValueError):pack_compact_rgb565(RGB[:-1])

    def test_reverse_expansion_matches_independent_reference_and_has_guarded_bounds(self):
        packed=pack_compact_rgb565(RGB);self.feed(packed)
        self.assertEqual(self.h.ca_ok(),1);self.assertEqual(list(snapshot(self.h)),expected_words(RGB))
        self.assertEqual(set(snapshot(self.h,0)),{1111},'committed old slot may not be overwritten')
        array=(ctypes.c_ushort*(12544+8))(*([54321]*(12544+8)))
        self.assertFalse(self.h.ca_expand(array,12543));self.assertEqual(set(array),{54321})
        for i in range(6400):array[i]=i
        self.assertTrue(self.h.ca_expand(array,12544));self.assertEqual(list(array[12544:]),[54321]*8)
        ref=Image.new('I',(80,80));ref.putdata(list(range(6400)))
        self.assertEqual(list(array[:12544]),list(ref.resize((112,112),Image.Resampling.NEAREST).getdata()))

    def test_mask_from_existing_vinyl_has_no_interpolated_green_halo(self):
        from media_bridge import WindowsMediaBridge
        im=Image.new('RGB',(200,200),(213,41,67));blob=io.BytesIO();im.save(blob,format='PNG')
        raw=WindowsMediaBridge._to_vinyl_rgb888(blob.getvalue());packed=pack_compact_rgb565(raw);self.feed(packed)
        words=list(snapshot(self.h));self.assertEqual(words,expected_words(raw))
        self.assertEqual(words[0],self.h.ca_color(0,255,0));self.assertEqual(words[-1],self.h.ca_color(0,255,0))
        # Every output colour is a quantised original pixel: nearest creates no edge mixture.
        source={self.h.ca_color(*raw[i:i+3]) for i in range(0,len(raw),3)}
        self.assertTrue(set(words)<=source)

    def test_real_sender_and_parser_use_100_chunks_and_keep_112_descriptor_slot(self):
        e=self.engine();e._artwork_v2_next_id=65534;writes,sleep=self.send(e)
        chunks=[p for p in writes if p.startswith(b'MEDIA_ART2_CHUNK:')]
        self.assertTrue(writes[0].startswith(b'MEDIA_ART2_BEGIN565:65535:80:80:12800:'))
        self.assertEqual(sum(p.count(b'\n') for p in chunks),100);self.assertEqual(len(chunks),13)
        self.assertEqual(sum(map(len,writes)),20179);sleep.assert_not_called()
        self.assertEqual(self.h.ca_id(),65535);self.assertEqual(list(snapshot(self.h)),expected_words(RGB))
        descriptor=(ctypes.c_int*4)();self.h.ca_descriptor(descriptor)
        self.assertEqual(list(descriptor),[112,112,25088,1])

    def test_compact_retry_keeps_codec_with_single_frame_15ms_pacing(self):
        e=self.engine();writes,sleep=self.send(e,1)
        chunks=[p for p in writes if p.startswith(b'MEDIA_ART2_CHUNK:')]
        self.assertTrue(writes[0].startswith(b'MEDIA_ART2_BEGIN565:'));self.assertEqual(len(chunks),100)
        self.assertTrue(all(p.count(b'\n')==1 for p in chunks));self.assertEqual(sleep.call_count,100)
        self.assertTrue(all(c.args==(0.015,) for c in sleep.call_args_list));self.assertEqual(self.h.ca_ok(),1)

    def test_legacy_peer_and_stale_or_wrong_baud_caps_never_receive_compact_payload(self):
        for baud,cap,stale in [(230400,True,False),(921600,False,False),(921600,True,True)]:
            self.h.ca_reset();e=self.engine(baud,cap)
            if stale:e._artwork_v2_compact_challenge='FEDCBA9876543210'
            writes,_=self.send(e)
            self.assertTrue(writes[0].startswith(b'MEDIA_ART2_BEGIN:'));self.assertEqual(self.h.ca_ok(),1)
            out=Pixels();self.h.ca_legacy_pixels(RGB,out);self.assertEqual(list(snapshot(self.h)),list(out))
        old=load_host(False);old.ca_reset()
        old.ca_line(b'MEDIA_ART2_BEGIN565:1:80:80:12800:00000000',1)
        self.assertFalse(old.ca_receiving());self.assertEqual(old.ca_active(),0)

    def test_reader_requires_fresh_distinct_compact_cap_and_new_sync_clears_it(self):
        e=self.engine(cap=False);e._artwork_v2_fast_challenge=CHALLENGE
        replies=iter([f'CAPS:MEDIA_ART2_RGB56580:FEDCBA9876543210:921600\n'.encode(),
            f'CAPS:MEDIA_ART2_FAST:{CHALLENGE}:921600\n'.encode(),
            f'CAPS:MEDIA_ART2_RGB56580:{CHALLENGE}:921600\n'.encode()]);count=0
        def read():
            nonlocal count
            count+=1
            self.assertEqual(e._artwork_v2_compact_challenge,'')
            if count==3:e.running=False
            return next(replies)
        e.serial_conn.readline.side_effect=read
        with patch('engine.diagnostics.event'):e._serial_reader_loop()
        self.assertEqual(e._artwork_v2_compact_challenge,CHALLENGE)
        e.get_system_stats=Mock(return_value=(1,2));e.send_command=Mock(return_value=True)
        with patch('engine.secrets.token_hex',return_value='abcd1234abcd1234'),patch('builtins.print'):e.send_initial_sync()
        self.assertEqual(e._artwork_v2_compact_challenge,'')

    def test_crc_order_bad_length_and_incomplete_frame_never_commit(self):
        packed=pack_compact_rgb565(RGB)
        self.feed(packed,crc=(zlib.crc32(packed)^1)&0xffffffff)
        self.assertEqual(self.h.ca_active(),0);self.assertEqual(self.h.ca_reason(),b'art2_crc')
        self.h.ca_reset();self.h.ca_line(b'MEDIA_ART2_BEGIN565:7:80:80:12800:00000000',1)
        self.h.ca_line(b'MEDIA_ART2_CHUNK:7:128:'+base64.b64encode(packed[:128]),2)
        self.assertEqual(self.h.ca_active(),0);self.assertEqual(self.h.ca_reason(),b'art2_offset')
        self.h.ca_reset();self.h.ca_line(b'MEDIA_ART2_BEGIN565:7:112:112:12800:00000000',1)
        self.assertFalse(self.h.ca_receiving())
        self.h.ca_line(b'MEDIA_ART2_BEGIN565:7:80:80:12800:00000000',2)
        self.h.ca_line(b'MEDIA_ART2_END:7',3);self.assertEqual(self.h.ca_reason(),b'art2_length')

    def test_latest_context_aborts_staging_without_touching_committed_slot(self):
        self.feed(pack_compact_rgb565(RGB));previous=list(snapshot(self.h));active=self.h.ca_active()
        self.h.ca_line(b'MEDIA_ART2_BEGIN565:8:80:80:12800:00000000',4)
        self.h.ca_line(b'MEDIA_ART2_CHUNK:8:0:'+base64.b64encode(bytes(128)),5)
        self.h.ca_context(123456,6);self.assertFalse(self.h.ca_receiving())
        self.h.ca_line(b'MEDIA_ART2_END:8',7)
        self.assertEqual(self.h.ca_active(),active);self.assertEqual(list(snapshot(self.h)),previous)

    def test_rapid_abort_and_partialwrite_do_not_send_end_or_commit_old_frame(self):
        import serial
        e=self.engine();writes=[];switched=False
        def write(p):
            nonlocal switched
            writes.append(p)
            for line in p.splitlines():self.h.ca_line(line,1)
            if p.startswith(b'MEDIA_ART2_CHUNK:') and not switched:
                switched=True;e._on_media_update(legacy.ArtworkV2Tests.snapshot('new'),None)
            return len(p)
        e.serial_conn.write.side_effect=write
        with patch('engine.diagnostics.event'):e._send_artwork_v2(e.serial_conn,'song',RGB,0)
        self.assertEqual(b''.join(writes).count(b'MEDIA_ART2_CHUNK:'),8)
        self.assertNotIn(b'MEDIA_ART2_END:',b''.join(writes));self.assertEqual(self.h.ca_ok(),0)
        self.h.ca_reset();e=self.engine();writes.clear()
        def partial(p):
            writes.append(p)
            if p.startswith(b'MEDIA_ART2_BEGIN'):self.h.ca_line(p.rstrip(),1);return len(p)
            return len(p)-1
        e.serial_conn.write.side_effect=partial
        with patch('engine.diagnostics.event'),self.assertRaises(serial.SerialTimeoutException):e._send_artwork_v2(e.serial_conn,'song',RGB,0)
        self.assertNotIn(b'MEDIA_ART2_END:',b''.join(writes));self.assertEqual(self.h.ca_active(),0)
        self.assertFalse(e._artwork_transfer_active.is_set())

    def test_error_at_last_batch_prevents_end_and_false_sent_log(self):
        e=self.engine();writes=[]
        def write(p):
            writes.append(p)
            if b'MEDIA_ART2_CHUNK:1:12288:' in p:
                e._artwork_v2_ack_result=False;e._artwork_ack.set()
            return len(p)
        e.serial_conn.write.side_effect=write
        with patch('engine.diagnostics.event') as event:e._send_artwork_v2(e.serial_conn,'song',RGB,0)
        self.assertNotIn(b'MEDIA_ART2_END:',b''.join(writes));self.assertTrue(e._artwork_retry)
        self.assertFalse(any(c.args==('ART_SENT',) for c in event.call_args_list))

    def test_separate_profile_does_not_advertise_old_fast_tier_or_change_default(self):
        ini=configparser.ConfigParser(interpolation=None);ini.read(ROOT/'platformio.ini')
        profile=ini['env:esp32-024r-spotify-compact80']
        self.assertIn('BONGO_ART2_COMPACT80=1',profile['build_flags']);self.assertNotIn('BONGO_ART2_FAST_TIER',profile['build_flags'])
        self.assertEqual(profile['monitor_speed'],'921600');self.assertEqual(ini['env:esp32-024r-spotify']['upload_speed'],'115200')
        self.assertEqual(ini['platformio']['default_envs'],'esp32-024r-spotify-fastserial')

    def model(self,name,**kwargs):
        e=self.engine();m=CompactModel(e,**kwargs)
        e.serial_conn.write.side_effect=m.write;e.serial_conn.flush.side_effect=m.flush
        with patch('engine.time.sleep',side_effect=m.sleep),patch('engine.time.monotonic',side_effect=lambda:m.now/1e6),\
             patch.object(e._artwork_ack,'wait',side_effect=m.wait),patch('engine.diagnostics.event'):
            e._send_artwork_v2(e.serial_conn,'song',RGB,0)
        expected=bytes(Pixels(*expected_words(RGB)))
        result=dict(name=name,assumptions=dict(kwargs,parse_us=m.parse_us,loop_delay_ms=m.limits['loop_delay_ms']),
            wire_ms=round(m.wire_end/1000,3),ack_ms=round(m.acks[-1][0]/1000,3) if m.acks else None,
            committed=m.committed==expected,peak_queue=m.peak_queue,peak_uart=m.peak_uart,
            dropped=m.dropped,touch_services=len(m.touch_times),retry=e._artwork_retry is not None)
        MODEL_RESULTS.append(result);return m,result

    def test_models_larger_paint_pauses_preserve_frame_and_show_latency_limits(self):
        for name,options in [('paint50',dict(render_ms=50)),('paint80',dict(render_ms=80)),
            ('blackout300_paint50',dict(blackout_ms=300,render_ms=50)),('paint150',dict(render_ms=150)),
            ('flush50_paint50',dict(flush_poll_ms=50,render_ms=50))]:
            with self.subTest(name=name):
                m,r=self.model(name,**options)
                self.assertTrue(r['committed']);self.assertEqual(m.dropped,0);self.assertLessEqual(m.peak_queue,96)
                self.assertGreater(len(m.touch_times),1)
                if name=='paint150':self.assertGreater(r['ack_ms'],1000)
                elif name!='flush50_paint50':self.assertLess(r['ack_ms'],1000)


if __name__=='__main__':unittest.main()

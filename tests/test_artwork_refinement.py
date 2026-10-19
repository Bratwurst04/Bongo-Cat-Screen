"""Actual sender + reader + firmware CRC/slots/render, without device/API."""
import ctypes
import math
from dataclasses import replace
from pathlib import Path
import queue
from threading import Event,Lock,RLock,Thread
import time
import unittest
from unittest.mock import Mock,patch

import test_artwork_v2 as legacy
from turntable_face_host import load_host,frame,snapshot,transfer,Pixels

TOKEN='0123456789ABCDEF';NEXT='FEDCBA9876543210'
RGB=bytes(v for y in range(112) for x in range(112) for v in
          ((240,45,25) if (x+y)%2 else (20,105,230)))
OTHER=bytes((35,195,85))*(112*112)

def until(predicate,seconds=0.8):
    end=time.monotonic()+seconds
    while not predicate() and time.monotonic()<end:Event().wait(0.002)
    if not predicate():raise AssertionError('Expected bounded asynchronous result')

class FirmwareWire:
    """Native production parser/notify; returned lines use the real reader."""
    def __init__(self,engine,order='ack-first'):
        self.engine=engine;self.h=load_host();self.h.ca_reset()
        self.h.ff_generation(TOKEN.encode());self.h.ff_play(True,20,200);frame(self.h,0)
        self.h.ca_context(101,0);transfer(self.h,OTHER,1,0);frame(self.h,200)
        self.rx=queue.Queue();self.lock=RLock();self.writes=[];self.is_open=True
        self.now=1000;self.order=order;self.render_compact=True;self.seen_shown=self.h.ff_shown()
        self.current_compact=False;self.compact_ends=0;self.full_ends=0
        self.hold_full_ack=False;self.drop_full_end=False;self.drop_compact_end=False;self.corrupt_full=False
        self.after_write=None;self.before_full=None;self.full_started=Event();self.full_end=Event()
        self.low_pixels=None;self.low_held=True
    def shown_line(self):
        if self.h.ff_shown()==self.seen_shown:return None
        self.seen_shown=self.h.ff_shown()
        return f'MEDIA_ART2_SHOWN:{self.h.ff_shown_id()}:'.encode()+self.h.ff_shown_challenge()+b'\n'
    def render(self,now,visible=True):
        with self.lock:
            f=frame(self.h,now,visible);line=self.shown_line()
            if line:self.rx.put(line)
            return f
    def write(self,payload):
        self.writes.append(payload)
        with self.lock:
            for line in payload.splitlines():
                if line.startswith(b'MEDIA_ART_DEFAULT'):self.h.ff_default()
                elif line.startswith(b'MEDIA_TRACK_CONTEXT:'):
                    self.h.ca_context(int(line.split(b':')[1]),self.now)
                elif line==b'MEDIA_STATE:NONE':self.h.ff_none()
                elif line.startswith(b'MEDIA_ART2_'):
                    if line.startswith(b'MEDIA_ART2_BEGIN'):
                        self.current_compact=line.startswith(b'MEDIA_ART2_BEGIN565:')
                        if not self.current_compact:
                            self.full_started.set()
                            if self.before_full:self.before_full()
                    if ((self.drop_full_end and not self.current_compact or self.drop_compact_end and self.current_compact)
                            and line.startswith(b'MEDIA_ART2_END:')):
                        self.full_end.set();continue
                    actual=line
                    if self.corrupt_full and not self.current_compact and line.startswith(b'MEDIA_ART2_CHUNK:'):
                        fields=line.split(b':',3)
                        fields[3]=(b'A' if fields[3][:1]!=b'A' else b'B')+fields[3][1:]
                        actual=b':'.join(fields)
                    if not self.current_compact and line.startswith(b'MEDIA_ART2_CHUNK:') and self.low_pixels:
                        self.low_held &= bytes(snapshot(self.h))==self.low_pixels
                    ok=self.h.ca_ok();bad=self.h.ca_error()
                    self.h.ca_line(actual,self.now)
                    if self.h.ca_error()>bad:
                        self.rx.put(f'MEDIA_ART2_ERROR:{self.h.ca_id()}\n'.encode())
                    if self.h.ca_ok()>ok:
                        ack=f'MEDIA_ART2_OK:{self.h.ca_id()}\n'.encode();shown=None
                        if self.current_compact:
                            self.compact_ends+=1
                            if self.render_compact:
                                frame(self.h,self.now+880);shown=self.shown_line()
                                self.low_pixels=bytes(snapshot(self.h))
                        else:self.full_ends+=1;self.full_end.set()
                        if shown and self.order=='shown-first':self.rx.put(shown)
                        if self.current_compact or not self.hold_full_ack:self.rx.put(ack)
                        if shown and self.order=='ack-first':self.rx.put(shown)
        if self.after_write:self.after_write(payload)
        return len(payload)
    def flush(self):pass
    def readline(self):
        try:return self.rx.get(timeout=0.02)
        except queue.Empty:return b''
    def close(self):self.is_open=False

def make_pair(order='ack-first',refine=True):
    e=legacy.ArtworkV2Tests().make_engine();e.baudrate=921600;e._data_lock=Lock()
    e._artwork_v2_supported=True;e._artwork_v2_challenge=TOKEN
    e._artwork_v2_compact_challenge=TOKEN;e._artwork_v2_fast_challenge=TOKEN
    e._artwork_v2_refine_challenge=TOKEN if refine else '';e._artwork_refinement=None
    e.media_bridge=Mock();wire=FirmwareWire(e,order);e.serial_conn=wire
    e._on_media_update(legacy.ArtworkV2Tests.snapshot('song'),RGB)
    reader=Thread(target=e._serial_reader_loop,daemon=True);reader.start()
    return e,wire,reader

def send_primary(e):
    key,art,attempt=e._artwork_queue.get_nowait()
    with patch('engine.time.sleep'):
        e._send_artwork_v2(e.serial_conn,key,art,attempt)

class RefinementTests(unittest.TestCase):
    def pair(self,*args,**kwargs):
        e,w,t=make_pair(*args,**kwargs)
        self.addCleanup(self.stop,e,w,t);return e,w
    @staticmethod
    def stop(e,w,t):e.running=False;w.rx.put(b'\n');t.join(0.5)
    def ready(self,e,w):
        send_primary(e);until(lambda:e._artwork_refinement is not None and e._artwork_refinement['shown'])
        job=e._take_artwork_refinement();self.assertIsNotNone(job);return job
    def refine(self,e,job):
        with patch('engine.time.sleep'):
            e._send_artwork_v2(e.serial_conn,job['track'],job['artwork'],0,job)
    def test_ack_and_shown_both_orders_are_retained_and_refine_once(self):
        for order in ('ack-first','shown-first'):
            e,w=self.pair(order);job=self.ready(e,w)
            self.assertTrue(job['acknowledged']);self.assertTrue(job['shown'])
            self.assertIsNone(e._take_artwork_refinement())
            self.refine(e,job);self.assertIsNone(e._artwork_refinement)
            self.assertEqual((w.compact_ends,w.full_ends),(1,1))
    def test_compact_ack_alone_cannot_overwrite_waiting_staging(self):
        e,w=self.pair();w.render_compact=False
        old=bytes(snapshot(w.h));send_primary(e)
        self.assertIsNone(e._take_artwork_refinement());self.assertEqual(bytes(snapshot(w.h)),old)
        self.assertEqual(w.full_ends,0)
        w.render(1880);until(lambda:e._artwork_refinement['shown'])
        self.assertIsNotNone(e._take_artwork_refinement())
    def test_shown_alone_without_ack_never_starts_optional_transfer(self):
        e,w=self.pair();w.render_compact=False
        # Deterministically arm by holding END before native completion.
        at_end=Event();release=Event()
        def hook(payload):
            if payload.startswith(b'MEDIA_ART2_CHUNK:') and not at_end.is_set():
                at_end.set();release.wait(0.5)
        w.after_write=hook
        t=Thread(target=send_primary,args=(e,));t.start();self.assertTrue(at_end.wait(0.5))
        job=e._artwork_refinement
        w.rx.put(f'MEDIA_ART2_SHOWN:{job["id"]}:{TOKEN}\n'.encode())
        until(lambda:job['shown']);self.assertFalse(job['acknowledged']);self.assertIsNone(e._take_artwork_refinement())
        release.set();t.join(1);self.assertFalse(t.is_alive())
    def test_full_bytes_not_repacked_and_pacing_is_conservative_even_with_fast_cap(self):
        e,w=self.pair();job=self.ready(e,w)
        with patch('engine.pack_compact_rgb565',side_effect=AssertionError('Do not repack refinement')):
            self.refine(e,job)
        header=next(p for p in w.writes if p.startswith(b'MEDIA_ART2_BEGIN:'))
        self.assertIn(b':112:112:37632:',header)
        full=w.writes[w.writes.index(header)+1:]
        chunks=[p for p in full if p.startswith(b'MEDIA_ART2_CHUNK:')]
        self.assertEqual(len(chunks),147);self.assertTrue(all(p.count(b'\n')==2 for p in chunks))
        self.assertTrue(w.low_held);self.assertEqual(w.full_ends,1)
    def test_actual_pixels_gain_detail_without_geometry_or_new_motion(self):
        e,w=self.pair();job=self.ready(e,w)
        low=bytes(snapshot(w.h));before=w.render(4000)
        self.refine(e,job);high=bytes(snapshot(w.h));after=w.render(4000)
        expected=Pixels();w.h.ca_legacy_pixels.argtypes=[ctypes.c_char_p,ctypes.POINTER(ctypes.c_ushort)]
        w.h.ca_legacy_pixels(RGB,expected)
        self.assertEqual(high,bytes(expected));self.assertNotEqual(low,high)
        self.assertEqual(tuple(before)[:13],tuple(after)[:13]);self.assertEqual(tuple(after)[10:13],(0,0,0))
        defaults=sum(b'MEDIA_ART_DEFAULT' in p for p in w.writes)
        self.assertEqual(defaults,1)
        out_low=Pixels();out_high=Pixels();palette=(ctypes.c_ushort*5)(0,1,2,3,4)
        low_words=Pixels.from_buffer_copy(low)
        for out,pixels in ((out_low,low_words),(out_high,expected)):
            self.assertTrue(w.h.tt_render(out,12544,pixels,after,0,32768,palette))
        self.assertEqual([i for i,p in enumerate(out_low) if p!=0],[i for i,p in enumerate(out_high) if p!=0])
        self.assertNotEqual(bytes(out_low),bytes(out_high))
    def test_real_vinyl_refinement_preserves_exact_low_mask_and_improves_cache_detail(self):
        from media_bridge import WindowsMediaBridge
        root=Path(__file__).resolve().parents[1]
        rgb=WindowsMediaBridge._to_vinyl_rgb888((root/'visuals/artwork-compact80-2026-10-18/r1/fixture-cover.png').read_bytes())
        e,w=self.pair();e._on_media_update(legacy.ArtworkV2Tests.snapshot('song'),rgb)
        job=self.ready(e,w);low=Pixels.from_buffer_copy(bytes(snapshot(w.h)))
        before=w.render(4000)
        self.refine(e,job);high=snapshot(w.h)
        after=w.render(4000)
        expected=Pixels();w.h.ca_legacy_pixels.argtypes=[ctypes.c_char_p,ctypes.POINTER(ctypes.c_ushort)]
        w.h.ca_legacy_pixels(rgb,expected);chroma=0xe007
        self.assertEqual([p==chroma for p in low],[p==chroma for p in high])
        self.assertTrue(all(a==b for a,b,c in zip(high,expected,low) if b!=chroma and c!=chroma))
        self.assertGreater(sum(a!=b for a,b in zip(low,high)),1000)
        self.assertIs(e._cached_artwork,rgb)
        self.assertEqual(tuple(before)[:13],tuple(after)[:13])
        palette=(ctypes.c_ushort*5)(chroma,1,2,3,4)
        for compact in (False,True):
            g0=(ctypes.c_int*10)();g1=(ctypes.c_int*10)()
            w.h.tt_geometry(before,compact,g0);w.h.tt_geometry(after,compact,g1)
            self.assertEqual(tuple(g0),tuple(g1));self.assertEqual(g0[2],320 if compact else 384)
            for angle in (0,37,90):
                sine=round(math.sin(math.radians(angle))*32768);cosine=round(math.cos(math.radians(angle))*32768)
                masks=[];bounds=[]
                for pixels in (low,high):
                    out=Pixels();self.assertTrue(w.h.tt_render(out,12544,pixels,after,sine,cosine,palette))
                    mask=[p!=chroma for p in out];masks.append(mask)
                    pts=[(i%112,i//112) for i,p in enumerate(mask) if p]
                    bounds.append((min(x for x,y in pts),min(y for x,y in pts),max(x for x,y in pts),max(y for x,y in pts)))
                self.assertEqual(masks[0],masks[1]);self.assertEqual(bounds[0],bounds[1])
    def test_crc_failure_keeps_low_and_never_schedules_high_retry(self):
        e,w=self.pair();job=self.ready(e,w);low=bytes(snapshot(w.h));w.corrupt_full=True
        self.refine(e,job)
        self.assertEqual(bytes(snapshot(w.h)),low);self.assertIsNone(e._artwork_retry)
        self.assertIsNone(e._artwork_refinement);self.assertIsNone(e._take_due_artwork_v2_retry())
    def test_near_key_rgb_quantizing_to_chroma_cannot_add_a_transparent_hole(self):
        rgb=bytearray(bytes((240,0,0))*(112*112));index=56*112+1
        rgb[index*3:index*3+3]=bytes((3,253,5));rgb=bytes(rgb)
        e,w=self.pair();e._on_media_update(legacy.ArtworkV2Tests.snapshot('song'),rgb)
        job=self.ready(e,w);low=Pixels.from_buffer_copy(bytes(snapshot(w.h)))
        self.assertNotEqual(low[index],0xe007)
        self.refine(e,job);high=snapshot(w.h)
        self.assertEqual([p==0xe007 for p in low],[p==0xe007 for p in high])
        self.assertEqual(high[index],low[index])
    def test_new_track_and_same_track_cache_revision_abort_during_full_chunks(self):
        for same in (False,True):
            e,w=self.pair();job=self.ready(e,w);changed=Event()
            def change(payload):
                if w.full_started.is_set() and payload.startswith(b'MEDIA_ART2_CHUNK:') and not changed.is_set():
                    changed.set();e._on_media_update(legacy.ArtworkV2Tests.snapshot('song' if same else 'next'),OTHER)
            w.after_write=change;self.refine(e,job)
            self.assertTrue(changed.is_set());self.assertEqual(w.full_ends,0)
            self.assertTrue(any(p.startswith(b'MEDIA_ART2_ABORT:') for p in w.writes))
            self.assertIsNone(e._artwork_refinement);self.assertIsNone(e._artwork_retry)
            key,blob,_=e._artwork_queue.get_nowait();self.assertEqual(blob,OTHER)
    def test_held_refinement_ack_yields_quickly_to_next_compact(self):
        for same in (False,True):
            e,w=self.pair();job=self.ready(e,w);w.hold_full_ack=True
            t=Thread(target=self.refine,args=(e,job));t.start();self.assertTrue(w.full_end.wait(1))
            e._on_media_update(legacy.ArtworkV2Tests.snapshot('song' if same else 'next'),OTHER)
            t.join(0.4);self.assertFalse(t.is_alive(),'Refinement must not hold sender for the old 4s wait')
            w.after_write=None;send_primary(e)
            self.assertEqual(w.compact_ends,2)
            headers=[p for p in w.writes if p.startswith(b'MEDIA_ART2_BEGIN')]
            self.assertTrue(headers[-1].startswith(b'MEDIA_ART2_BEGIN565:'))
    def test_held_refinement_ack_yields_to_epoch_or_stop(self):
        for change in ('epoch','stop'):
            e,w=self.pair();job=self.ready(e,w);w.hold_full_ack=True
            t=Thread(target=self.refine,args=(e,job));t.start();self.assertTrue(w.full_end.wait(1))
            if change=='epoch':e._artwork_v2_epoch+=1
            else:e._stop_requested.set()
            t.join(0.4);self.assertFalse(t.is_alive());self.assertIsNone(e._artwork_refinement)
    def test_epoch_reconnect_and_stop_abort_pending_or_active_refinement(self):
        for change in ('epoch','connection','stop'):
            e,w=self.pair();job=self.ready(e,w);done=Event()
            def mutate(payload):
                if payload.startswith(b'MEDIA_ART2_CHUNK:') and w.full_started.is_set() and not done.is_set():
                    done.set()
                    if change=='epoch':e._artwork_v2_epoch+=1
                    elif change=='connection':e.serial_conn=Mock(is_open=True)
                    else:e._stop_requested.set()
            w.after_write=mutate;self.refine(e,job)
            self.assertEqual(w.full_ends,0);self.assertIsNone(e._artwork_refinement)
    def test_old_challenge_or_captured_epoch_cannot_release_same_id(self):
        e,w=self.pair();w.render_compact=False;send_primary(e);job=e._artwork_refinement
        for generation,challenge in [((job['epoch']-1,TOKEN),TOKEN),((job['epoch'],TOKEN),NEXT)]:
            e._record_artwork_shown(w,generation,job['id'],challenge)
            self.assertIsNone(e._take_artwork_refinement());self.assertFalse(job['shown'])
        w.rx.put(f'MEDIA_ART2_SHOWN:{job["id"]}:{NEXT}\n'.encode());Event().wait(0.03)
        self.assertFalse(job['shown']);w.render(1880);until(lambda:job['shown'])
        self.assertIs(e._take_artwork_refinement(),job)
    def test_notice_generation_retires_old_rx_and_notice_without_resetting_disc(self):
        h=load_host();h.ca_reset();h.ff_generation(TOKEN.encode());h.ff_play(True,0,200)
        frame(h,0);h.ca_context(101,0);transfer(h,OTHER,10,0);frame(h,200)
        shown=h.ff_shown();old=bytes(snapshot(h))
        h.ca_context(102,1000);transfer(h,RGB,11,1300,finish=False)
        h.ff_generation(NEXT.encode());self.assertFalse(h.ca_receiving());self.assertEqual(bytes(snapshot(h)),old)
        h.ca_line(b'MEDIA_ART2_END:11',1400);frame(h,1880)
        self.assertEqual(h.ff_shown(),shown)
        transfer(h,RGB,11,1900);frame(h,1920)
        self.assertEqual(h.ff_shown_id(),11);self.assertEqual(h.ff_shown_challenge(),NEXT.encode())
    def test_same_nonce_fallback_query_keeps_staging_and_pending_notice(self):
        h=load_host();h.ca_reset();h.ff_generation(TOKEN.encode());frame(h,0)
        h.ca_context(101,0);transfer(h,OTHER,10,0);frame(h,200)
        h.ca_context(102,1000);transfer(h,RGB,11,1300,finish=False)
        self.assertTrue(h.ca_receiving());old=bytes(snapshot(h))
        h.ff_generation(TOKEN.encode());self.assertTrue(h.ca_receiving());self.assertEqual(bytes(snapshot(h)),old)
        h.ca_line(b'MEDIA_ART2_END:11',1400);frame(h,1880)
        self.assertEqual(h.ff_shown_id(),11);self.assertEqual(h.ff_shown_challenge(),TOKEN.encode())
    def test_refinement_dispatch_never_becomes_raw_or_requeued_coarse_after_race(self):
        for change in ('capability','epoch','metadata'):
            e,w=self.pair();job=self.ready(e,w);job['started']=False;before=len(w.writes)
            take=e._take_artwork_refinement;gets=0
            def pop(timeout):
                nonlocal gets
                gets+=1
                if gets>1:e.running=False
                raise queue.Empty
            def race():
                result=take()
                if result is not None:
                    if change=='capability':e._artwork_v2_supported=False
                    elif change=='epoch':e._artwork_v2_epoch+=1;e._artwork_v2_supported=False
                    else:e._last_media_track_key=''
                return result
            with patch.object(e._artwork_queue,'get',side_effect=pop),\
                    patch.object(e,'_take_artwork_refinement',side_effect=race),\
                    patch.object(e,'_flush_latest_media',return_value=None):
                e._artwork_sender_loop()
            self.assertEqual(len(w.writes),before);self.assertTrue(e._artwork_queue.empty())
            self.assertIsNone(e._artwork_refinement)
    def test_old_peers_or_unconfirmed_refine_cap_keep_single_existing_image(self):
        e,w=self.pair(refine=False);send_primary(e)
        self.assertIsNone(e._artwork_refinement);self.assertIsNone(e._take_artwork_refinement())
        self.assertFalse(any(p.startswith(b'MEDIA_ART2_BEGIN:') for p in w.writes))
    def test_refine_cap_is_accepted_only_for_fresh_challenge_by_real_reader(self):
        e,w=self.pair(refine=False)
        w.rx.put(f'CAPS:MEDIA_ART2_REFINE:{NEXT}:921600\n'.encode());Event().wait(0.03)
        self.assertEqual(e._artwork_v2_refine_challenge,'')
        w.rx.put(f'CAPS:MEDIA_ART2_REFINE:{TOKEN}:921600\n'.encode())
        until(lambda:e._artwork_v2_refine_challenge==TOKEN);self.ready(e,w)
    def test_failed_compact_ack_keeps_ordinary_retry_but_never_high_job(self):
        e,w=self.pair();w.drop_compact_end=True
        with patch.object(e._artwork_ack,'wait',return_value=False):send_primary(e)
        self.assertIsNone(e._artwork_refinement);self.assertEqual(e._artwork_retry[3],1)
        self.assertFalse(any(p.startswith(b'MEDIA_ART2_BEGIN:') for p in w.writes))
    def test_incomplete_high_timeout_keeps_low_and_drops_optional_work(self):
        e,w=self.pair();job=self.ready(e,w);w.drop_full_end=True;low=bytes(snapshot(w.h))
        counter=iter(range(100000,200000))
        with patch('engine.time.monotonic',side_effect=lambda:next(counter)):
            self.refine(e,job)
        self.assertEqual(bytes(snapshot(w.h)),low);self.assertIsNone(e._artwork_retry)
        self.assertIsNone(e._artwork_refinement)
    def test_actual_sender_loop_prefers_new_coarse_job_over_ready_refinement(self):
        e,w=self.pair();job=self.ready(e,w);job['started']=False
        w.render(4000);w.now=4000;e._on_media_update(legacy.ArtworkV2Tests.snapshot('next'),OTHER)
        t=Thread(target=e._artwork_sender_loop);t.start()
        until(lambda:w.compact_ends==2);e.running=False;t.join(0.5)
        self.assertFalse(t.is_alive());self.assertEqual(w.full_ends,0)
    def test_stats_and_touch_can_run_between_refinement_batches(self):
        e,w=self.pair();job=self.ready(e,w);served=Event();seen=[]
        e.media_bridge.control.side_effect=lambda action:(seen.append((action,e._artwork_transfer_active.is_set())),served.set())
        first=True
        def pause(_):
            nonlocal first
            if first:
                first=False;e.send_command('STATS:CPU:2,RAM:3,WPM:0')
                w.rx.put(b'MEDIA_CMD:NEXT\n');self.assertTrue(served.wait(0.4))
        with patch('engine.time.sleep',side_effect=pause):
            e._send_artwork_v2(w,job['track'],job['artwork'],0,job)
        self.assertEqual(seen,[('NEXT',True)])
        stats=next(i for i,p in enumerate(w.writes) if p.startswith(b'STATS:'))
        end=next(i for i,p in enumerate(w.writes) if p.startswith(b'MEDIA_ART2_END:') and i>stats)
        self.assertLess(stats,end)
    def test_missing_shown_expires_without_extra_query_retry_or_download(self):
        e,w=self.pair();w.render_compact=False;send_primary(e)
        e._artwork_refinement['expires']=time.monotonic()-1;before=len(w.writes)
        self.assertIsNone(e._take_artwork_refinement());self.assertIsNone(e._artwork_refinement)
        self.assertEqual(len(w.writes),before);self.assertIsNone(e._artwork_retry)

if __name__=='__main__':unittest.main()

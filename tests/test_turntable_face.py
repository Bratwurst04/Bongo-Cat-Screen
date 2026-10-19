"""Real compact/full/raw receivers, pixel ownership and timed visible faces."""
import ctypes
from pathlib import Path
import unittest
from turntable_face_host import load_host,frame,snapshot,transfer,Pixels

ROOT=Path(__file__).resolve().parents[1]
OLD=bytes((210,25,45))*(112*112)
NEW=bytes((20,90,230))*(112*112)
LATEST=bytes((240,180,15))*(112*112)
EDGE=870;END=1880;FULL_EDGE=1070;FULL_END=2380

class FaceOwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.h=load_host()
    def setUp(self):
        h=self.h;h.ca_reset();h.ff_play(True,0,200);frame(h,0)
        h.ca_context(101,0);transfer(h,OLD,1,0);frame(h,200)
        self.old_slot=h.ca_active();self.old=bytes(snapshot(h));self.base=1000
    def context(self,key=102,now=1000):
        frame(self.h,now);self.h.ff_default();self.h.ca_context(key,now)
    def f(self,elapsed,visible=True):return frame(self.h,self.base+elapsed,visible)
    def pixels(self):return bytes(snapshot(self.h))
    def test_default_alone_and_same_context_resync_preserve_old_pixels(self):
        self.h.ff_default();self.assertEqual(frame(self.h,100)[0],1);self.assertEqual(self.pixels(),self.old)
        self.h.ca_context(101,100);self.assertFalse(frame(self.h,100)[10]);self.assertEqual(self.pixels(),self.old)
    def test_early_art_ack_stages_old_face_until_exact_edge(self):
        self.context();transfer(self.h,NEW,2,1300)
        self.assertEqual(self.h.ca_ok(),2);self.assertEqual(self.h.ca_active(),self.old_slot)
        for t in (0,160,300,420,680,800,EDGE-1):
            self.assertEqual(self.f(t)[0],1);self.assertEqual(self.pixels(),self.old)
        edge=self.f(EDGE);self.assertEqual(edge[1],2);self.assertNotEqual(self.h.ca_active(),self.old_slot)
        self.assertNotEqual(self.pixels(),self.old);self.assertEqual(edge[0],1)
        descriptor=(ctypes.c_int*4)();self.h.ca_descriptor(descriptor);self.assertEqual(tuple(descriptor),(112,112,25088,1))
    def test_new_begin_overwrites_only_staging_and_discards_uncommitted_target(self):
        self.context();transfer(self.h,NEW,2,1200)
        transfer(self.h,LATEST,3,1250,finish=False)
        self.assertNotEqual(self.h.ff_receiving_slot(),self.old_slot)
        self.assertEqual(self.f(800)[0],1);self.assertEqual(self.pixels(),self.old)
        self.assertEqual(self.f(EDGE)[0],0) # Partial/new BEGIN cannot expose stale staged NEW.
        self.h.ca_line(b'MEDIA_ART2_END:3',1900);self.assertEqual(self.h.ca_ok(),3)
        self.assertEqual(self.f(900)[0],1)
    def test_retarget_before_edge_keeps_motion_and_only_latest_context_can_commit(self):
        self.context();transfer(self.h,NEW,2,1200)
        self.h.ca_context(103,1400);self.h.ca_line(b'MEDIA_ART2_END:2',1401)
        transfer(self.h,LATEST,3,1450)
        self.assertEqual(self.f(EDGE-1)[1],3);self.assertEqual(self.pixels(),self.old)
        self.assertEqual(self.f(EDGE)[1],2)
        latest=self.pixels();self.assertNotEqual(latest,self.old)
        self.assertEqual(self.f(END)[14],1);self.assertEqual(self.pixels(),latest)
    def test_after_edge_single_latest_waits_for_next_hidden_point_no_old_flash(self):
        self.context();transfer(self.h,NEW,2,1200);self.f(EDGE)
        shown=self.pixels();slot=self.h.ca_active()
        self.h.ca_context(103,2000);transfer(self.h,LATEST,3,2050)
        self.h.ca_context(104,2100);transfer(self.h,OLD,4,2150)
        for t in (1100,1400,1800,END):
            f=self.f(t);self.assertEqual(self.pixels(),shown);self.assertEqual(self.h.ca_active(),slot);self.assertEqual(f[14],0)
        self.f(END+EDGE-1);self.assertEqual(self.pixels(),shown)
        self.f(END+EDGE);self.assertEqual(self.pixels(),self.old)
        self.assertEqual(self.f(2*END)[14],1)
    def test_fifth_completed_exchange_holds_old_until_fully_out(self):
        for n in range(4):
            at=1000+n*(END+500);self.context(102+n,at)
            frame(self.h,at+EDGE);frame(self.h,at+END);self.assertEqual(frame(self.h,at+END)[14],n+1)
        # Put recognizable art on the fourth stable identity before change five.
        at=1000+4*(END+500);transfer(self.h,OLD,9,at-100);frame(self.h,at-100)
        self.old=self.pixels();self.base=at;self.context(106,at);transfer(self.h,NEW,10,at+300)
        self.assertTrue(self.f(100)[11])
        self.assertEqual(self.f(FULL_EDGE-1)[0],1);self.assertEqual(self.pixels(),self.old)
        out=self.f(FULL_EDGE);self.assertEqual(out[2],-160);self.assertNotEqual(self.pixels(),self.old)
        self.assertEqual(self.f(FULL_END)[14],5)
    def test_late_art_reveals_180ms_without_restarting_paw(self):
        self.context();self.assertEqual(self.f(EDGE)[0],0);self.f(END)
        transfer(self.h,NEW,2,self.base+END+100)
        f=self.f(END+100);self.assertEqual((f[0],f[6],f[12]),(1,0,0))
        self.assertTrue(self.f(END+180)[10]);self.assertFalse(self.f(END+280)[10])
    def test_hidden_panel_dj_or_menu_settles_latest_without_replay(self):
        self.context();transfer(self.h,NEW,2,1200)
        hidden=self.f(400,False);self.assertFalse(hidden[10]);self.assertNotEqual(self.pixels(),self.old)
        self.h.ca_context(103,1500);transfer(self.h,LATEST,3,1550)
        self.f(600,False);returned=self.f(700,True)
        self.assertEqual((returned[0],returned[10],returned[12]),(1,0,0))
    def test_none_cancels_pending_image_and_default_does_not_replay_it(self):
        self.context();transfer(self.h,NEW,2,1200);self.h.ff_none()
        self.assertEqual(self.f(400)[0],0);self.assertFalse(self.f(400)[10])
        self.h.ff_default();self.h.ca_context(102,1500)
        self.assertEqual(self.f(600)[0],0)
    def test_crc_failure_abort_and_stale_end_never_replace_pinned_pixels(self):
        self.context();transfer(self.h,NEW,2,1300,crc_delta=1)
        self.assertEqual(self.h.ca_ok(),1);self.assertEqual(self.h.ca_error(),1)
        self.assertEqual(self.f(800)[0],1);self.assertEqual(self.pixels(),self.old)
        transfer(self.h,NEW,3,1820,finish=False);self.h.ca_context(103,1830)
        self.h.ca_line(b'MEDIA_ART2_END:3',1840);self.assertEqual(self.h.ca_ok(),1)
        self.assertEqual(self.f(EDGE)[0],0)
    def test_full_rgb888_and_raw_paths_use_same_safe_slot_policy(self):
        for raw in (False,True):
            self.setUp();self.context()
            if raw:self.h.ff_raw_begin();self.h.ff_raw(NEW,len(NEW))
            else:transfer(self.h,NEW,2,1300,compact=False)
            self.assertEqual(self.f(800)[0],1);self.assertEqual(self.pixels(),self.old)
            self.f(EDGE);self.assertNotEqual(self.pixels(),self.old)
    def test_missed_frames_and_millis_wrap_commit_only_latest_once(self):
        self.base=0xffffff00;self.context(102,self.base)
        transfer(self.h,NEW,2,(self.base+300)&0xffffffff)
        self.assertEqual(self.f(EDGE-1)[0],1);self.assertEqual(self.pixels(),self.old)
        late=self.f(END+200);self.assertEqual(late[1],2);self.assertEqual(late[14],0)
        self.assertNotEqual(self.pixels(),self.old)
        self.assertEqual(self.f(END+220)[14],1)
        self.assertEqual(self.f(END+10000)[14],1)
    def test_frame_gap_paints_offscreen_pose_before_full_exchange_returns(self):
        for n in range(4):
            at=1000+n*(END+500);self.context(102+n,at)
            frame(self.h,at+EDGE);frame(self.h,at+END)
        self.base=1000+4*(END+500);self.context(106,self.base)
        transfer(self.h,NEW,10,self.base+300)
        self.f(600);gap=self.f(FULL_END+200)
        self.assertEqual((gap[2],gap[10],gap[11]),(-160,1,1))
        self.assertEqual(self.f(FULL_END+220)[14],5)
    def test_existing_pixels_and_codec_storage_not_enlarged(self):
        source=(ROOT/'src/bongo_cat_featured.inc').read_text(encoding='utf-8')
        self.assertEqual(source.count('static lv_color_t media_art_buffers[2]'),1)
        self.assertEqual(source.count('heap_caps_malloc('),1)
        self.assertEqual(source.count('media_art_receiving_buffer = media_record_flip.beginArtwork()'),2)
        self.assertLess(frame(self.h,0)[15],192)

if __name__=='__main__':unittest.main()

"""Actual native state/render and production commit/identity bodies, no hardware."""
import ctypes
import math
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from turntable_paw_host import load_host,Frame,Pixels,timings


class TurntableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h=load_host();cls.T=timings(cls.h)
    def setUp(self):
        self.h.tt_reset();self.h.tt_playback(True,0,200);self.frame(0)
        self.h.tt_event(2,101,0,False);self.h.tt_event(3,0,0,False);self.frame(0)
    def frame(self,now,visible=True):
        f=Frame();self.h.tt_frame(now,visible,f);return f
    def advance(self,start,end,step=20):
        f=None
        for now in range(start,end+1,step):f=self.frame(now)
        return f
    def context(self,key,now=1000,animate=True):
        self.h.tt_event(1,key,now,animate)
        return self.h.tt_event(2,key,now,animate)
    def geometry(self,f,compact=False):
        g=(ctypes.c_int*10)();self.h.tt_geometry(f,compact,g);return g
    def render(self,f,art=None):
        out=Pixels();palette=(ctypes.c_ushort*5)(0,1,2,3,4)
        self.assertTrue(self.h.tt_render(out,112*112,art,f,0,32768,palette));return out

    def test_play_pause_lifts_then_parks_and_resume_uses_current_progress(self):
        self.h.tt_playback(False,0,200)
        self.frame(20);raised=self.frame(100);self.assertGreater(raised[9],0)
        parked=self.advance(120,400);self.assertEqual((parked[8],parked[9]),(0,1000))
        self.h.tt_playback(True,160,200)
        self.frame(420);swing=self.frame(500);self.assertGreater(swing[8],0);self.assertEqual(swing[9],1000)
        down=self.advance(520,2500)
        self.assertEqual((down[8],down[9]),(1000,0))
        self.assertAlmostEqual(down[7],800,delta=1)
        g=self.geometry(down);self.assertLess(g[5],170)

    def test_progress_correction_is_smoothed_and_reaches_goal_at_1ms_frames(self):
        self.h.tt_playback(True,200,200)
        first=self.frame(1);self.assertLess(first[7],100)
        end=self.advance(2,4000,1);self.assertEqual(end[7],1000)
        self.h.tt_playback(True,0,200)
        first=self.frame(4001);self.assertGreater(first[7],900)
        end=self.advance(4002,8000,1);self.assertEqual(end[7],0)
        self.assertEqual(end[13],0);self.assertFalse(end[10])

    def test_unknown_duration_holds_same_track_target_and_new_track_has_stable_default(self):
        self.h.tt_playback(True,150,200);self.advance(20,3000)
        self.h.tt_playback(True,999,0);held=self.advance(3020,6000)
        self.assertEqual(held[7],750)
        self.context(102,6020);unknown=self.advance(6020,9000)
        self.assertEqual(unknown[7],350)
        self.assertEqual(unknown[14],1)

    def test_default_context_and_identical_metadata_give_one_change(self):
        self.context(102);self.assertEqual(self.frame(1000)[13],1)
        for now in (1100,1300,1500):
            self.h.tt_event(1,99,now,True);self.h.tt_event(2,102,now,True)
        end=1000+self.T['normal_ms']+200
        done=self.advance(1520,end)
        self.assertEqual((done[13],done[14]),(1,1));self.assertFalse(done[10])
        self.context(103,end+100);self.assertEqual(self.frame(end+100)[13],2)

    def test_none_then_same_context_resync_never_replays_physical_change(self):
        self.h.tt_event(0,0,100,False);self.h.tt_event(2,0,100,False)
        self.h.tt_event(1,999,200,True);self.h.tt_event(2,101,200,True)
        f=self.frame(200);self.assertFalse(f[10]);self.assertEqual(f[13],0)
        self.h.tt_event(3,0,500,True);f=self.frame(500)
        self.assertFalse(f[12]);self.assertEqual(f[13],0)

    def test_normal_flip_clears_arm_grips_lands_and_retracts(self):
        self.context(102)
        self.frame(1000);clear=self.advance(1020,1000+self.T['clear_end'])
        self.assertEqual((clear[8],clear[9]),(0,1000))
        grip=self.frame(1000+self.T['reach_end']);self.assertTrue(grip[12]);self.assertEqual(grip[4],-56)
        edge=self.frame(1000+(self.T['lift_end']+self.T['flip_end'])//2);self.assertEqual(edge[1],2)
        landed=self.frame(1000+self.T['lower_end']+20);self.assertEqual((landed[1],landed[3]),(110,1))
        withdrawn=self.frame(1000+self.T['withdraw_end']);self.assertFalse(withdrawn[12])
        done=self.advance(1000+self.T['withdraw_end']+20,1000+self.T['normal_ms']+200)
        self.assertFalse(done[10]);self.assertEqual(done[9],0)

    def test_pausing_during_change_leaves_arm_parked(self):
        self.context(102);self.frame(1000);self.h.tt_playback(False,0,200)
        done=self.advance(1020,1000+self.T['normal_ms']+200)
        self.assertEqual((done[8],done[9],done[14]),(0,1000,1))

    def test_fifth_completed_stable_change_is_full_and_disc_exits_left(self):
        spacing=self.T['normal_ms']+400
        for n in range(4):
            at=1000+n*spacing;self.context(102+n,at);done=self.advance(at,at+self.T['normal_ms']+200)
            self.assertFalse(done[11]);self.assertEqual(done[14],n+1)
        base=1000+4*spacing
        self.context(106,base);self.assertTrue(self.frame(base)[11])
        outside=self.frame(base+self.T['full_out_end']);self.assertEqual(outside[2],-160)
        for compact in (False,True):
            g=self.geometry(outside,compact);self.assertLess(g[0]+outside[2]*g[2]//256+56*g[2]//256,0)
        done=self.advance(base+self.T['full_out_end']+20,base+self.T['full_ms']+200)
        self.assertEqual(done[14],5);self.assertFalse(done[10])

    def test_rapid_contexts_coalesce_without_resetting_time_or_queuing(self):
        self.context(102,1000);self.frame(1000)
        for i,now in enumerate((1100,1200,1400),103):
            self.context(i,now);self.frame(now)
        self.h.tt_event(3,0,1600,True)
        done=self.advance(1620,1000+self.T['normal_ms']+200)
        self.assertEqual((done[13],done[14]),(4,1));self.assertFalse(done[10]);self.assertEqual(done[0],1)
        self.assertFalse(self.frame(5000)[10])

    def test_skip_at_landing_counts_only_after_latest_identity_is_stable(self):
        self.context(102,1000);self.frame(1000)
        self.frame(1000+(self.T['lift_end']+self.T['flip_end'])//2)
        latest=1000+self.T['normal_ms']-10
        self.context(103,latest);self.frame(latest)
        self.assertEqual(self.frame(1000+self.T['normal_ms'])[14],0)
        self.assertEqual(self.frame(latest+380)[14],0)
        self.assertEqual(self.frame(latest+400)[14],0)
        # Retarget after the edge needs another hidden point, after this motion.
        self.frame(1000+self.T['normal_ms']+(self.T['lift_end']+self.T['flip_end'])//2)
        self.assertEqual(self.frame(1000+2*self.T['normal_ms'])[14],1)

    def test_late_art_is_only_180ms_surface_reveal_no_paw_or_needle_lift(self):
        self.context(102);at=1000+self.T['normal_ms']+300;self.advance(1000,at)
        before=self.frame(at);self.assertEqual(before[9],0)
        self.h.tt_event(3,0,at,True)
        for now in (at,at+80,at+160):
            f=self.frame(now);self.assertTrue(f[10]);self.assertFalse(f[12]);self.assertEqual(f[9],0)
            self.assertEqual((f[13],f[14]),(1,1))
        done=self.frame(at+self.T['reveal_ms']);self.assertFalse(done[10]);self.assertEqual(done[6],256)
        self.assertFalse(self.h.tt_event(3,0,at+self.T['reveal_ms']+20,True))

    def test_menu_dj_other_panel_and_focus_resize_settle_without_replayed_queue(self):
        for hidden_at in (1000+self.T['reach_end'],1000+(self.T['lift_end']+self.T['flip_end'])//2,
                          1000+self.T['lower_end']):
            self.setUp();self.context(102);self.frame(1000);self.frame(hidden_at,False)
            self.h.tt_event(3,0,hidden_at+20,False)
            returned=self.frame(hidden_at+100,True)
            self.assertFalse(returned[10]);self.assertFalse(returned[12]);self.assertEqual(returned[0],1)
            self.assertEqual(returned[9],0)
            self.assertEqual(self.geometry(returned,True)[1],126)

    def test_millis_wrap_has_no_stuck_phases(self):
        self.context(102,0xffffff00);self.frame(0xffffff00)
        done=self.advance(0xffffff14,0xffffff00+self.T['normal_ms']+400)
        self.assertFalse(done[10]);self.assertFalse(done[12]);self.assertEqual(done[14],1)

    def test_same_physical_diameter_generic_album_and_thin_flip(self):
        f=self.frame(0);f[0]=0;generic=self.render(f)
        f[0]=1;album=self.render(f,Pixels(*([12345]*(112*112))))
        row=slice(56*112,57*112)
        self.assertEqual(sum(p!=0 for p in generic[row]),112)
        self.assertEqual(sum(p!=0 for p in album[row]),112)
        f[1]=2;edge=self.render(f)
        self.assertEqual(sum(p!=0 for p in edge[55*112:56*112]),112)

    def test_capacity_and_all_overlapping_art_aliases_are_rejected_without_writes(self):
        palette=(ctypes.c_ushort*5)(0,1,2,3,4);f=self.frame(0)
        out=Pixels(*([54321]*(112*112)))
        self.assertFalse(self.h.tt_render(out,112*112-1,None,f,0,32768,palette));self.assertEqual(set(out),{54321})
        larger=(ctypes.c_ushort*(112*112+8))(*([1111]*(112*112+8)))
        for offset in (0,2,8):
            pointer=ctypes.cast(ctypes.byref(larger,offset),ctypes.POINTER(ctypes.c_ushort))
            self.assertFalse(self.h.tt_render(pointer,112*112,larger,f,0,32768,palette))
        self.assertEqual(set(larger),{1111})

    def test_oom_reduced_generic_is_bounded_and_has_matching_radius(self):
        palette=(ctypes.c_ushort*5)(0,1,2,3,4);out=(ctypes.c_ushort*4096)(*([54321]*4096))
        self.assertFalse(self.h.tt_reduced(out,3135,palette));self.assertEqual(set(out),{54321})
        self.assertTrue(self.h.tt_reduced(out,4096,palette));self.assertEqual(set(out[3136:]),{54321})
        self.assertEqual(sum(p!=0 for p in out[28*56:29*56]),56)
        self.assertEqual(self.h.tt_fw_oom(),1)

    def test_arm_length_pivot_bounds_and_needle_path_in_both_layouts(self):
        f=self.frame(0);f[8]=1000;f[9]=0
        for compact in (False,True):
            points=[]
            for progress in (0,500,1000):
                f[7]=progress;g=self.geometry(f,compact)
                self.assertEqual((g[3],g[4]),(214,60))
                self.assertEqual(g[2],320 if compact else 384)
                self.assertAlmostEqual(math.hypot(g[5]-214,g[6]-60),106,delta=1)
                points.append(math.hypot(g[5]-g[0],g[6]-g[1]))
                self.assertGreater(g[6],50);self.assertLess(g[6]+6,205)
            self.assertGreater(points[0],points[-1])

    def test_overlay_geometry_is_outside_artbox_and_above_metadata_focus_card(self):
        self.context(102);f=self.frame(1000+self.T['reach_end']);colors=(ctypes.c_ushort*5)(0,1,2,3,4)
        for compact in (False,True):
            for paw in (False,True):
                out=(ctypes.c_int*(64*7))();n=self.h.tt_primitives(f,compact,paw,out,colors)
                self.assertGreater(n,0);self.assertLess(n,64)
                self.assertTrue(all(min(out[i*7+2],out[i*7+4])>=50 and max(out[i*7+2],out[i*7+4])<205 for i in range(n)))
        source=(ROOT/'src/bongo_cat_featured.inc').read_text(encoding='utf-8')
        self.assertIn('media_art_image = lv_img_create(media_screen)',source)
        self.assertIn('LV_OBJ_FLAG_CLICKABLE | LV_OBJ_FLAG_SCROLLABLE',source)
        self.assertNotIn('lv_line_set_points',source)

    def test_current_firmware_ack_stages_without_releasing_still_visible_old_art(self):
        self.h.tt_fw_reset();self.h.tt_fw_context(102,1000);self.h.tt_fw_art(1000+self.T['lift_end']+40)
        self.assertEqual(self.h.tt_fw_acks(),1)
        out=Pixels();self.h.tt_fw_draw(out,1000+self.T['lift_end'])
        self.assertIn(1111,out);self.assertNotIn(2222,out)
        self.assertEqual(self.h.tt_fw_begin(),1);self.h.tt_fw_overwrite()
        self.h.tt_fw_draw(out,1000+self.T['lift_end']+20)
        self.assertIn(1111,out);self.assertNotIn(3333,out)
        self.assertLess(self.frame(0)[15],192)


if __name__=='__main__':unittest.main()

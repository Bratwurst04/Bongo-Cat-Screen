"""Raster/phase checks against actual native output, with no device or SDK."""
import ctypes
from collections import deque
import unittest
from PIL import Image, ImageDraw
from turntable_paw_host import load_host, Frame, timings


class ArmTempoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h=load_host();cls.T=timings(cls.h)

    def start(self,full=False):
        h=self.h;h.tt_reset();h.tt_playback(True,0,200);h.tt_frame(0,True,Frame())
        h.tt_event(2,101,0,False);h.tt_event(3,0,0,False);h.tt_frame(0,True,Frame())
        spacing=self.T['normal_ms']+400
        for n in range(4 if full else 0):
            at=1000+n*spacing;h.tt_event(2,102+n,at,True)
            for now in range(at,at+self.T['normal_ms']+201,20):h.tt_frame(now,True,Frame())
        self.base=1000+(4*spacing if full else 0)
        h.tt_event(2,106 if full else 102,self.base,True)

    def frame(self,ms):
        f=Frame();self.h.tt_frame(self.base+ms,True,f);return f

    def primitives(self,f,compact):
        raw=(ctypes.c_int*(64*7))();colors=(ctypes.c_ushort*5)(0,1,2,3,4)
        count=self.h.tt_primitives(f,compact,True,raw,colors)
        self.assertLess(count,64,'overlay capacity needs review')
        return [tuple(raw[i*7:i*7+7]) for i in range(count)]

    def raster(self,primitives):
        image=Image.new('L',(240,205),255);draw=ImageDraw.Draw(image)
        for shape,x1,y1,x2,y2,color,width in primitives:
            self.assertEqual(shape,0);self.assertLessEqual(x1,x2);self.assertLessEqual(y1,y2)
            self.assertGreaterEqual(y1,50);self.assertLess(y2,205)
            draw.rectangle((x1,y1,x2,y2),fill=color)
        return image

    def test_white_forearm_and_paw_are_one_component_joining_left_edge_through_motion(self):
        checked=0
        for full in (False,True):
            self.start(full)
            for ms in range(0,self.T['full_ms' if full else 'normal_ms']+1,20):
                f=self.frame(ms)
                for compact in (False,True):
                    image=self.raster(self.primitives(f,compact))
                    white={(x,y) for y in range(90,145) for x in range(65) if image.getpixel((x,y))==1}
                    if not white:continue
                    checked+=1;self.assertTrue(any(x==0 for x,y in white),(full,compact,ms))
                    seed=next(iter(white));visited={seed};todo=deque([seed])
                    while todo:
                        x,y=todo.popleft()
                        for q in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                            if q in white and q not in visited:visited.add(q);todo.append(q)
                    self.assertEqual(visited,white,(full,compact,ms,'floating white piece or wrist seam'))
        self.assertGreater(checked,150)

    def test_complete_withdrawal_leaves_no_arm_stump_or_inverted_rectangles(self):
        self.start(True);offscreen=0
        for ms in range(0,self.T['full_ms']+1,10):
            f=self.frame(ms)
            for compact in (False,True):
                g=(ctypes.c_int*10)();self.h.tt_geometry(f,compact,g)
                primitives=self.primitives(f,compact);self.raster(primitives)
                if g[8]+3<0 or not f[12]:
                    offscreen+=1;self.assertEqual(primitives,[],(ms,compact))
        self.assertGreater(offscreen,50)

    def test_grip_pause_then_gradual_lift_and_slower_lower_in_both_routines(self):
        T=self.T
        self.assertTrue(1700<=T['normal_ms']<=1900)
        self.assertTrue(2200<=T['full_ms']<=2400)
        for full in (False,True):
            self.start(full)
            grip=[self.frame(ms) for ms in range(T['reach_end'],T['grip_end']+1,20)]
            self.assertGreaterEqual(T['grip_end']-T['reach_end'],100)
            self.assertTrue(all((f[2],f[3],f[4],f[1])==(0,0,-56,112) for f in grip))
            lift=[self.frame(ms) for ms in range(T['grip_end'],T['lift_end']+1,20)]
            self.frame(T['full_out_end'] if full else (T['lift_end']+T['flip_end'])//2)
            begin=T['full_in_end' if full else 'flip_end'];end=T['full_lower_end' if full else 'lower_end']
            lower=[self.frame(ms) for ms in range(begin,end+1,20)]
            self.assertGreaterEqual(T['lift_end']-T['grip_end'],250);self.assertGreaterEqual(end-begin,300)
            self.assertEqual((lift[0][3],lift[-1][3],lower[0][3],lower[-1][3]),(0,-T['lift_pixels'],-T['lift_pixels'],0))
            for frames in (lift,lower):
                values=[f[3] for f in frames]
                self.assertGreaterEqual(len(set(values)),5)
                self.assertTrue(all(abs(a-b)<=1 for a,b in zip(values,values[1:])))
                self.assertTrue(all(f[1]==112 for f in frames),'lift/lower must move the flat disc')
            self.assertEqual([f[3] for f in lift],sorted((f[3] for f in lift),reverse=True))
            self.assertEqual([f[3] for f in lower],sorted(f[3] for f in lower))
            settle=[self.frame(ms)[3] for ms in range(end,end+81,10)]
            self.assertLessEqual(max(settle),1);self.assertEqual(settle[-1],0)

    def test_flat_lift_clears_focus_card_and_stays_above_metadata(self):
        self.start()
        for ms in range(0,self.T['normal_ms']+1,10):
            f=self.frame(ms)
            for compact in (False,True):
                g=(ctypes.c_int*10)();self.h.tt_geometry(f,compact,g)
                cy=g[1]+int(f[3]*g[2]/256);half=(f[1]*g[2]//256)//2
                self.assertGreaterEqual(cy-half,50 if compact else 20)
                self.assertLess(cy+half,205)


if __name__=='__main__':unittest.main()

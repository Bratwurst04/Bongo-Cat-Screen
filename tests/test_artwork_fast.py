"""Explicit high-baud pairing, unchanged bytes, bounded bursts and RX assumptions."""
import base64
import configparser
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
import zlib

import test_artwork_v2 as legacy
from engine import ARTWORK_V2_FRAME_BYTES,ARTWORK_V2_921600_BATCH_FRAMES
from config import ConfigManager
from artwork_fast_host import BUILD,ROOT,WireModel,load_host,firmware_limits

MODEL_RESULTS=[]
ART=bytes(range(256))*(ARTWORK_V2_FRAME_BYTES//256)
CHALLENGE='0123456789ABCDEF'


class ArtworkFastTests(unittest.TestCase):
    def engine(self,baud=921600,fast=True):
        e=legacy.ArtworkV2Tests().make_engine();e.baudrate=baud
        e._artwork_v2_supported=True;e._artwork_v2_challenge=CHALLENGE
        e._artwork_v2_fast_challenge=CHALLENGE if fast else ''
        e._on_media_update(legacy.ArtworkV2Tests.snapshot('song'),None)
        return e

    def immediate(self,e,attempt=0):
        writes=[]
        def write(payload):
            writes.append(payload)
            if payload.startswith(b'MEDIA_ART2_END:'):
                e._artwork_v2_ack_result=True;e._artwork_ack.set()
            return len(payload)
        e.serial_conn.write.side_effect=write
        with patch('engine.time.sleep') as sleep,patch('engine.diagnostics.event'):
            e._send_artwork_v2(e.serial_conn,'song',ART,attempt)
        return writes,sleep

    def test_fast_bytes_offsets_crc_and_no_sleep_at_worst_transfer_id(self):
        e=self.engine();e._artwork_v2_next_id=65534;writes,sleep=self.immediate(e)
        chunks=[p for p in writes if p.startswith(b'MEDIA_ART2_CHUNK:')]
        self.assertEqual(len(chunks),37);self.assertTrue(all(p.count(b'\n')==8 for p in chunks[:-1]))
        self.assertLessEqual(max(map(len,chunks)),2048);sleep.assert_not_called()
        decoded=bytearray()
        for line in b''.join(chunks).splitlines():
            _,ident,offset,encoded=line.split(b':',3)
            self.assertEqual(ident,b'65535');self.assertEqual(int(offset),len(decoded))
            decoded.extend(base64.b64decode(encoded,validate=True))
        self.assertEqual(decoded,ART)
        header=next(p for p in writes if p.startswith(b'MEDIA_ART2_BEGIN:'))
        self.assertTrue(header.endswith(f'{zlib.crc32(ART)&0xffffffff:08X}\n'.encode()))
        self.assertEqual(sum(map(len,writes)),59366)

    def test_old_pair_wrong_baud_stale_challenge_and_retry_keep_conservative_pacing(self):
        for baud,cap,attempt,expected in [(115200,True,0,1),(230400,True,0,2),
                (460800,True,0,2),(921600,False,0,2),(921600,True,1,1)]:
            with self.subTest(baud=baud,cap=cap,attempt=attempt):
                writes,sleep=self.immediate(self.engine(baud,cap),attempt)
                chunks=[p for p in writes if p.startswith(b'MEDIA_ART2_CHUNK:')]
                self.assertEqual(chunks[0].count(b'\n'),expected)
                self.assertEqual(sleep.call_count,len(chunks))
                self.assertTrue(all(c.args==(0.015,) for c in sleep.call_args_list))
        e=self.engine();e._artwork_v2_challenge='FEDCBA9876543210'
        writes,_=self.immediate(e);self.assertEqual(next(p for p in writes if p.startswith(b'MEDIA_ART2_CHUNK:')).count(b'\n'),2)

    def test_reader_requires_baud_and_current_challenge_for_fast_capability(self):
        for baud in (230400,921600):
            e=self.engine(baud,False);e._artwork_v2_supported=False
            replies=iter([b'CAPS:MEDIA_ART2_FAST:AAAAAAAAAAAAAAAA:921600\n',
                f'CAPS:MEDIA_ART2_FAST:{CHALLENGE}:230400\n'.encode(),
                f'CAPS:MEDIA_ART2:{CHALLENGE}\n'.encode(),
                f'CAPS:MEDIA_ART2_FAST:{CHALLENGE}:921600\n'.encode()])
            seen=[]
            def read():
                seen.append(e._artwork_v2_fast_challenge)
                line=next(replies)
                if len(seen)==4:e.running=False
                return line
            e.serial_conn.readline.side_effect=read
            with patch('engine.diagnostics.event'):e._serial_reader_loop()
            self.assertEqual(seen,['']*4);self.assertTrue(e._artwork_v2_supported)
            self.assertEqual(e._artwork_v2_fast_challenge,CHALLENGE if baud==921600 else '')

    def test_new_sync_discards_previous_fast_capability(self):
        e=self.engine();e.get_system_stats=Mock(return_value=(10,20));e.send_command=Mock(return_value=True)
        with patch('engine.secrets.token_hex',return_value='fedcba9876543210'),patch('builtins.print'):e.send_initial_sync()
        self.assertEqual(e._artwork_v2_fast_challenge,'')
        self.assertEqual(e._artwork_v2_challenge,'FEDCBA9876543210')

    def test_metadata_and_abort_get_slot_after_one_fast_batch(self):
        e=self.engine();writes=[];switched=False
        def write(payload):
            nonlocal switched
            writes.append(payload)
            if payload.startswith(b'MEDIA_ART2_CHUNK:') and not switched:
                switched=True;e._on_media_update(legacy.ArtworkV2Tests.snapshot('new'),None)
            return len(payload)
        e.serial_conn.write.side_effect=write
        with patch('engine.diagnostics.event'):e._send_artwork_v2(e.serial_conn,'song',ART,0)
        wire=b''.join(writes)
        self.assertEqual(wire.count(b'MEDIA_ART2_CHUNK:'),8)
        self.assertIn(b'MEDIA_ART2_ABORT:1\n',wire);self.assertNotIn(b'MEDIA_ART2_END:',wire)
        self.assertIn(b'MEDIA_TITLE:new\n',wire);self.assertIsNone(e._artwork_retry)

    def test_stop_and_epoch_change_cancel_without_old_end_or_ack_ownership(self):
        for change in ('stop','epoch'):
            e=self.engine();writes=[];calls=0
            def interleave():
                nonlocal calls
                calls+=1
                if calls==2:
                    if change=='stop':e.running=False
                    else:e._artwork_v2_epoch+=1;e._artwork_v2_challenge=''
            e._flush_latest_media=Mock(side_effect=interleave)
            e.serial_conn.write.side_effect=lambda p:(writes.append(p) or len(p))
            with patch('engine.diagnostics.event'):e._send_artwork_v2(e.serial_conn,'song',ART,0)
            self.assertEqual(b''.join(writes).count(b'MEDIA_ART2_CHUNK:'),8)
            self.assertNotIn(b'MEDIA_ART2_END:',b''.join(writes));self.assertIsNone(e._artwork_v2_pending_id)
            self.assertFalse(e._artwork_transfer_active.is_set())

    def test_partial_fast_write_never_sends_end_and_releases_transfer_state(self):
        import serial
        e=self.engine();writes=[]
        def partial(p):writes.append(p);return len(p)-1 if p.startswith(b'MEDIA_ART2_CHUNK:') else len(p)
        e.serial_conn.write.side_effect=partial
        with patch('engine.diagnostics.event'),self.assertRaises(serial.SerialTimeoutException):
            e._send_artwork_v2(e.serial_conn,'song',ART,0)
        self.assertNotIn(b'MEDIA_ART2_END:',b''.join(writes));self.assertFalse(e._artwork_transfer_active.is_set())
        self.assertIsNone(e._artwork_v2_pending_id)

    def model(self,name,**kwargs):
        e=self.engine();m=WireModel(e,**kwargs)
        e.serial_conn.write.side_effect=m.write;e.serial_conn.flush.side_effect=m.flush
        with patch('engine.time.sleep',side_effect=m.sleep),patch('engine.time.monotonic',side_effect=lambda:m.now/1e6),\
             patch.object(e._artwork_ack,'wait',side_effect=m.wait),patch('engine.diagnostics.event'):
            e._send_artwork_v2(e.serial_conn,'song',ART,0)
        result=dict(name=name,assumptions=dict(kwargs,parse_us=m.parse_us,loop_delay_ms=m.limits['loop_delay_ms']),
            wire_ms=round(m.wire_end/1000,3),ack_ms=round(m.acks[-1][0]/1000,3) if m.acks else None,
            committed=m.committed==ART,peak_queue=m.peak_queue,peak_uart=m.peak_uart,
            uart_dropped_bytes=m.dropped,framing_overflows=m.h.af_overflows(),
            touch_service_calls=len(m.touch_times),retry_scheduled=e._artwork_retry is not None)
        MODEL_RESULTS.append(result)
        return m,result

    def test_native_rx_budget_model_keeps_bytes_and_services_touch_under_stated_stalls(self):
        for name,options in [('idle',{}),('paint20',{'render_ms':20}),
                ('paint20_blackout100',{'render_ms':20,'blackout_ms':100})]:
            with self.subTest(name=name):
                m,r=self.model(name,**options)
                self.assertEqual(m.committed,ART);self.assertEqual(m.dropped,0);self.assertEqual(m.h.af_overflows(),0)
                self.assertLessEqual(m.peak_queue,firmware_limits()['SERIAL_RX_QUEUE_DEPTH'])
                self.assertGreater(len(m.touch_times),10);self.assertLess(r['ack_ms'],1000)

    def test_model_exposes_slow_paint_overflow_instead_of_claiming_unlimited_throughput(self):
        m,r=self.model('overload500',blackout_ms=500,render_ms=30)
        self.assertGreater(m.dropped,0);self.assertIsNone(m.committed);self.assertTrue(r['retry_scheduled'])

    def test_model_exposes_win32_flush_poll_cost_separately(self):
        m,r=self.model('flush_poll50',flush_poll_ms=50)
        self.assertEqual(m.committed,ART);self.assertGreater(r['ack_ms'],1000)

    def test_native_crc_order_and_incomplete_frame_reject_wrong_commit(self):
        h=load_host();h.af_reset();crc=zlib.crc32(ART)&0xffffffff
        self.assertTrue(h.af_begin(1,len(ART),crc))
        self.assertFalse(h.af_accept(1,128,ART[:128],128));self.assertFalse(h.af_complete(1))
        for offset in range(0,len(ART),128):
            data=ART[offset:offset+128]
            if not offset:data=bytes([data[0]^1])+data[1:]
            self.assertTrue(h.af_accept(1,offset,data,len(data)))
        self.assertFalse(h.af_complete(1));self.assertFalse(h.af_complete(2));h.af_abort()

    def test_explicit_profile_and_config_save_reload_preserve_defaults(self):
        ini=configparser.ConfigParser(interpolation=None);ini.read(ROOT/'platformio.ini')
        self.assertEqual(ini['platformio']['default_envs'],'esp32-024r-spotify-fastserial')
        self.assertEqual(ini['env:esp32-024r-spotify']['upload_speed'],'115200')
        self.assertEqual(ini['env:esp32-024r-spotify-artfast921600']['monitor_speed'],'921600')
        self.assertIn('BONGO_ART2_FAST_TIER=1',ini['env:esp32-024r-spotify-artfast921600']['build_flags'])
        folder=BUILD/'config-fixtures';folder.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=folder) as path,patch('builtins.print'):
            manager=ConfigManager(path);self.assertEqual(manager.get_connection_settings()['baudrate'],230400)
            for baud in (115200,230400,460800,921600):
                manager.set_setting('connection','baudrate',baud);manager.save_config()
                self.assertEqual(ConfigManager(path).get_connection_settings()['baudrate'],baud)
        self.assertEqual(json.loads((ROOT/'companion/default_config.json').read_text())['connection']['baudrate'],230400)


if __name__=='__main__':unittest.main()

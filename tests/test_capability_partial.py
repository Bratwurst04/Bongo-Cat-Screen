"""Fresh partial CAPS contract through the real reader/sender/native receiver."""
from itertools import permutations
from threading import Lock
import unittest
from unittest.mock import Mock,patch

import test_artwork_v2 as legacy
from test_capability_startup import TOKEN,NEXT,STATUS

BASE=f'CAPS:MEDIA_ART2:{TOKEN}\n'.encode()
REFINE=f'CAPS:MEDIA_ART2_REFINE:{TOKEN}:921600\n'.encode()
COMPACT=f'CAPS:MEDIA_ART2_RGB56580:{TOKEN}:921600\n'.encode()
FAST=f'CAPS:MEDIA_ART2_FAST:{TOKEN}:921600\n'.encode()


class PartialCapabilityTests(unittest.TestCase):
    def engine(self,baud=921600):
        e=legacy.ArtworkV2Tests().make_engine();e.baudrate=baud;e._data_lock=Lock()
        e._artwork_v2_challenge=TOKEN;e._artwork_v2_base_challenge=''
        e._artwork_v2_fast_challenge='';e._artwork_v2_compact_challenge='';e._artwork_v2_refine_challenge=''
        e._capability_fallback=(e.serial_conn,e._artwork_v2_epoch,TOKEN);e.media_bridge=Mock()
        return e

    def read(self,e,lines,hook=None):
        replies=iter(lines)
        def next_line():
            try:line=next(replies)
            except StopIteration:e.running=False;return b''
            if hook:hook(line)
            return line
        e.running=True;e.serial_conn.readline.side_effect=next_line
        with patch('engine.diagnostics.event') as events:e._serial_reader_loop()
        return [call.args[0] for call in events.call_args_list]

    def test_exact_repeated_partial_caps_recover_without_another_query(self):
        e=self.engine();cached=bytes(37632);e._cached_artwork=cached
        events=self.read(e,[BASE,REFINE,STATUS,BASE,REFINE,STATUS])
        self.assertTrue(e._artwork_v2_supported);self.assertEqual(e._artwork_v2_compact_challenge,TOKEN)
        self.assertEqual(e._artwork_v2_refine_challenge,TOKEN);self.assertIs(e._cached_artwork,cached)
        self.assertEqual(events.count('ART_COMPACT_INFERRED'),1)
        self.assertEqual(events.count('ART_COMPACT_CAPABILITY'),1)
        e.serial_conn.write.assert_not_called();self.assertIsNone(e._capability_fallback)

    def test_both_fresh_proofs_work_in_either_order(self):
        for rows in permutations((BASE,REFINE)):
            e=self.engine();events=self.read(e,rows)
            self.assertEqual(e._artwork_v2_compact_challenge,TOKEN)
            self.assertEqual(events.count('ART_COMPACT_INFERRED'),1)

    def test_direct_compact_peer_without_refine_is_preserved(self):
        e=self.engine();events=self.read(e,[BASE,COMPACT])
        self.assertEqual(e._artwork_v2_compact_challenge,TOKEN);self.assertEqual(e._artwork_v2_refine_challenge,'')
        self.assertNotIn('ART_COMPACT_INFERRED',events)

    def test_explicit_compact_before_refine_needs_no_inference(self):
        e=self.engine();events=self.read(e,[BASE,COMPACT,REFINE,STATUS])
        self.assertNotIn('ART_COMPACT_INFERRED',events);e.serial_conn.write.assert_not_called()

    def test_legacy_base_only_and_fast_only_keep_bounded_existing_fallback(self):
        for rows in ((BASE,), (BASE,FAST), (REFINE,), ()):
            e=self.engine();self.read(e,[*rows,STATUS,STATUS,STATUS])
            self.assertEqual(e._artwork_v2_compact_challenge,'')
            e.serial_conn.write.assert_called_once_with(f'CAPS?:{TOKEN}\n'.encode())

    def test_wrong_baud_wrong_nonce_and_malformed_partial_lines_never_promote(self):
        for baud,rows in ((230400,[BASE,REFINE]),(115200,[BASE,REFINE]),
                (921600,[BASE,REFINE.replace(TOKEN.encode(),NEXT.encode())]),
                (921600,[BASE.replace(TOKEN.encode(),NEXT.encode()),REFINE]),
                (921600,[BASE,REFINE.replace(b':921600',b':460800')]),
                (921600,[BASE,REFINE.replace(b'\n',b':extra\n')])):
            e=self.engine(baud);self.read(e,rows);self.assertEqual(e._artwork_v2_compact_challenge,'')

    def test_missing_or_fragmented_compact_line_does_not_block_fresh_contract(self):
        for middle in ([],[COMPACT[:25],COMPACT[25:]], [b'ignored diagnostic\n']):
            e=self.engine();self.read(e,[BASE,*middle,REFINE])
            self.assertEqual(e._artwork_v2_compact_challenge,TOKEN)

    def test_generation_changed_during_blocking_read_cannot_register_capability(self):
        for row in (BASE,REFINE,COMPACT,FAST):
            e=self.engine()
            def change(_):e._artwork_v2_epoch+=1
            self.read(e,[row],change)
            self.assertFalse(e._artwork_v2_supported)
            self.assertEqual((e._artwork_v2_compact_challenge,e._artwork_v2_refine_challenge,e._artwork_v2_fast_challenge),('','',''))

    def test_stale_base_bool_is_not_fresh_base_proof(self):
        e=self.engine();e._artwork_v2_supported=True;e._artwork_v2_base_challenge=NEXT
        self.read(e,[REFINE]);self.assertEqual(e._artwork_v2_compact_challenge,'')

    def test_inference_rejects_old_connection_epoch_nonce_closed_and_stopped(self):
        for variant in ('conn','epoch','nonce','closed','stopped','inactive'):
            e=self.engine();conn=e.serial_conn;generation=(e._artwork_v2_epoch,TOKEN)
            e._artwork_v2_supported=True;e._artwork_v2_base_challenge=TOKEN;e._artwork_v2_refine_challenge=TOKEN
            if variant=='conn':e.serial_conn=Mock(is_open=True)
            if variant=='epoch':e._artwork_v2_epoch+=1
            if variant=='nonce':e._artwork_v2_challenge=NEXT
            if variant=='closed':conn.is_open=False
            if variant=='stopped':e._stop_requested.set()
            if variant=='inactive':e.running=False
            e._confirm_compact_from_refine(conn,generation)
            self.assertEqual(e._artwork_v2_compact_challenge,'')

    def test_resync_rearms_proofs_and_rejects_old_refine(self):
        e=self.engine();self.read(e,[BASE,REFINE]);e.running=True
        e.get_system_stats=Mock(return_value=(1,2));e._last_media_snapshot=None
        with patch('engine.secrets.token_hex',return_value=NEXT.lower()),patch('engine.diagnostics.event'),patch('builtins.print'):
            e._resync_device()
        self.assertEqual(e._artwork_v2_base_challenge,'');self.assertEqual(e._artwork_v2_compact_challenge,'')
        self.read(e,[BASE.replace(TOKEN.encode(),NEXT.encode()),REFINE])
        self.assertEqual(e._artwork_v2_compact_challenge,'')
        self.read(e,[REFINE.replace(TOKEN.encode(),NEXT.encode())])
        self.assertEqual(e._artwork_v2_compact_challenge,NEXT)

    def test_inferred_compact_then_real_ack_slot_and_full_refinement_use_same_cache(self):
        from test_artwork_refinement import make_pair,send_primary,until,RGB
        from turntable_face_host import snapshot
        e,wire,reader=make_pair()
        try:
            with e._media_lock:
                e._artwork_v2_supported=False;e._artwork_v2_base_challenge=''
                e._artwork_v2_compact_challenge='';e._artwork_v2_refine_challenge=''
            wire.rx.put(BASE);wire.rx.put(REFINE)
            until(lambda:e._artwork_v2_compact_challenge==TOKEN)
            self.assertIs(e._cached_artwork,RGB)
            send_primary(e);until(lambda:e._artwork_refinement['shown'])
            job=e._take_artwork_refinement();self.assertIs(job['artwork'],RGB)
            coarse=bytes(snapshot(wire.h))
            with patch('engine.time.sleep'):e._send_artwork_v2(wire,job['track'],job['artwork'],0,job)
            self.assertEqual((wire.compact_ends,wire.full_ends),(1,1));self.assertTrue(wire.low_held)
            self.assertNotEqual(bytes(snapshot(wire.h)),coarse)
            headers=[p.splitlines()[0] for p in wire.writes if p.startswith(b'MEDIA_ART2_BEGIN')]
            self.assertIn(b':80:80:12800:',headers[0]);self.assertIn(b':112:112:37632:',headers[1])
        finally:e.running=False;wire.rx.put(b'\n');reader.join(.5)


if __name__=='__main__':unittest.main()

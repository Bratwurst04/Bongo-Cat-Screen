"""Actual engine payload -> actual C++ byte framer, plus actual glyph data."""
import ctypes
from pathlib import Path
import sys
import unicodedata
import unittest
from dataclasses import replace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'companion'), str(ROOT / 'tests'), str(ROOT / 'tools')]
from engine import BongoCatEngine
import test_artwork_v2 as artwork_tests
from media_bridge import MediaSnapshot
from record_flip_host import load_host
from generate_media_swedish_font import generate
from record_flip_visuals import glyph_data


class MediaTextTests(unittest.TestCase):
    def test_nfc_decomposed_swedish_and_previous_ascii_fallback(self):
        clean = BongoCatEngine._clean_media_text
        for text in ('Dö ung', 'åäöÅÄÖ'):
            self.assertEqual(clean(text), text)
            self.assertEqual(clean(unicodedata.normalize('NFD', text)), text)
        self.assertEqual(clean('Beyoncé — café 東京'), 'Beyonce cafe')
        self.assertEqual(clean('Dö\nMEDIA_CMD:PLAY\x00\x1b\r\nHov1|x'), 'Dö MEDIA_CMD:PLAY Hov1/x')

    def test_actual_payload_utf8_byte_fragmentation_and_line_budget(self):
        host = load_host();host.rf_serial_reset()
        engine = artwork_tests.ArtworkV2Tests().make_engine()
        snapshot = MediaSnapshot(available=True, source='SPOTIFY API', title='Dö ung',
                                 artist='Hov1 åäöÅÄÖ', track_key='fixture', duration_seconds=180)
        engine._on_media_update(snapshot, None)
        data = b''.join(call.args[0] for call in engine.serial_conn.write.call_args_list)
        self.assertIn('MEDIA_TITLE:Dö ung\n'.encode('utf-8'), data)
        self.assertIn('MEDIA_ARTIST:Hov1 åäöÅÄÖ\n'.encode('utf-8'), data)
        completed = []
        for index, byte in enumerate(data):
            result = host.rf_serial_push(byte, index // 3)
            self.assertNotEqual(result, 2)
            if result == 1:completed.append(host.rf_serial_line().decode('utf-8'))
        self.assertIn('MEDIA_TITLE:Dö ung', completed)
        self.assertIn('MEDIA_ARTIST:Hov1 åäöÅÄÖ', completed)
        self.assertTrue(completed[-1].startswith('MEDIA_TRACK_CONTEXT:'))
        self.assertTrue(all(len(line) < 256 for line in data.splitlines()))
        engine.serial_conn.write.reset_mock()
        engine._on_media_update(replace(snapshot, title='ö' * 200, artist='Å' * 200, track_key='long'), None)
        longest = b''.join(call.args[0] for call in engine.serial_conn.write.call_args_list)
        self.assertIn(('MEDIA_TITLE:' + 'ö' * 72).encode(), longest)
        self.assertTrue(all(len(line) <= 157 for line in longest.splitlines()))

    def test_control_numerics_art2_and_overflow_recovery_stay_ascii(self):
        host = load_host();host.rf_serial_reset()
        for byte in b'x' * 256:self.assertEqual(host.rf_serial_push(byte, 0), 0)
        self.assertEqual(host.rf_serial_push(10, 1), 2)
        for byte in b'MEDIA_TIME:1:180\n':last = host.rf_serial_push(byte, 2)
        self.assertEqual(last, 1)
        self.assertEqual(host.rf_serial_line(), b'MEDIA_TIME:1:180')
        self.assertIn('header.encode("ascii")', (ROOT / 'companion/engine.py').read_text(encoding='utf-8'))

    def test_real_engine_duration_correction_is_not_a_track_change(self):
        engine = artwork_tests.ArtworkV2Tests().make_engine()
        snapshot = MediaSnapshot(available=True, source='SPOTIFY API', title='Dö ung',
                                 artist='Hov1', track_key='fixture', duration_seconds=0)
        engine._on_media_update(snapshot, None)
        engine.serial_conn.write.reset_mock()
        engine._on_media_update(replace(snapshot, duration_seconds=180), None)
        payload = b''.join(call.args[0] for call in engine.serial_conn.write.call_args_list)
        self.assertIn(b'MEDIA_TIME:0:180\n', payload)
        self.assertNotIn(b'MEDIA_ART_DEFAULT', payload)
        self.assertNotIn(b'MEDIA_TRACK_CONTEXT', payload)

    def test_generated_glyphs_are_real_six_character_fallback_at_both_sizes(self):
        self.assertEqual((ROOT/'src/media_swedish_font.h').read_text(encoding='utf-8'), generate())
        source = (ROOT/'src/bongo_cat_featured.inc').read_text(encoding='utf-8')
        for size, label in ((16, 'media_title_label'), (14, 'media_artist_label')):
            self.assertIn(f'lv_obj_set_style_text_font({label}, &lv_font_media_swedish_{size}, 0)', source)
            bitmap, glyphs = glyph_data(size)
            self.assertEqual(set(glyphs), set('åäöÅÄÖ'))
            for char, (offset, advance, width, height, ox, oy) in glyphs.items():
                self.assertGreater(advance, 0)
                self.assertLessEqual(offset + (width * height + 1) // 2, len(bitmap))
                top = [((bitmap[offset+i//2] >> (4 if i%2==0 else 0)) & 15)
                       for i in range(width * 3)]
                self.assertIn(15, top, char)


if __name__ == '__main__': unittest.main()

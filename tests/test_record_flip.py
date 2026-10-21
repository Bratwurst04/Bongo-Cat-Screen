"""Legacy 280ms helper with frozen pre-staging integration and current guards.
Current scene/staging/transport is executed by test_turntable*.py.
"""
import ctypes
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tests'), str(ROOT / 'tools')]
from record_flip_host import load_host
import export_ui_visuals as v


class RecordFlipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.host = load_host()

    def setUp(self):
        self.host.rf_reset()
        self.host.rf_event(0, 0, 0, 0)
        self.host.rf_event(3, 0, 0, 0)

    def event(self, kind, value=0, now=0, animate=True):
        return self.host.rf_event(kind, value, now, animate)

    def frame(self, now, visible=True):
        result = (ctypes.c_int * 3)()
        self.host.rf_frame(now, visible, result)
        return tuple(result)

    def test_full_outgoing_and_incoming_flip_is_280ms(self):
        self.event(1, 1)
        self.assertEqual(self.frame(0), (1, 0, 1))
        self.assertEqual(self.frame(120), (1, 6, 1))
        self.assertEqual(self.frame(140), (0, 7, 1))
        self.assertEqual(self.frame(280), (0, 14, 0))
        self.event(3, now=600)
        self.assertEqual(self.frame(600), (0, 0, 1))
        self.assertEqual(self.frame(740), (1, 7, 1))
        self.assertEqual(self.frame(880), (1, 14, 0))

    def test_new_committed_cover_during_outgoing_drops_old_face_immediately(self):
        self.event(1, 1)
        self.assertEqual(self.frame(80), (1, 4, 1))
        self.event(3, now=100)
        self.assertEqual(self.frame(100), (1, 7, 1))
        self.assertEqual(self.frame(240), (1, 14, 0))

    def test_new_track_cancels_old_incoming_no_queue_and_only_latest_target(self):
        self.event(1, 1);self.frame(280);self.event(3, now=600)
        self.event(1, 2, now=620)
        self.assertEqual(self.frame(620), (0, 14, 0))
        self.event(3, now=660)
        self.assertEqual(self.frame(940), (1, 14, 0))
        self.assertEqual(self.frame(100000), (1, 14, 0))

    def test_default_fullsync_and_art_retries_do_not_reflip_same_track(self):
        self.event(1, 1);self.event(2, 101);self.frame(280)
        self.event(3, now=600);self.frame(880)
        for now in (3000, 6000, 9000):
            self.assertFalse(self.event(1, 1, now))
            self.assertFalse(self.event(2, 101, now))
            self.assertFalse(self.event(3, now=now))
            self.assertEqual(self.frame(now), (1, 14, 0))

    def test_same_title_different_context_still_counts_as_real_track_change(self):
        self.event(2, 101)
        self.event(1, 0, now=50)
        self.assertEqual(self.frame(50), (1, 14, 0))
        self.assertTrue(self.event(2, 102, now=60))
        self.assertEqual(self.frame(60), (1, 0, 1))

    def test_changed_key_without_default_still_flips_identical_title_artist(self):
        self.event(2, 101)
        self.assertTrue(self.event(2, 102, now=60))
        self.assertEqual(self.frame(60), (1, 0, 1))

    def test_dj_menu_other_panel_settle_and_return_full_latest(self):
        self.event(1, 1)
        self.assertEqual(self.frame(100, visible=False), (0, 14, 0))
        self.event(3, now=180, animate=False)
        self.assertEqual(self.frame(500), (1, 14, 0))

    def test_millis_wrap_has_no_stuck_animation(self):
        start = 0xFFFFFFF0
        self.event(1, 1, now=start)
        self.assertEqual(self.frame((start + 140) & 0xFFFFFFFF), (0, 7, 1))
        self.assertEqual(self.frame((start + 280) & 0xFFFFFFFF), (0, 14, 0))

    def test_actual_projection_height_edge_width_and_read_only_sources(self):
        words = ctypes.c_ushort * (112 * 112)
        art = words(*([12345] * (112 * 112)));out = words()
        palette = (ctypes.c_ushort * 5)(0, 1, 2, 3, 4)
        heights = []
        for step in range(15):
            self.host.rf_render(out, art, 1, step, True, 0, 32767, palette)
            heights.append(len({i // 112 for i, value in enumerate(out) if value}))
            self.assertEqual(set(art), {12345})
            if step == 7:
                self.assertEqual(sum(bool(p) for p in out), 92 * 2)
        self.assertEqual(heights, [112, 109, 101, 88, 70, 49, 25, 2, 25, 49, 70, 88, 101, 109, 112])

    def test_latest_active_slot_is_only_art_source_after_coalescing(self):
        words = ctypes.c_ushort * (112 * 112)
        old = words(*([1111] * (112 * 112)));latest = words(*([2222] * (112 * 112)))
        out = words();palette = (ctypes.c_ushort * 5)(0, 1, 2, 3, 4)
        self.event(1, 1);self.event(3, now=100)
        # Simulate next BEGIN overwriting the previous active slot after ACK.
        for i in range(len(old)): old[i] = 3333
        side, step, moving = self.frame(160)
        self.host.rf_render(out, latest, side, step, moving, 0, 32767, palette)
        self.assertIn(2222, out)
        self.assertNotIn(1111, out);self.assertNotIn(3333, out)
        self.assertEqual(set(latest), {2222})

    def test_real_firmware_transport_and_rotation_hooks(self):
        source = v.FIRMWARE.read_text(encoding='utf-8')
        activate = v.section(source, 'activateMediaArtwork')
        self.assertIn('media_record_flip.artworkInSlot', activate)
        self.assertNotIn('media_art_active_buffer = buffer_index', activate)
        self.assertNotIn('renderRecordFrame', activate)
        self.assertNotIn('delay(', activate)
        self.assertNotIn('media_vinyl_angle = 0', activate)
        generic = v.section(source, 'loadGenericVinyl')
        self.assertNotIn('media_art_buffers[', generic)
        self.assertNotIn('activateMediaArtwork', generic)
        art2 = v.section(source, 'handleMediaArt2Command')
        self.assertIn('media_art_receiving_buffer = media_record_flip.beginArtwork()', art2)
        self.assertLess(art2.index('media_art_v2.complete('), art2.index('activateMediaArtwork('))
        self.assertLess(art2.index('activateMediaArtwork('), art2.index('MEDIA_ART2_OK:'))
        self.assertIn('media_record_flip.moving()', v.section(source, 'updateMediaVinyl'))
        self.assertIn('!media_is_playing', v.section(source, 'updateMediaVinyl'))
        duration_change = source[source.index('uint32_t next_duration ='):source.index('refreshMediaProgressUi();', source.index('uint32_t next_duration ='))]
        self.assertNotIn('media_record_metadata_revision', duration_change)
        self.assertEqual(self.host.rf_state_bytes(), 20)

    def test_actual_firmware_activation_acks_before_render_and_releases_old_slot(self):
        self.host.rf_fw_reset();self.host.rf_fw_default()
        self.host.rf_fw_accept()
        self.assertEqual(self.host.rf_fw_acks(), 1)  # No frame/render call yet.
        self.assertEqual(self.host.rf_fw_next_begin(), 0)
        self.host.rf_fw_overwrite_received()
        out = (ctypes.c_ushort * (112 * 112))()
        self.host.rf_fw_draw(out, 160)
        self.assertIn(2222, out)
        self.assertNotIn(1111, out);self.assertNotIn(3333, out)
        before = [self.host.rf_fw_sum(i) for i in (0, 1)]
        self.host.rf_fw_generic()  # Actual production generic function.
        self.assertEqual(before, [self.host.rf_fw_sum(i) for i in (0, 1)])

    def test_actual_duration_correction_then_same_context_resync_keeps_full_art(self):
        self.host.rf_fw_reset()
        self.host.rf_fw_duration(180)  # Execute the actual firmware duration branch.
        self.host.rf_fw_resync()
        result = (ctypes.c_int * 3)()
        self.host.rf_fw_frame(50, result)
        self.assertEqual(tuple(result), (1, 14, 0))
        self.host.rf_fw_new_context()  # Same title/artist, really different key.
        self.host.rf_fw_frame(60, result)
        self.assertEqual(tuple(result), (1, 0, 1))

    def test_oom_generic_bounds_and_no_retries_in_service_or_ack(self):
        words = ctypes.c_ushort * (64 * 64)
        out = words(*([54321] * (64 * 64)))
        palette = (ctypes.c_ushort * 5)(0, 1, 2, 3, 4)
        self.assertFalse(self.host.rf_reduced(out, 56 * 56 - 1, palette))
        self.assertEqual(set(out), {54321})
        self.assertTrue(self.host.rf_reduced(out, 64 * 64, palette))
        self.assertNotIn(54321, out[:56 * 56])
        self.assertEqual(set(out[56 * 56:]), {54321})
        source = v.FIRMWARE.read_text(encoding='utf-8')
        self.assertEqual(source.count('heap_caps_malloc('), 1)
        self.assertIn('heap_caps_malloc(', v.section(source, 'allocateMediaRecordPixels'))
        self.assertIn('allocateMediaRecordPixels();', v.section(source, 'createMediaScreen'))
        self.assertEqual(self.host.rf_oom_probe(), 1)
        update = v.section(source, 'updateMediaRecordFlip')
        self.assertNotIn('malloc', update)
        self.assertLess(update.index('if (!visible)'), update.index('renderTurntableGenericReduced'))
        self.assertIn('visible && media_record_pixels', update)
        self.assertIn('image->header.w == RECORD_PIXELS / 2 ? 2 : 1', update)
        ui = v.section(source, 'refreshMediaUi')
        self.assertLess(ui.index('renderMediaCat();'), ui.index('lv_obj_clear_flag(media_cat_canvas'))
        self.assertIn('lv_canvas_fill_bg(media_cat_canvas', v.section(source, 'renderMediaCat'))

    def test_historical_preview_matches_frozen_sources_and_outputs(self):
        if not (ROOT/'build/record-flip-2026-10-15-r2/source-frozen').exists():
            self.skipTest('Historical record preview source archive absent')
        output = ROOT / 'visuals/record-flip-2026-10-15/final'
        manifest = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual((manifest['flip_ms'], manifest['frame_ms']), (280, 20))
        for path, digest in manifest['source_sha256'].items():
            self.assertEqual(hashlib.sha256((ROOT/'build/record-flip-2026-10-15-r2/source-frozen'/path).read_bytes()).hexdigest().upper(), digest, path)
        for name, digest in manifest['output_sha256'].items():
            self.assertEqual(hashlib.sha256((output/name).read_bytes()).hexdigest().upper(), digest, name)
        self.assertTrue(all(not f['playing'] for f in manifest['states']['paused']))
        self.assertTrue(all(not f['compact'] for f in manifest['states']['dj-interrupt']))


if __name__ == '__main__': unittest.main()

"""Real software-raster regression checks; no physical TFT/FPS claim."""
import json
import unittest
from unittest.mock import patch
import lvgl_viewport_host as port
from lvgl_viewport_host import BUILD, library


class ViewportRasterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.host = library()

    def run_case(self, number):
        host = self.host
        self.assertEqual(host.vp_run(number), 0, host.vp_error().decode('utf-8'))
        self.assertGreater(host.vp_measure(2), 0)
        return host

    def test_normal_compact_rotation_and_reduced_generic(self):
        host = self.run_case(0)
        measurements = {
            'lvgl': '8.3.11 actual software renderer',
            'rotation_frames': 400,
            'reduced_generic_rotation_frames': 400,
            'viewport_flushed_pixels': host.vp_measure(0),
            'screen_parent_flushed_pixels': host.vp_measure(1),
            'compared_incremental_frames': host.vp_measure(2),
            'isolated_legacy_sampling_difference_pixels': host.vp_measure(3),
            'isolated_legacy_sampling_max_difference_pixels_per_frame': host.vp_measure(4),
            'isolated_legacy_sampling_different_frames': host.vp_measure(5),
            'isolated_legacy_112_max_difference_pixels': host.vp_measure(6),
            'isolated_legacy_56_max_difference_pixels': host.vp_measure(7),
            'sampling_limit': 'symmetric nearest color within 1 display pixel, at most 32 differences/frame',
            'full_vs_incremental_tolerance': 0,
            'physical_fps_cpu_tft_measured': False,
        }
        (BUILD / 'rotation-raster-measures.json').write_text(json.dumps(measurements, indent=2), encoding='utf-8')
        self.assertLess(measurements['viewport_flushed_pixels'], measurements['screen_parent_flushed_pixels'])

    def test_flip_full_withdrawal_rapid_track_and_slots(self):
        self.run_case(1)

    def test_focus_dj_menu_panel_cancel_and_return(self):
        self.run_case(2)

    def test_real_swedish_marquee_and_pixel_oracle(self):
        self.run_case(3)

    def test_host_varargs_abi_uses_real_lvgl_formatter(self):
        self.assertEqual(self.host.vp_format_test(), 5)
        self.assertEqual(self.host.vp_error(), b'17 OK')

    def test_build_cache_routes_each_output_and_input_identity(self):
        # Regression for the old argument-free cached helpers: a second fresh
        # output must reach the builder with its own path, even after first use.
        with patch.object(port, '_library', side_effect=lambda *key: key):
            first = port.library()
            with patch.object(port, 'BUILD', port.BUILD / 'second-output'):
                second = port.library()
        self.assertNotEqual(first[0], second[0])
        self.assertEqual(first[1:], second[1:])
        self.assertEqual(len(first[2]), 64)

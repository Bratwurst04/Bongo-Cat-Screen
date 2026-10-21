"""Timing bucket boundaries, wrap, context isolation and sparse report cadence."""
import unittest
from render_diagnostics_host import load_host


class RenderDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.host = load_host()
        self.host.rd_reset()

    def test_histogram_exact_boundaries_and_maximum(self):
        values = [0, 1000, 1001, 4000, 4001, 16000, 16001, 33000, 33001, 66000, 66001, 0xFFFFFFFF]
        for value in values:
            self.host.rd_flush(0, value, 0, 0)
        self.assertEqual(self.host.rd_value(0, 2, 0), 12)
        self.assertEqual(self.host.rd_value(0, 2, 1), 0xFFFFFFFF)
        self.assertEqual([self.host.rd_value(0, 2, i) for i in range(2, 8)], [2] * 6)

    def test_micros_wrap_for_handler_gap_and_flush(self):
        self.assertTrue(self.host.rd_begin(0xFFFFFFF0, 1, 0))
        self.host.rd_end(0x10)
        self.assertTrue(self.host.rd_begin(0x20, 1, 0))
        self.host.rd_end(0x50)
        self.host.rd_flush(0xFFFFFFFE, 1, 1, 0)
        self.assertEqual(self.host.rd_value(1, 0, 0), 1)
        self.assertEqual(self.host.rd_value(1, 0, 1), 48)
        self.assertEqual(self.host.rd_value(1, 1, 0), 2)
        self.assertEqual(self.host.rd_value(1, 1, 1), 48)
        self.assertEqual(self.host.rd_value(1, 2, 1), 3)

    def test_playing_paused_and_transfer_samples_are_separate(self):
        for group in range(4):
            self.assertTrue(self.host.rd_begin(1000 * (group + 1), group & 1, group >> 1))
            self.host.rd_end(1000 * (group + 1) + group + 1)
            self.host.rd_flush(0, group + 10, group & 1, group >> 1)
        for group in range(4):
            self.assertEqual(self.host.rd_value(group, 1, 0), 1)
            self.assertEqual(self.host.rd_value(group, 1, 1), group + 1)
            self.assertEqual(self.host.rd_value(group, 2, 1), group + 10)

    def test_nested_handler_does_not_overwrite_outer_sample(self):
        self.assertTrue(self.host.rd_begin(100, 1, 0))
        self.assertFalse(self.host.rd_begin(150, 0, 1))
        self.host.rd_end(300)
        self.assertEqual(self.host.rd_value(1, 1, 0), 1)
        self.assertEqual(self.host.rd_value(1, 1, 1), 200)
        self.assertEqual(self.host.rd_value(2, 1, 0), 0)
        self.host.rd_end(400)
        self.assertEqual(self.host.rd_value(1, 1, 0), 1)

    def test_report_interval_exact_boundary_and_millis_wrap(self):
        self.assertFalse(self.host.rd_due(14999))
        self.assertTrue(self.host.rd_due(15000))
        self.assertFalse(self.host.rd_due(29999))
        self.assertTrue(self.host.rd_due(30000))
        self.assertTrue(self.host.rd_due(0xFFFFFF00))
        self.assertFalse(self.host.rd_due((0xFFFFFF00 + 14999) & 0xFFFFFFFF))
        self.assertTrue(self.host.rd_due((0xFFFFFF00 + 15000) & 0xFFFFFFFF))

    def test_window_reset_keeps_real_entry_gap_and_clears_counters(self):
        self.host.rd_begin(1000, 0, 0)
        self.host.rd_end(1100)
        self.host.rd_clear()
        self.assertEqual(self.host.rd_value(0, 1, 0), 0)
        self.host.rd_begin(2000, 0, 0)
        self.host.rd_end(2010)
        self.assertEqual(self.host.rd_value(0, 0, 0), 1)
        self.assertEqual(self.host.rd_value(0, 0, 1), 1000)
        self.assertEqual(self.host.rd_value(0, 1, 1), 10)


if __name__ == "__main__":
    unittest.main()

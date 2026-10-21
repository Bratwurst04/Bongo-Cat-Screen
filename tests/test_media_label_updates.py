"""Real current metadata/refresh path; LVGL boundary counts, no FPS/phase claim."""
import unittest
from media_label_host import load_host

TITLE = "Återvändande skymning över sjön med äventyr och öar på vägen"
ARTIST = "Ängsliga örnar från Åmål med långa artistnamn"


class MediaLabelUpdateTests(unittest.TestCase):
    def setUp(self):
        self.host = load_host()
        self.host.mt_reset()

    def command(self, text, now=0):
        self.host.mt_apply(text.encode("utf-8"), now)

    def settled(self):
        for text in ("MEDIA_SOURCE:SPOTIFY", "MEDIA_TITLE:" + TITLE,
                     "MEDIA_ARTIST:" + ARTIST, "MEDIA_STATE:PLAYING"):
            self.command(text)

    def test_first_render_and_real_title_change_still_update(self):
        self.settled()
        self.assertEqual(self.host.mt_text(1).decode("utf-8"), TITLE)
        self.assertEqual(self.host.mt_text(2).decode("utf-8"), ARTIST)
        self.assertEqual(self.host.mt_writes(1), 2)  # initial placeholder, then actual title
        before = self.host.mt_writes(1)
        self.command("MEDIA_TITLE:Åäö Ett annat verkligt långt låtnamn")
        self.assertEqual(self.host.mt_writes(1), before + 1)
        self.assertEqual(self.host.mt_text(1).decode("utf-8"), "Åäö Ett annat verkligt långt låtnamn")

    def test_three_second_metadata_repeats_do_not_call_label_or_color_setters(self):
        self.settled()
        writes, colors, revision, anchor = (self.host.mt_total(), self.host.mt_colors(),
                                            self.host.mt_revision(), self.host.mt_anchor())
        for now in range(3000, 30001, 3000):
            for command in ("MEDIA_SOURCE:SPOTIFY", "MEDIA_TITLE:" + TITLE,
                            "MEDIA_ARTIST:" + ARTIST, "MEDIA_STATE:PLAYING"):
                self.command(command, now)
        self.assertEqual(self.host.mt_total(), writes)
        self.assertEqual(self.host.mt_colors(), colors)
        self.assertEqual(self.host.mt_revision(), revision)
        self.assertEqual(self.host.mt_anchor(), anchor)

    def test_state_transitions_update_only_status_and_button(self):
        self.settled()
        before = self.host.mt_total()
        title_writes = self.host.mt_writes(1)
        self.command("MEDIA_STATE:PAUSED", 1000)
        self.assertEqual(self.host.mt_total(), before + 2)
        self.assertEqual(self.host.mt_text(3), b"PAUSED")
        self.command("MEDIA_STATE:PAUSED", 3000)
        self.assertEqual(self.host.mt_total(), before + 2)
        self.assertEqual(self.host.mt_anchor(), 1000)
        self.command("MEDIA_STATE:PLAYING", 4000)
        self.assertEqual(self.host.mt_total(), before + 4)
        self.assertEqual(self.host.mt_writes(1), title_writes)
        self.assertEqual(self.host.mt_anchor(), 4000)

    def test_time_updates_only_the_changed_elapsed_or_duration_label(self):
        self.settled()
        self.command("MEDIA_TIME:3:180")
        self.assertEqual(self.host.mt_text(5), b"0:03")
        self.assertEqual(self.host.mt_text(6), b"3:00")
        before = self.host.mt_total()
        self.command("MEDIA_TIME:3:180", 3000)
        self.assertEqual(self.host.mt_total(), before)
        self.command("MEDIA_TIME:4:180", 4000)
        self.assertEqual(self.host.mt_total(), before + 1)
        self.command("MEDIA_TIME:4:181", 5000)
        self.assertEqual(self.host.mt_total(), before + 2)

    def test_colors_change_once_per_dj_mode_change_not_on_art_activation(self):
        self.settled()
        before = self.host.mt_colors()
        self.host.mt_mode(1, 0)
        self.assertEqual(self.host.mt_colors(), before + 2)
        self.host.mt_mode(1, 0)
        self.assertEqual(self.host.mt_colors(), before + 2)
        self.host.mt_mode(0, 1)
        self.assertEqual(self.host.mt_colors(), before + 4)
        self.host.mt_mode(0, 0)
        self.assertEqual(self.host.mt_colors(), before + 4)


if __name__ == "__main__":
    unittest.main()

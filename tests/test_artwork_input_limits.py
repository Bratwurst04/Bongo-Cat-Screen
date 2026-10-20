"""Reject unexpected image formats and oversized inputs before pixel decode."""

import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from PIL import Image, UnidentifiedImageError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "companion"))
from media_bridge import WindowsMediaBridge


def encoded(format, size=(40, 40)):
    stream = io.BytesIO()
    Image.new("RGB", size, (30, 80, 120)).save(stream, format=format)
    return stream.getvalue()


class ArtworkInputLimitsTests(unittest.TestCase):
    def test_normal_jpeg_and_png_produce_same_vinyl_pixels(self):
        from fixtures.vinyl59fc import Installed59FC
        for format in ("JPEG", "PNG"):
            with self.subTest(format=format):
                payload = encoded(format)
                actual = WindowsMediaBridge._to_vinyl_rgb888(payload)
                self.assertEqual(len(actual), 112 * 112 * 3)
                self.assertEqual(actual, Installed59FC._to_vinyl_rgb888(payload))

    def test_other_formats_cannot_select_a_decoder(self):
        for format in ("GIF", "BMP", "TIFF", "WEBP"):
            with self.subTest(format=format), self.assertRaises(UnidentifiedImageError):
                WindowsMediaBridge._to_vinyl_rgb888(encoded(format))

    def test_byte_limit_precedes_image_open(self):
        with patch("media_bridge.Image.open", side_effect=AssertionError("Must not open")):
            for payload in (b"", b"x" * (8 * 1024 * 1024 + 1)):
                with self.assertRaises(ValueError):
                    WindowsMediaBridge._to_vinyl_rgb888(payload)

    def test_pixel_limit_precedes_decode(self):
        payload = encoded("PNG", (4097, 1))
        with patch("PIL.PngImagePlugin.PngImageFile.load", side_effect=AssertionError("Must not decode")):
            with self.assertRaisesRegex(ValueError, "dimensions"):
                WindowsMediaBridge._to_vinyl_rgb888(payload)

    def test_animated_png_is_rejected(self):
        stream = io.BytesIO()
        Image.new("RGB", (4, 4), "red").save(stream, format="PNG", save_all=True,
                                             append_images=[Image.new("RGB", (4, 4), "blue")], duration=100)
        with self.assertRaisesRegex(ValueError, "animation"):
            WindowsMediaBridge._to_vinyl_rgb888(stream.getvalue())


if __name__ == "__main__":
    unittest.main()

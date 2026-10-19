"""Selective SMTC cleanup; local authorized fixture, no Windows/profile/network I/O."""
import asyncio
import ctypes
import datetime as dt
from functools import lru_cache
import hashlib
import io
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, Mock, patch
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'companion'), str(ROOT/'tests')]
from artwork_crop import spotify_smtc_album_box
from media_bridge import WindowsMediaBridge
from frozen_source import load_module

FIXTURE = ROOT/'build/artwork-crop-2026-10-19/fixtures/whoopty-source.png'
FIXTURE_SHA = '25F4B3A2733D1BB4557D9A4A0D734F0374B9F0B462367490A2C7148C69F0E6F7'
FOOTER = ROOT/'tests/fixtures/spotify-smtc-footer-alpha.png'
FOOTER_SHA = 'F516F11E9F0D5D08BAC8791A5EECA3A64A7E8DFF5A9E766EC2A21565A255BEDB'
BOX = (33, 0, 267, 234)


def encoded(image, format='PNG'):
    output = io.BytesIO(); image.save(output, format=format); return output.getvalue()


def detect(payload):
    with Image.open(io.BytesIO(payload)) as image:
        return spotify_smtc_album_box(image)


def read_fixture():
    if not FIXTURE.exists():
        raise unittest.SkipTest('Authorized local SMTC fixture absent; original photo is not committed')
    payload = FIXTURE.read_bytes()
    assert hashlib.sha256(payload).hexdigest().upper() == FIXTURE_SHA
    with Image.open(io.BytesIO(payload)) as image:
        return payload, image.copy()


def synthetic_wrapper():
    # Independent full-resolution observed footer alpha, not the product's
    # downsampled signature. No album photo or title is part of this fixture.
    assert hashlib.sha256(FOOTER.read_bytes()).hexdigest().upper() == FOOTER_SHA
    image = Image.new('RGBA', (300, 300))
    album = Image.new('RGBA', (234, 234))
    album.putdata([((x*3)%256, (y*5)%256, ((x+y)*7)%256, 255)
                   for y in range(234) for x in range(234)])
    image.paste(album, (33, 0))
    footer = Image.new('RGBA', (192, 53), 'white')
    with Image.open(FOOTER) as alpha:
        footer.putalpha(alpha)
    image.paste(footer, (54, 247))
    return image


@lru_cache(maxsize=1)
def legacy_converter():
    return load_module('crop_legacy_reference', ROOT/'tests/fixtures/vinyl59fc.py').Installed59FC._to_vinyl_rgb888


def expected_without_inset(album):
    # Legacy 6% of264 is15: this independent padded input loses only padding,
    # leaving the exact234 square, including its outer album edge.
    assert album.size == (234, 234)
    padded = Image.new('RGB', (264, 264), (251, 1, 151)); padded.paste(album.convert('RGB'), (15, 15))
    return legacy_converter()(encoded(padded))


class CropTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image = synthetic_wrapper(); cls.payload = encoded(cls.image)

    def test_real_square_wrapper_exact_album_without_second_inset(self):
        payload, image = read_fixture()
        self.assertEqual(detect(payload), BOX)
        rgb = WindowsMediaBridge._to_vinyl_rgb888(payload, windows_spotify_thumbnail=True)
        self.assertEqual(rgb, expected_without_inset(image.crop(BOX)))
        self.assertNotEqual(rgb, legacy_converter()(payload))

    def test_scaled_wrapper_family(self):
        for edge, filter in ((600, Image.Resampling.NEAREST), (900, Image.Resampling.LANCZOS),
                             (1200, Image.Resampling.NEAREST), (450, Image.Resampling.LANCZOS)):
            with self.subTest(edge=edge, filter=filter):
                side = round(234*edge/300); left = (edge-side)//2
                self.assertEqual(detect(encoded(self.image.resize((edge, edge), filter))),
                                 (left, 0, left+side, side))

    def test_different_album_and_black_album_keep_same_recognition(self):
        for color in ((0, 0, 0, 255), (3, 150, 220, 255)):
            image = self.image.copy(); album = Image.new('RGBA', (234, 234), color)
            ImageDraw.Draw(album).rectangle((0, 0, 233, 233), outline=(200, 30, 20, 255), width=5)
            image.paste(album, BOX)
            payload = encoded(image)
            self.assertEqual(detect(payload), BOX)
            self.assertEqual(WindowsMediaBridge._to_vinyl_rgb888(payload, windows_spotify_thumbnail=True),
                             expected_without_inset(album))

    def negatives(self):
        source = self.image
        yield 'plain RGB square', encoded(source.convert('RGB'))
        opaque = source.copy(); opaque.putalpha(255)
        yield 'opaque RGBA square', encoded(opaque)
        yield 'already correct album', encoded(source.crop(BOX))
        yield 'black correct album', encoded(Image.new('RGBA', (300, 300), (0, 0, 0, 255)))
        footer = source.copy(); footer.paste((0, 0, 0, 0), (0, 234, 300, 300))
        ImageDraw.Draw(footer).rectangle((54, 247, 245, 299), fill=(255, 255, 255, 255))
        yield 'white footer alone', encoded(footer)
        wrong = source.copy(); wrong.paste(source.crop((54, 247, 246, 300)).transpose(Image.Transpose.FLIP_LEFT_RIGHT), (54, 247))
        yield 'mirrored logo', encoded(wrong)
        wrong = source.copy(); wrong.paste((255, 255, 255, 255), (0, 235, 300, 246))
        yield 'no transparent gap', encoded(wrong)
        wrong = source.copy(); wrong.paste((0, 0, 0, 255), (0, 0, 15, 230))
        yield 'opaque black side pad', encoded(wrong)
        wrong = source.copy(); wrong.paste((230, 20, 20, 255), (54, 247, 246, 300))
        yield 'colored footer', encoded(wrong)
        wrong = Image.new('RGBA', (300, 300)); wrong.paste(source, (-10, 0))
        yield 'wrong layout', encoded(wrong)
        yield 'all transparent', encoded(Image.new('RGBA', (300, 300)))
        yield 'flattened JPEG', encoded(source.convert('RGB'), 'JPEG')
        yield 'transparent WEBP unsupported', encoded(source, 'WEBP')
        yield 'uncertain small resampling', encoded(source.resize((150, 150), Image.Resampling.LANCZOS))
        yield 'portrait unrelated', encoded(source.resize((300, 450)))
        yield 'prior accepted synthetic cover', (ROOT/'visuals/artwork-compact80-2026-10-18/r1/fixture-cover.png').read_bytes()

    def test_meaningful_nonmatches_are_byteidentical_to_installed_converter(self):
        old = legacy_converter()
        for name, payload in self.negatives():
            with self.subTest(name=name):
                self.assertIsNone(detect(payload))
                expected = old(payload)
                self.assertEqual(WindowsMediaBridge._to_vinyl_rgb888(payload), expected)
                self.assertEqual(WindowsMediaBridge._to_vinyl_rgb888(payload, windows_spotify_thumbnail=True), expected)

    def test_default_caller_never_runs_detector_even_for_matching_wrapper(self):
        with patch('media_bridge.spotify_smtc_album_box', side_effect=AssertionError('Not opted in')):
            self.assertEqual(WindowsMediaBridge._to_vinyl_rgb888(self.payload), legacy_converter()(self.payload))

    def session(self, source):
        session = Mock(source_app_user_model_id=source)
        session.try_get_media_properties_async = AsyncMock(return_value=NS(
            title='unrelated title', artist='unrelated artist', album_artist='', album_title='',
            track_number=1, thumbnail=object()))
        session.get_playback_info.return_value.playback_status = 'PLAYING'
        session.get_timeline_properties.return_value = NS(position=dt.timedelta(seconds=1),
            end_time=dt.timedelta(seconds=100), last_updated_time=dt.datetime.now(dt.timezone.utc))
        return session

    def test_actual_windows_session_gate_converts_once_and_uses_existing_cache(self):
        for source, crop in (('Spotify.exe', True), ('OtherPlayer.exe', False)):
            bridge = WindowsMediaBridge(on_update=Mock()); bridge._spotify = Mock()
            with patch.object(bridge, '_read_thumbnail', AsyncMock(return_value=self.payload)) as read, \
                 patch.object(bridge, '_to_vinyl_rgb888', wraps=bridge._to_vinyl_rgb888) as convert, \
                 patch('media_bridge.diagnostics.event'):
                first = asyncio.run(bridge._read_session(self.session(source)))
                second = asyncio.run(bridge._read_session(self.session(source)))
            self.assertEqual(convert.call_count, 1); read.assert_awaited_once()
            convert.assert_called_once_with(self.payload, **({'windows_spotify_thumbnail': True} if crop else {}))
            self.assertEqual(first[1], WindowsMediaBridge._to_vinyl_rgb888(self.payload, windows_spotify_thumbnail=crop))
            self.assertIsNone(second[1]); self.assertEqual(bridge._spotify.mock_calls, [])

    def test_api_download_uses_existing_once_only_path_without_crop(self):
        bridge = WindowsMediaBridge(on_update=Mock()); bridge._spotify = Mock()
        bridge._spotify.download_artwork.return_value = self.payload
        with patch.object(bridge, '_to_vinyl_rgb888', wraps=bridge._to_vinyl_rgb888) as convert, \
             patch('media_bridge.diagnostics.event'):
            first = asyncio.run(bridge._try_api_artwork('fixture', 'https://fixture.invalid/cover'))
            second = asyncio.run(bridge._try_api_artwork('fixture', 'https://fixture.invalid/cover'))
        self.assertEqual(first, legacy_converter()(self.payload)); self.assertIsNone(second)
        convert.assert_called_once_with(self.payload)
        bridge._spotify.download_artwork.assert_called_once_with('https://fixture.invalid/cover')

    def test_cropped_common_cache_through_actual_sender_crc_slots_and_refinement(self):
        from test_artwork_refinement import make_pair, send_primary, until
        from turntable_face_host import snapshot, frame, Pixels
        from artwork_codec import pack_compact_rgb565, refinement_rgb888
        import test_artwork_v2 as legacy
        rgb = WindowsMediaBridge._to_vinyl_rgb888(self.payload, windows_spotify_thumbnail=True)
        engine, wire, reader = make_pair()
        try:
            engine._on_media_update(legacy.ArtworkV2Tests.snapshot('song'), rgb)
            send_primary(engine); until(lambda:engine._artwork_refinement['shown'])
            job = engine._take_artwork_refinement(); self.assertIs(job['artwork'], rgb)
            coarse = bytes(snapshot(wire.h)); before = list(frame(wire.h, 4000))
            with patch('engine.time.sleep'):
                engine._send_artwork_v2(wire, job['track'], job['artwork'], 0, job)
            fine = snapshot(wire.h); after = list(frame(wire.h, 4000))
            expected = Pixels(); wire.h.ca_legacy_pixels.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_ushort)]
            wire.h.ca_legacy_pixels(refinement_rgb888(rgb, pack_compact_rgb565(rgb)), expected)
            self.assertEqual(bytes(fine), bytes(expected)); self.assertNotEqual(bytes(fine), coarse)
            low = Pixels.from_buffer_copy(coarse)
            chroma = wire.h.ca_color(0, 255, 0)
            self.assertTrue(any(p==chroma for p in low))
            self.assertEqual([p==chroma for p in low], [p==chroma for p in fine])
            self.assertEqual(before, after); self.assertEqual((wire.compact_ends, wire.full_ends), (1, 1))
            self.assertTrue(wire.low_held)
        finally:
            engine.running=False; wire.rx.put(b'\n'); reader.join(.5)


if __name__ == '__main__':
    unittest.main()

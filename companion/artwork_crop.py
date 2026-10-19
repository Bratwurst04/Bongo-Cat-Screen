"""Recognize one evidenced transparent Spotify SMTC wrapper, fail closed.

Only the Windows Spotify thumbnail caller opts in. Geometry is the known
300px family; the signature contains ONLY its white footer alpha, no album.
Reference source SHA256: 25F4B3A2733D1BB4557D9A4A0D734F0374B9F0B462367490A2C7148C69F0E6F7.
"""
import math
from PIL import Image

_SIGNATURE_SIZE = (96, 27)
_SIGNATURE_HEX = (
    "007f8000000000000000000001ffe000000000000000000003fff80000000000000000000ffffc0000000000000000001ffffe0000000000000000001fffff0000000000000000003fffff001c00000000e1e0007fffff807f80000000e3e00070007f80ff80000008e3800070000fc0e180000038030000fbfc03c0c019c0787e6ff030ffffc1c0e03be1fefeeff870fe03f3c0fc3ff3fe7eeff860f8003fc07f3c3b8738e31ce0f9f80fc00fb83b0738e31ce0ffff87c003983b0738e30ec0ff07e7c0819c3b8738e30fc07c00ffc0c39c7b8738e307807ffc3f80ffbff1fe3ee307807fff9f807f3be0fc1ee307003fffff0008380030000007001fffff0000380000000007001ffffe000038000000000e000ffffc00000000000000000007fff800000000000000000001ffe0000000000000000000007f80000000000000000000"
)
_SIGNATURE = int.from_bytes(bytes.fromhex(_SIGNATURE_HEX), "big")


def _empty(alpha, box):
    return (box[2] > box[0] and box[3] > box[1] and
            alpha.crop(box).getextrema()[1] == 0)


def spotify_smtc_album_box(image):
    """Return known album square or None; never trim artwork by RGB darkness.

    Fixed layout evidence, one 300px-reference-pixel geometry tolerance
    (rounded up) and 97% logo alpha IoU are all required. Three reference-pixel edge guards permit only
    resampling fringes around otherwise fully transparent pads/gap. Small,
    flattened, opaque and uncertain inputs keep the caller's legacy path.
    """
    width, height = image.size
    if (image.mode != "RGBA" or getattr(image, "format", None) not in (None, "PNG") or
            width != height or not 128 <= width <= 2048):
        return None
    alpha = image.getchannel("A")
    if alpha.getextrema()[0] == 255 or alpha.getextrema()[1] == 0:
        return None
    scale = width / 300
    tolerance = max(1, math.ceil(scale))
    guard = max(1, math.ceil(3 * scale))
    side = round(234 * scale)
    left = (width - side) // 2
    album = (left, 0, left + side, side)
    footer = (round(54 * scale), round(247 * scale), round(246 * scale), height)
    split = round(240 * scale)
    core = alpha.point(lambda a: 255 if a >= 16 else 0)
    top_bounds = core.crop((0, 0, width, split)).getbbox()
    lower_bounds = core.crop((0, split, width, height)).getbbox()
    if not top_bounds or not lower_bounds:
        return None
    lower_bounds = (lower_bounds[0], lower_bounds[1] + split, lower_bounds[2], lower_bounds[3] + split)
    if (any(abs(a - b) > tolerance for a, b in zip(top_bounds, album)) or
            any(abs(a - b) > tolerance for a, b in zip(lower_bounds, footer))):
        return None
    if not all(_empty(alpha, b) for b in (
            (0, 0, left - guard, side - guard),
            (left + side + guard, 0, width, side - guard),
            (0, side + guard, width, footer[1] - guard))):
        return None
    histogram = alpha.crop(album).histogram()
    area = side * side
    if (area - histogram[0] < area * 0.995 or sum(histogram[240:]) < area * 0.97):
        return None
    opaque = white = 0
    for r, g, b, a in image.crop(footer).getdata():
        if a >= 128:
            opaque += 1
            white += min(r, g, b) >= 220 and max(r, g, b) - min(r, g, b) <= 16
    if not opaque or white < opaque * 0.98:
        return None
    bitmap = alpha.crop(footer).resize(_SIGNATURE_SIZE, Image.Resampling.LANCZOS)
    bits = int.from_bytes(bitmap.point(lambda a: 255 if a >= 128 else 0, mode="1").tobytes(), "big")
    union = (bits | _SIGNATURE).bit_count()
    if not union or (bits & _SIGNATURE).bit_count() * 100 < union * 97:
        return None
    return album

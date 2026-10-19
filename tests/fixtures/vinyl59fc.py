"""Frozen installed59FC converter reference; no runtime or optional WinRT imports."""
import io
from PIL import Image, ImageDraw, ImageOps
ART_SIZE = 112


class Installed59FC:
    @staticmethod
    def _to_vinyl_rgb888(image_bytes: bytes) -> bytes:
        """Build a colour-safe vinyl graphic with a full, clean cover label.

        RGB888 is deliberately used on the wire.  The ESP32 performs the final
        conversion with LVGL's own colour helper, avoiding controller-specific
        RGB565 byte-order differences.
        """
        with Image.open(io.BytesIO(image_bytes)) as source:
            source_rgb = source.convert("RGB")
            # Spotify's Windows thumbnail can include a tiny source badge at
            # the outer edge. A small centre crop removes that chrome before
            # filling the circular record label.
            inset = int(min(source_rgb.size) * 0.06)
            if inset > 0 and source_rgb.width > inset * 2 and source_rgb.height > inset * 2:
                source_rgb = source_rgb.crop((
                    inset, inset, source_rgb.width - inset, source_rgb.height - inset,
                ))
            label_size = int(round(ART_SIZE * 0.72))
            label = ImageOps.fit(
                source_rgb,
                (label_size, label_size),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )

        # Exact LVGL chroma-key green makes the square image corners
        # transparent after rotation, preventing the clipped/half-vinyl look.
        vinyl = Image.new("RGB", (ART_SIZE, ART_SIZE), (0, 255, 0))
        draw = ImageDraw.Draw(vinyl)
        edge = ART_SIZE - 3
        draw.ellipse((2, 2, edge, edge), fill=(16, 17, 20), outline=(61, 64, 70), width=2)

        # Subtle grooves plus two asymmetric highlights make rotation visible.
        for inset, shade in ((7, 35), (11, 24), (15, 39), (19, 27), (23, 43)):
            draw.ellipse(
                (inset, inset, ART_SIZE - 1 - inset, ART_SIZE - 1 - inset),
                outline=(shade, shade + 1, shade + 4),
                width=1,
            )
        draw.arc((6, 6, ART_SIZE - 7, ART_SIZE - 7), 202, 286, fill=(91, 94, 101), width=2)
        draw.arc((10, 10, ART_SIZE - 11, ART_SIZE - 11), 20, 66, fill=(41, 44, 50), width=2)
        center = ART_SIZE // 2
        draw.ellipse((center - 3, 4, center + 3, 10), fill=(30, 215, 96))

        label_mask = Image.new("L", label.size, 0)
        ImageDraw.Draw(label_mask).ellipse((0, 0, label_size - 1, label_size - 1), fill=255)
        label_xy = ((ART_SIZE - label_size) // 2,) * 2
        vinyl.paste(label, label_xy, label_mask)
        draw.ellipse((center - 4, center - 4, center + 4, center + 4), fill=(232, 235, 238))
        draw.ellipse((center - 1, center - 1, center + 1, center + 1), fill=(8, 10, 12))

        return vinyl.tobytes("raw", "RGB")

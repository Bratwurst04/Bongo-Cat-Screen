"""Compose existing Bongo sprites and index isolated native WinForms previews.

Render the views first with tests/test_settings_ui.ps1 -PreviewDirectory
visuals/companion-ui. No live companion, Spotify or serial access is used.
"""
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'visuals/companion-ui'
CAT = ROOT / 'companion/ui/bongo.png'
PARTS = ['body/standardbody1', 'face/stock_face', 'table/table1', 'paws/twopawsup']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    CAT.parent.mkdir(parents=True, exist_ok=True)
    cat = Image.new('RGBA', (64, 64))
    for part in PARTS:
        cat.alpha_composite(Image.open(ROOT / f'assets/cat-sprites/{part}.png').convert('RGBA'))
    cat.resize((128, 128), Image.Resampling.NEAREST).save(CAT)
    views = [('overview', 'Översikt'), ('settings', 'Inställningar'),
             ('settings-advanced', 'Avancerade intervall'), ('diagnostics', 'Diagnostik · API'),
             ('diagnostics-screen', 'Diagnostik · skärmen'), ('connect-waiting', 'Spotify · väntan')]
    sheet = Image.new('RGB', (1280, 1600), '#080A0C')
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 18)
    draw.text((20, 15), 'BONGO CAT COMPANION · WinForms med isolerade exempeldata · 2026-10-07', font=font, fill='#B8C1CB')
    for index, (name, caption) in enumerate(views):
        file = OUT / f'{name}.png'
        if not file.exists():
            continue
        x, y = 20 + (index % 2) * 640, 55 + (index // 2) * 510
        with Image.open(file) as image:
            image.thumbnail((620, 465), Image.Resampling.LANCZOS)
            sheet.paste(image, (x, y))
        draw.text((x, y + 470), caption, font=font, fill='#B8C1CB')
    sheet.save(OUT / 'contact_sheet.png')
    for name, title in [('overview', 'Översikt'), ('settings', 'Inställningar')]:
        before, after = OUT / 'before' / f'{name}.png', OUT / f'{name}.png'
        if not before.exists() or not after.exists():
            continue
        comparison = Image.new('RGB', (1280, 555), '#080A0C')
        cd = ImageDraw.Draw(comparison)
        for x, file, label in [(20, before, 'Före'), (660, after, 'Efter')]:
            cd.text((x, 12), f'{title} · {label} · isolerade exempeldata', font=font, fill='#B8C1CB')
            with Image.open(file) as native:
                native.thumbnail((620, 495), Image.Resampling.LANCZOS)
                comparison.paste(native, (x, 45))
        comparison.save(OUT / f'comparison-{name}.png')
    sources = ['companion/settings.ps1', 'companion/settings-view.ps1', 'companion/BongoDeskSpotify.spec',
               'tests/test_settings_ui.ps1'] + [f'assets/cat-sprites/{part}.png' for part in PARTS]
    manifest = {
        'date': '2026-10-07',
        'classification': 'native WinForms renders with isolated fixture data; not the installed app',
        'concept': 'concept.png is a drawn design proposal, not a native render',
        'before': 'before/ and comparison images preserve the first UI pass (candidate EC064E26…); these are not current renders',
        'contact_sheet': 'contact_sheet.png',
        'source_sha256': {path: sha(ROOT / path) for path in sources},
        'views': [{'file': path.name, 'dimensions': list(Image.open(path).size), 'sha256': sha(path)}
                  for path in sorted(OUT.glob('*.png'))],
        'limits': ['No real serial, Spotify, installed EXE, or user config was accessed by the UI fixture test.',
                   'Scale150 renders enlarge both fonts and geometry; they are not a monitor/DPI transition test.',
                   'DrawToBitmap does not verify compositor, real monitor appearance, screen readers or human keyboard use.',
                   'Sleep and wake are not exposed as explicit states by desktop_status.json.'],
    }
    (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

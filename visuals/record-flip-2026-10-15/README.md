# Skivflip och åäö – simulerade granskningsunderlag

Frames/tillstånd kommer från riktig C++-helper och de nya firmwareglyfernas
faktiska bitmaps. En normal flip är 280 ms, med 20 ms-steg. Detta är inte
uppmätt ESP32-fps eller fysisk acceptans. Planvinkeln är fryst till noll för
läsbarhet; ordinarie rotation hanteras av firmware.

- `normal.gif`, `focus.gif`: gammal skiva → generisk → komplett nytt omslag.
- `rapid.gif`: avbruten/coalescad följd; senaste orange omslag vinner.
- `paused.gif`: musik PAUSED, Fokus är ett separat fortfarande aktivt pass.
- `dj-interrupt.gif`, `focus-interrupt.gif`, `panel-interrupt.gif`: separata
  avbrott, hela slutbilder utan kvarhängande halva skivor.
- `oom-fallback.gif`: direkt byte, grövre generisk reserv i befintlig scratch.
- `scroll.gif`: riktiga 14/16-glyfer, 204 px-klipp och LVGL:s cirkulära
  tre-mellanslagsgap; 4 px per 160 ms är simulerade samples.
- `contact-sheet.png`, `scroll-contact-sheet.png`, `glyphs.png` och `*-end.png`.

UI godkände exakt manifest
`F0AA9837CC2FA55F798E4D81FAD66FE39ABC8F64E41AAD6FCCB96EE3CA4E1BA3`,
med åtta källhashar och 20 PNG/GIF-hashar. Bilderna innehåller endast
syntetiska omslag/texter och användarens tillåtna Dö ung/Hov1.
Se [bygg-/frysningsrapport](../../docs/record-flip-utf8-2026-10-15.md).

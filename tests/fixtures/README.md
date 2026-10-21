# Portable native and font fixtures

These are test/visual inputs, never application modules or firmware sources.
`portable-native.json` pins their hashes, byte sizes and local upstream hashes.
Missing/corrupt public fixtures fail; only explicitly optional historical
archives may skip a comparison.

- `lvgl8311-color16.inc`: exact LVGL 8.3.11 `lv_color16_t` and swapped
  `LV_COLOR_MAKE16` macro; `LV_COLOR_16_SWAP=1` matches the device.
- `lvgl8311-ascii-fonts.json`: exact ASCII glyphs, bitmaps, metrics and
  kerning from LVGL 8.3.11 Montserrat 10/14/16/20 and Unscii 16. Glyphs beyond ASCII are
  excluded. This is original data, not an approximated replacement font.
  The source generator and pixel rendering must agree with installed LVGL.
- `LVGL-LICENSE.txt`: unmodified upstream LVGL MIT license, copyright
  2021 LVGL Kft. `Montserrat-OFL.txt` retains the source font's copyright
  notice and [SIL Open Font License](https://github.com/JulietaUla/Montserrat/blob/master/OFL.txt).
  The Unscii data derives from `unscii-8.ttf`, whose non-full variants are
  [public domain according to its author Viznut](https://github.com/viznut/unscii).
- `record-c3-legacy.inc`: six extracted historical C3 firmware functions
  plus the three existing host adapters for BEGIN, duration and media touch.
  No seek implementation or complete old firmware is included. Current
  parser/CRC/slot/render tests continue extracting the current source.

The earlier `vinyl59fc.py` is the narrow historical vinyl conversion
reference. `spotify-smtc-footer-alpha.png` contains only the observed logo
alpha, without album art. The original album photo stays uncommitted; only
its real-reference test skips when it is unavailable.

`.gitattributes` fixes fixture `.inc`/`.json` files to LF so raw SHA pins
also work with Windows `core.autocrlf=true`. PNG remains binary. License
text hashes in the manifest normalize CRLF to LF; their wording is unchanged.

# app-v1.2 – verifiering och överlämning

Förberett 2026-10-03 i `D:\DEV\Ai\Github\Bongo-Cat-Screen`. Ingen commit, tagg, push, GitHub-publicering eller flashning gjordes i releaseförberedelsen. Projektledaren granskar först hela den ändrade källan och filerna.

## Bygg och test

- `python -m platformio run -e esp32-024r-spotify`: lyckades, RAM 34,0 %, flash 46,8 %. Appen `.pio/build/esp32-024r-spotify/firmware.bin` är 919904 byte och har SHA-256 `F0F7EC82E28AB30607EC59A8409B4B4876578D869403753C09DD33F3747FCFEF`. Den matchar exakt appen som flashades vid `0x10000` och provades den 2026-10-02.
- Xtensa C++ `-std=gnu++17 -fsyntax-only tests/focus_logic_compile.cpp`: godkänt.
- `python -X utf8 -m unittest discover -s tests -q`: 34 godkända tester. Companion-koden kompilerade med `python -m compileall -q companion tests`.
- `esptool image-info` visade giltiga checksumma och valideringshash för bootloader och app. Partitionstabellen avkodades och verifierades: `app0` börjar vid `0x10000` och är 1920 KiB.
- `git diff --check`: godkänt efter dokumentuppdatering.

## Komplett bild för `0x0`

`BongoDesk-app-v1.2-2026-10-03-full-0x0.bin`: 985440 byte, SHA-256 `B25028C1995AEFA81C99123133FA0A24898D2DA264DBBF2CDA9A2DBA3345B095`. Byggd med `esptool merge-bin --format raw` från dessa segment och kontrollerad byte för byte, inklusive `0xff` i varje mellanrum:

| Segment | Adress | Storlek | SHA-256 |
| --- | ---: | ---: | --- |
| Bootloader | `0x1000` | 17536 | `3D234A7471F67B013686DABD4DEE7C1FA915C9928463616A94BC9297ACF1ABF8` |
| Partitioner | `0x8000` | 3072 | `0A8B5720E7B77FF11F1462458C3A509DEE79224E5279898F26D6A2E3AE0517B7` |
| `boot_app0` | `0xe000` | 8192 | `F94C5D786A7A8FAB06AC5D10E33BF37711A6697636DC037559EA19CC410A17F0` |
| App | `0x10000` | 919904 | `F0F7EC82E28AB30607EC59A8409B4B4876578D869403753C09DD33F3747FCFEF` |

De tre startsegmenten är också byteidentiska med motsvarande delar i `app-v1.1`. Den sammanslagna `app-v1.2`-bilden har **inte** flashats från `0x0`. En sådan flashning skriver över NVS, inklusive sparade Fokus-värden.

## Windows companion

`BongoDeskSpotify-app-v1.2-2026-10-03.exe`: 19288447 byte, SHA-256 `71756E01987D8A84C76DDCF83B76E9C512A7B5B2E09439DB94D10E36109ABF9F`. Kopierad från den installerade, fysiskt provade EXE:n; den och utvecklingskandidaten i `dist/companion-2026-10-02-local-media-dev/` har samma hash. PyInstaller-arkivet kontrollerades för `engine`, `media_bridge`, `spotify_api` och `diagnostics`. Inga profiler, inställningar eller OAuth-token paketerades.

## Fysisk status och kvarstående prov

Appen vid `0x10000` har provats med Fokus 5/1, TIDER, meny, tema, lokala fassignaler, bortfall/släckning och väckning utan observerad ljusblixt. Observationerna är kvalitativa. Den installerade companionen har visat aktuell titel och rätt omslag samt styrt lokal Spotify via play/paus och NEXT även vid snabba låtbyten; loggen visade omslagskvittens utan seriellt bortfall. Användaren bekräftade också att Spelaren visar väntstatus vid Spotify API-spärr medan Bongo, tid och statistik fungerar. PREVIOUS provades i källkörning, men inte separat efter EXE-installationen.

Återstår: fysisk flash och start från den kompletta bilden vid `0x0`, strömmätning i deep sleep, exakt släcknings-/väcktid och LED-pulser samt återhämtning av samma låt/omslag efter en verklig Spotify-429 när ingen lokal Windows-session finns. Äldre releasefiler är bevarade.

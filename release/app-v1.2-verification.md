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

De tre startsegmenten är också byteidentiska med motsvarande delar i `app-v1.1`. När releaseförberedelsen skrevs hade den sammanslagna `app-v1.2`-bilden **inte** flashats från `0x0`; det efterföljande fysiska provet finns nedan. En sådan flashning skriver över NVS, inklusive sparade Fokus-värden.

## Windows companion

`BongoDeskSpotify-app-v1.2-2026-10-03.exe`: 19288447 byte, SHA-256 `71756E01987D8A84C76DDCF83B76E9C512A7B5B2E09439DB94D10E36109ABF9F`. Kopierad från den installerade, fysiskt provade EXE:n; den och utvecklingskandidaten i `dist/companion-2026-10-02-local-media-dev/` har samma hash. PyInstaller-arkivet kontrollerades för `engine`, `media_bridge`, `spotify_api` och `diagnostics`. Inga profiler, inställningar eller OAuth-token paketerades.

## Fysisk status och kvarstående prov

Appen vid `0x10000` har provats med Fokus 5/1, TIDER, meny, tema, lokala fassignaler, bortfall/släckning och väckning utan observerad ljusblixt. Observationerna är kvalitativa. Den installerade companionen har visat aktuell titel och rätt omslag samt styrt lokal Spotify via play/paus och NEXT även vid snabba låtbyten; loggen visade omslagskvittens utan seriellt bortfall. Användaren bekräftade också att Spelaren visar väntstatus vid Spotify API-spärr medan Bongo, tid och statistik fungerar. PREVIOUS provades i källkörning, men inte separat efter EXE-installationen.

## Efterföljande fullbildsprov 2026-10-03

Efter uttryckligt godkännande stoppades installerad companion. NVS (`0x9000`, `0x5000` byte) lästes före flashning separat och som del av en 1 MiB rollback-kopia; NVS-delarna matchade byte för byte. Fullbilden med SHA-256 `B25028C1995AEFA81C99123133FA0A24898D2DA264DBBF2CDA9A2DBA3345B095` flashades på COM6 vid `0x0`. Esptool verifierade skrivningens hash, och separat `verify-flash` matchade alla 985440 byte. NVS återställdes vid `0x9000` och lästes tillbaka; innehållet matchade den ursprungliga backupen byte för byte, SHA-256 `A83C3D9B31FCA2ACADB1A56D40A4BA9B9D4D28DEB233B0E17FCEE9086567FFCB`. Rollback-kopian finns kvar i ignorerade `.pio/device-backups/`.

Efter normal RESET/EN startade installerad companion med två processer. Loggen visade `SERIAL_CONNECT` 10:59:53 och `DEVICE_RESYNC` 10:59:57, därefter API-låt, `MEDIA_CMD_RX NEXT` 11:03:01 och lyckade `ART_ACK` 11:03:07 och 11:03:16. Användaren bekräftade normalt Bongo-UI med aktuell tid/statistik utan observerad ljusblixt, fungerande Fokusknappar och panelbyte samt rätt låt/omslag och touchstyrning av Spotify. TIDER visade 25/5. Read-only-avkodning av backupens NVS visade en aktiv, CRC-giltig `bongofocus`/`durations`-post `0x00050019` = 25/5 redan före flashningen; en äldre 5/1-post var markerad som raderad. Tidpunkten då 5/1 ändrades till 25/5 är okänd. Ett `MEDIA_REFRESH` med `error_type=OtherError` inträffade 11:03:01 efter NEXT, men ny låt och omslag följde och kvitterades. Samma feltyp hade synts 10:32:31 i det tidigare API-only-provet och återhämtade sig även då. Två övergående händelser är därmed observerade, utan kvarstående mediestörning i dessa prov.

Återstår: strömmätning i deep sleep, exakt släcknings-/väcktid och LED-pulser samt återhämtning av samma låt/omslag efter en ny verklig Spotify-429 utan lokal Windows-session. Äldre releasefiler är bevarade.

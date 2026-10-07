# app-v1.3 – verifiering och överlämning

Förberedd 2026-10-07 i `D:\DEV\Ai\Github\Bongo-Cat-Screen`. Releaseförberedelsen gör ingen firmwareflash. Projektledaren sköter installationsprovet och extern publicering. Companionens installationsprov är godkänt av Lead. Slutpaketet är fryst; den lokala releasecommiten omfattar endast de redovisade standarderna, profilerna, testerna, dokumenten och releasefilerna. Lead hanterar push/tagg/GitHub-publicering.

## Källändringar och prov

- `companion/config.py`, `default_config.json` och motorns två baudfallbacks använder 230400 för nya profiler. Ingen migrering eller ändring av protokoll, pacing eller UI.
- `platformio.ini` väljer `esp32-024r-spotify-fastserial` som standard, med 230400 i drift och ärvd flashhastighet 115200. Den namngivna `esp32-024r-spotify`-profilen behåller 115200 i drift. Fastserial-flaggorna och firmwarekällorna är oförändrade.
- PlatformIOs utlästa projektkonfiguration bekräftar fastserial som standard, uppladdning 115200 i båda profilerna och oförändrade ärvda fastserial-flaggor, utan ombyggnad.
- Två isolerade profiltester passerade: ny profil och motorns standardvägar ger 230400; befintlig giltig profil med uttryckligt 115200 laddas utan filändring och behåller baud, COM-port och oägt fält efter sparning. Backupen motsvarar den ursprungliga filen. Inga verkliga användarprofiler, Windows Run-poster eller token används i testerna.
- Alla 13 `test_power_resume.py`-tester passerade, inklusive skrivfel, återanslutning och återsynkning. `compileall` passerade. Den tidigare verifieringen omfattar 58 Python-tester, PowerShell-diagnostikprovet och 546 isolerade UI-kontroller; oförändrade UI-tester kördes inte om i releasepasset.

## Firmware: återanvänd provad app

Ingen firmware byggdes om i releasepasset. Appfilen är byteidentisk med `.pio/candidates/art2-core0-rx-6A5366C1.bin` och det tidigare lyckade fastserial-byggets app: 926432 byte, SHA-256 `6A5366C1E56E1137AEBC08E6675CBB12E1A49AE106D2DBD03B30132C6A7D2302`. Det tidigare bygget rapporterade RAM 34,2 % och flash 47,1 %. C++-gränstester kompilerades med Xtensa men kördes inte på värddatorn.

`BongoDesk-app-v1.3-2026-10-07-full-0x0.bin`: 991968 byte, SHA-256 `FE44F339D85084B9F9028AAE3146A12E78D3C0F87161425BB01B3989A7CAF491`. Sammanfogad med redan installerad esptool 5.3.1, `merge-bin --format raw`, DIO/40 MHz/4 MB. Varje segment kontrollerades byte för byte och varje mellanrum mot `0xff`:

| Segment | Adress | Byte | SHA-256 |
| --- | ---: | ---: | --- |
| Bootloader | `0x1000` | 17536 | `3D234A7471F67B013686DABD4DEE7C1FA915C9928463616A94BC9297ACF1ABF8` |
| Partitioner | `0x8000` | 3072 | `0A8B5720E7B77FF11F1462458C3A509DEE79224E5279898F26D6A2E3AE0517B7` |
| `boot_app0` | `0xe000` | 8192 | `F94C5D786A7A8FAB06AC5D10E33BF37711A6697636DC037559EA19CC410A17F0` |
| App | `0x10000` | 926432 | `6A5366C1E56E1137AEBC08E6675CBB12E1A49AE106D2DBD03B30132C6A7D2302` |

De tre startsegmenten är byteidentiska med app-v1.2. Partitionstabellens MD5 är giltig; `app0` börjar vid `0x10000`, är 1920 KiB och rymmer appen. NVS ligger vid `0x9000` med längd `0x5000`. Esptool `image-info` visade giltig checksumma och valideringshash för app och bootloader. Båda firmwarefilerna har separata `.sha256`-filer.

**Fullbilden är fil-/segmentverifierad och har inte flashats från `0x0`.** Appdelen är fysiskt provad efter app-only-flash vid `0x10000` 2026-10-06; NVS bevarades då. Fullbildens `0xff`-mellanrum skriver över NVS. App-only bevarar NVS när den befintliga layouten är kompatibel.

## Windows companion

`BongoDeskSpotify-app-v1.3-2026-10-07.exe`: 19299418 byte, SHA-256 `5609B99DAA1321ECB78B6384F1D5271DB23DBBF1BD6A2E2BBB49D6FD7AFEFD1D`. Byggd separat med ordinarie `BongoDeskSpotify.spec`, PyInstaller 6.22.3 och Python 3.10.11.

Arkivkontrollen jämförde kodobjekten för `config`, `engine`, `media_bridge`, `spotify_api` och `diagnostics` med kompilerad källa. Båda UI-skripten, `ui/bongo.png` och `default_config.json` matchar källan byteidentiskt. Inga personliga config-, backup- eller OAuth-tokenresurser paketerades. UI:t är samma som i tidigare provade `18465D92…`; endast baudstandarderna kräver det nya EXE-bygget. Releasefilen och dess sidecar är skapade efter Leads installationsprov och är byteidentiska med kandidaten i `dist/app-v1.3-2026-10-07-candidate/` och hashidentiska med installerad EXE enligt Leads kontroll.

## Releasebyggets installationsprov 2026-10-07

Lead installerade exakt `5609B99D…` på ordinarie `%LOCALAPPDATA%/BongoDesk/BongoDeskSpotify.exe` och kontrollerade dess SHA-256. Föregående visuellt provade `18465D92…` sparades som hashverifierad `BongoDeskSpotify.backup-20261007-app-v1.3-18465D92.exe`; config sparades som `%APPDATA%/BongoCat/config.pre-app-v1.3-20261007.json`. Före/efter-kontrollen visade byteidentisk config och oförändrad Windows Run-post. Den befintliga profilen använde redan 230400. Ingen firmwareflash gjordes.

Två normala processer startade kl. 11:49:04/14 (Stockholm), `APP_START` 11:49:15.307, serialanslutning på första försöket 11:49:17.464 och art2-handskakning 11:49:20.756. Naturlig uppspelning gav `MEDIA_TRACK seq1` 11:49:20.960, `ART_READY/QUEUED` för 37632 byte, försök 1, 11:49:21.047/48. `ART_SENT duration_ms=4859 protocol=art2 frames_per_write=2` kom 11:49:25.916 och lyckad `ART_ACK` 11:49:25.950, 34 ms senare. Ingen avvisning eller retry i denna överföring. Färsk status 11:49:50 visade ansluten ESP32, statusålder 1,71 s, heap 182352/min179320 byte, Spotify redo via `spotify_api` och effektivt Connect 15,0 s.

Detta är installations-, kontakt- och sändnings/kvittenskontroll. Ingen ny visuell UI-genomgång eller separat visuell omslagsbedömning gjordes; UI-resurserna är byteidentiska med den redan visuellt provade versionen. Äldre fysiska observationer redovisas separat nedan.

## Fysisk och syntetisk evidens

- **Exakt firmware 6A53, companion 41BE, 2026-10-06:** minst fem art2-överföringar lyckades på första försöket på 4968–5563 ms, med ACK 8–35 ms efter sändning. Användaren såg rätt omslag efter cirka fem sekunder vid tre byten och jämn text/skiva under laddningen. Två snabba NEXT gav rätt sista låt/omslag utan äldre återkomst; gamla överföringar avbröts. Paus/fortsätt, DJ, långtrycksmeny, Fokus och touch under laddning bekräftades fungera. Ingen ny Spotify-429 observerades.
- **Samma firmware, companion 41BE, 2026-10-07:** användaren rapporterade att sömn/väckning verkar fungera. Kvalitativ observation, utan exakta tider, ström eller fullständig kontroll av ljusblixtar.
- **Samma firmware, UI-companion 18465, 2026-10-07:** tray-öppning, sidbyte och Avancerat provades. Sparat Connect 20 s blev effektivt 20 s utan omstart, sedan återställt till sparat 15/effektivt 15,0. Oägda inställningar och Windows-start bevarades semantiskt. Naturlig omslagsöverföring tog 5000 ms med lyckad ACK 7 ms senare; ingen separat visuell omslagsbedömning gjordes i UI-provet.
- **UI-fixturer:** 546 isolerade kontroller och native förhandsbilder med syntetiska data. 150 % är layoutstress, inte faktisk DPI-/monitorväxling. Verklig skärmläsare, mänsklig tangentbordsgenomgång och diagnostikåtgärdernas hårdvarubesked är inte separat provade.

Återstående mätningar omfattar exakta släcknings-/väcktider och deep-sleep-ström, framtvingad 6A53-felåterhämtning samt samma låt/omslag efter ny verklig API-spärr utan lokal Windows-session. Äldre backoffprov gäller den tidigare felande firmwaren. Begränsningarna är dokumenterade och skapar inga nya, oombedda releasekrav.

## Kort fortsatt fysiskt prov

1. Låt aktiv companion gå minst elva minuter utan datorinmatning: skärmen ska vara kvar. Stäng sedan companionen och kontrollera släckning efter tio minuter och inga blixtar under mörka kontrollvakningar.
2. Prova både shutdown/power-on och Windows sleep/resume medan USB-porten behåller ström. Starta/återuppta companionen, mät till normal bild och kontrollera att portkontakten återkommer.
3. Kontrollera aktuell tid/statistik, samma låt och omslag efter väckning, meny, panelbyte, Fokus/TIDER, bonk, mediagester och DJ. Mät ström separat om faktisk deep-sleep-förbrukning ska bekräftas.

## Slutkontroll av releaseunderlag

Versionsfilernas storlek/hash och samtliga tre sidecars matchar. Lokala Markdown-länkar till releasefilerna kontrollerades. `git diff --check` och kontroll av staged scope passerade före lokal releasecommit. Äldre releasefiler och firmwarekällor är oförändrade.

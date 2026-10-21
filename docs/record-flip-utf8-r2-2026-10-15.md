# Skivflip och åäö – slutkandidat r2, 2026-10-15

## Status

**Byggd, verifierad och källfryst; inte startad, installerad eller flashad.** Denna r2 ersätter 09305A29 som rekommenderad byggkandidat efter en konkret resync-rättning. [Första rapporten](record-flip-utf8-2026-10-15.md), dess kandidat/snapshot/manifester och F0AA-förhandsbilder är orörda historiska underlag. Allt arbete sker i `D:\DEV\Ai\Github\Bongo-Cat-Screen` från Git-bas `83cc460b6e3a651f862db9aff1577f40b683bac0`. Ingen commit, push, tagg eller release gjord.

**Installerat är fortsatt 17466/F406 med 5 s aktivt daggrundintervall.** Den nya firmwarekandidaten innehåller även tidigare seek-stöd, som fortfarande är **inte flashat, inte skärmprovat och inte fysiskt accepterat**. Hela målet med svenska tecken kräver det matchande nya paret nedan; F406 är inte UTF-8-/glyphprovat med den nya companionen. Inga riktiga profiler, tokens, API-anrop eller taktändringar ingick.

## Exakt slutpar och spårbarhet

| Del | Bytes / sökväg / SHA-256 |
| --- | --- |
| Ny firmwareapp | **932720 byte**, `.pio/candidates/record-flip-utf8-r2-C7E594B4.bin` |
| Firmware SHA-256 | **`C7E594B462D0025B1BE00BFE70C535153326E18DCE4CA29017B4D84712AD7DFB`** |
| Återanvänd UTF-8-companion | **19657256 byte**, `dist/companion-2026-10-15-record-flip-utf8-dev/BongoDeskSpotify.exe` |
| Companion SHA-256 | **`0D397F89DCBC5C6B648517268A08B1D4E9DBEF23B7BAFD9B51816EBE77850ADD`** |
| Ny källsnapshot | **153 filer**, `build/record-flip-2026-10-15-r2/source-frozen/` |
| Källmanifest | `build/record-flip-2026-10-15-r2/source-frozen.json`, **`B271864571183D716170D8C8BA2F1748AD1EFF2FA3385B0948616BE7F46D09D4`** |
| Kandidatmanifest | `build/record-flip-2026-10-15-r2/candidate.json`, **`4593736B18EA09FBD032B83477AA10D4C87C0E07E4991E96C24581BEC2501F86`** |
| Slutpreviewmanifest | `visuals/record-flip-2026-10-15/final/manifest.json`, **`89243538B8C3D26D085DDFB756EE85ABF8C0AE55F81A48B14B5B706F61F3C511`** |

Companion 0D397F89 är exakt samma byteverifierade EXE som i första byggsteget; den byggdes inte om för r2 och har aldrig startats. Ny firmware ligger separat från 09305A29 och seek 57894EE0. Normal serial är fortsatt 230400; firmware är en appbild för kompatibel layout vid `0x10000`. Ingen flashning eller ny fullbild är beställd.

## Det rättade resyncfallet

En låt kan först rapportera okänd längd och sedan få korrekt längd, utan att låtnyckel, titel eller artist ändras. Engine skickar då MEDIA_TIME men ingen ny DEFAULT/SEEK_CONTEXT. Första implementationens fliprevision räknades ändå upp för längden, vilket kunde ge en onödig flip vid senare oförändrad resync.

R2 tar bort **endast längden ur skivans identitetsrevision**. Seekens separata `media_context_revision` räknas fortfarande upp, så en pågående gest behåller sitt skydd mot ändrad kontext. Ett faktiskt nytt kontext-ID med identisk titel/artist startar fortsatt en flip. Ingen renderingsgeometri, glyph, palett eller rörelse ändrades.

Två körbara beteendeprov visar kedjan: verklig engine med 0→180 s på samma låt skickar bara tidsändringen; verklig firmware-durationgren exekveras i native-fixturen, ökar seekrevisionen till 1, och samma kontext 101 följd av resync behåller hel ART utan flip. Ny kontext 102 startar däremot flip. Detta kompletterar de tidigare snabba bytes-/cache-/reconnect-proven.

## Lokal rörelse, bilder och buffertägarskap

En normal flip är **280 ms**, med tidsstyrd cosinuslik höjd i **20 ms-steg**: cirkel → tunn horisontell ellips/kant → rättvänd ny sida. Gammalt omslag går till befintlig generisk vinyl; komplett giltigt nytt omslag går från generisk till nytt omslag. Vanlig rotationsvinkel fryses och återupptas bara när musik spelar. Befintliga 172/144 px viewports, Fokus, gester, progress och meny bevaras.

LVGL 8.3.11 har endast gemensam bildzoom/planrotation för denna väg. En separat 112×112 RGB565-projektionsyta ger därför den lodräta kompressionen utan ny tråd, beroende eller blockerande animationsslinga. Högst en begränsad frame beräknas per nytt steg; missade steg hoppas över. Se [LVGL image](https://docs.lvgl.io/8.3/widgets/core/img.html) och [canvas/buffertar](https://docs.lvgl.io/8.3/widgets/core/canvas.html) samt första rapportens teknikbeskrivning.

LVGL/UI ligger kvar på core 1. Core 0, art2/CRC/chunkordning och ACK-protokoll ändras inte. Aktiv slot byts och ACK skickas innan någon animationsframe ritas. Ingen gammal bildpekare hålls mellan frames. Nästa BEGIN får den gamla aktiva slotten; animatören läser endast den nya committade slotten. Generisk/projicerad bild skriver aldrig i aktiv eller mottagande transportbuffer.

Senaste giltiga mål vinner i ett enda tillstånd, utan växande kö. En komplett bild mitt i utgående flip kan öppnas direkt från kanten; nytt låtbyte under inkommande flip avbryter till generisk. Det är avsiktligt coalescade/avbrutna förlopp, **inte en full 280 ms-animation för varje snabb signal**. Saknat/felaktigt omslag lämnar vanlig generisk vinyl utan väntanimation. Reconnect/fullsynk/cache på samma identitet ger ingen ny flip.

DJ/menu/annan panel och ändrad kompakt Fokus-layout avslutar till korrekt helt slutläge. DJ ritar hela sin canvas innan den visas. Återkomst till Spelare visar senaste beslutade bild, utan kvarhängande halvskiva.

## Minne och prestandagräns

| Slutbygge | Resultat |
| --- | --- |
| Firmwaremiljö och separat mapp | `esp32-024r-spotify-fastserial`, `build/record-flip-2026-10-15-r2/firmware/`; **PASS 91,088 s** |
| Statisk RAM | **112216/327680 byte**, +120 mot 83cc460/seek-basens 112096 |
| Bygg-flash | **931989/1966080 byte**, +2736 mot samma bas |
| Engångsheap | **25088 byte** intern 8-bitarsheap, utöver statiska tal |
| Ren state-helper | **20 byte**, ingen kö/heap/transportpekare |

Den första statiska 25088-byteytan överskred DRAM-länksegmentet med 12720 byte och ingår inte i slutbygget. Nu görs ett enda bevakat allokeringsförsök vid skärmskapandet, aldrig på frames, metadata, panelbyte eller resize. Vid OOM sker direkt bildbyte utan flip/väntan. Generisk reserv ritas i 56×56 av befintliga 64×64 DJ-scratch, endast när DJ är dold; dubbel zoom bevarar storleken med grövre raster. Hela DJ-canvasen fylls/ritas om före synlighet. Inga transportbuffertar berörs, och ingen bild läses samtidigt av LVGL på en annan core.

Tvingad OOM körs med verklig allokeringsfunktion i native-fixturen och provar att två anrop bara ger ett försök. Reducerytan provas med kapacitetsgräns/canarypixlar. Historiska cirka 180 kB friheap garanterar inte sammanhängande block eller ny minheap. **Fysisk framekostnad, jämnhet, största heapblock/minheap och TFT/serial/touch under belastning väntar.** Befintliga TFT_WIDTH/TFT_HEIGHT-varningar kvarstår; slutbygget har inga fel.

## Svenska tecken genom hela kedjan

- Faktisk `engine._clean_media_text` använder NFC, bevarar **åäöÅÄÖ**, sätter ihop dekomponerade tecken och behåller tidigare ASCII-fallback för andra ostödda tecken.
- Radbrytningar blir mellanslag, kontrolltecken tas bort och `|` blir `/`. 72 tecken per titel/artist ger högst 157 byte före LF, inom den oförändrade 256-byteframern.
- Medietextpayloaden skickas som UTF-8. Kommandon, numerik, art2/base64, trafiktakt och API-budget ändras inte. Riktig C++-framer provas bytevis, inklusive fragmentering, overflow och återhämtning.
- Riktiga rullande titel-/artistfält använder sex små 4bpp-glyfer vardera för Montserrat 16/14, härledda ur befintliga bitmaps. Baseline, advance och storlek behålls; ASCII/symboler går via originalfontens fallback.
- DJ/kompakt Spelare använder samma riktiga namn/fonter. Övriga fonter/geometri ändras inte. `tools/generate_media_swedish_font.py` reproducerar tilläggen utan ny fontkonverterarinstallation.

## Verifiering

**188 upptäckta: 186 PASS, två befintliga C++ SKIP**, 24,516 s; noll fel och noll externa anslutningsförsök. Isolerad profil/temp och loggar ligger under `build/record-flip-2026-10-15-r2/`. Ingen riktig profil/API används.

- **15 flip-/nativeprov:** riktig C++-helper/projektion samt faktiska firmwarefunktioner för activation/default/allokering och durationgren under minimala LVGL/TX-adaptrar. 280 ms, snabba byten, senaste slot, omedelbar ACK före frame, gamla slotten överskriven efter ny BEGIN, inga generic-skrivningar i transportbuffertar, dubbletter, kontextbyte, panel/DJ/resize, OOM-gräns/ingen retry och millis-wrap.
- **Fem text-/glyphprov:** faktisk enginepayload→riktig C++-framer, NFC/NFD, Dö ung/Hov1/åäöÅÄÖ, kontroller, fallback, bytegräns, overflow/recovery, verklig glyphdata/fontkoppling och samma låts längdkorrigering utan nytt track-paket.
- Nytt manifestprov kräver att slutpreviewns källhashar och 20 PNG/GIF-hashar matchar. Historiska previewprov använder 83cc460-Gitblobbar med LF/CRLF-hantering och byteverifierade pinnade fontfiler; inga gamla previews/manifester regenereras.
- Befintliga API-budget-/Retry-/manual-/control-confirm-/Windows-/seek-/art2-/serial-resume-/Fokusregressioner passerar.
- `test_cpp_state_cache_and_ui_calls` och `test_cpp_actual_touch_handler_and_media_dispatch` är fortfarande **SKIP** på grund av ofullständig lokal MSVC/headers. Den befintliga kompilatorn kan köra de nya fristående helperfixturerna utan CRT/SDK-reparation; det innebär inte att dessa två fulla körprov exekverades.
- Hela firmware inklusive riktiga LVGL-fonttyper/callbackkopplingar är kompilerad/länkad. Full LVGL/TFT-rendering, verklig UTF-8 på enheten och fysisk touchdispatch är inte exekverade här.
- Exakt återanvänd companion 0D397F89 är åter paketverifierad skrivskyddat: **11 moduler, fyra resurser, Stockholm-tzdata** matchar aktuell källa. API-budget, Spotify-klient, media_bridge och standardkonfig är bevarade med 5 s aktiv daggrund. EXE:n startades inte.
- **1141 historiska filer** bevarade, inklusive tidigare 09305/F0AA/153-snapshot/5099-manifest/första rapport/0D397 och äldre kandidater, rapporter, kopior och releases. Alla 153 nya snapshotfiler jämförs mot både aktuell källa och kopia.

## Slutbilder och UI-granskning

Slutunderlaget ligger endast i [visuals/record-flip-2026-10-15/final](../visuals/record-flip-2026-10-15/final/), med manifest **`89243538B8C3D26D085DDFB756EE85ABF8C0AE55F81A48B14B5B706F61F3C511`**. Alla **20 outputhashar är byteidentiska** med tidigare visuellt godkänt F0AA9837…-underlag. Fyra av åtta källhashar ändrades: firmware-durationgrenen, de två native-fixturefilerna och generatorns nya slutmappsval. Renderer/helper/glyphdata är oförändrade.

Normal/kompakt, snabb följd, riktig musikpaus, separat DJ-/Fokus-/panelavbrott, OOM, långa rullande namn med 204 px-klipp/tre mellanslags cirkulär kopia, glyphark och rena slutbilder ingår. Frames/state körs från riktig C++, text från riktiga firmwarebitmaps. Endast syntetiska omslag/texter och tillåtna Dö ung/Hov1 används. Fryst nollgradig planvinkel gör rörelsen tydlig; GIF-tid är inte uppmätt ESP32-fps.

**UI har nu fokuserat godkänt exakt slutmanifest 89243538B8C3D26D085DDFB756EE85ABF8C0AE55F81A48B14B5B706F61F3C511**, utan blockerande visuella avvikelser. UI verifierade 8/8 källhashar, 20/20 outputhashar och byteidentitet med F0AA, samt läste durationrättningen. Det tidigare F0AA-godkännandet och dess underlag bevaras separat. Detta är visuell simulationsgranskning, inte fysisk skärm-/prestandaacceptans.

Projektledarens oberoende slutkontroll passerade: 153 aktuella + 153 frysta källhashar, 1141 historiska filer, båda kandidatfiler och samtliga ovan angivna manifesthashar. Lead läste även r2-loggen med 188/186 PASS/2 SKIP, noll fel/externförsök. Paketets elva moduler/fyra resurser/tzdata var redan oberoende verifierade och engine/0D397F89 är oförändrade därefter. Installerad companion är fortsatt exakt 17466; den nya EXE:n har inte körts.

## Ändrade filer

Befintliga: `companion/engine.py`, `src/bongo_cat_featured.inc`, `tests/focus_countdown_test.cpp`, `tests/test_focus_countdown.py`. Nya: `src/media_record_flip.h`, `src/media_swedish_font.h`, `tests/record_flip_host.cpp`, `tests/record_flip_host.py`, `tests/test_record_flip.py`, `tests/test_media_text_utf8.py`, `tools/generate_media_swedish_font.py`, `tools/record_flip_visuals.py`, nya daterade rapporter och underlag endast i den nya record-flip-visualsmappen. Tidigare publicerade releasefiler och frysta underlag är orörda. Inget är stageat/committat i detta featuresteg.

## Kort senare skärmprov – allt nedan väntar

Efter separat uttryckligt godkännande för det nya paret:

1. Dö ung/Hov1 och åäöÅÄÖ i kort/lång titel/artist, båda rullkanterna och cirkulär omslutning, i normal/kompakt/DJ-vy.
2. Spelande/pausat: gammal→generisk→ny sida, fryst rotationsvinkel under flip och återupptagning bara vid spelande. Saknat/ogiltigt omslag lämnar generisk skiva.
3. Snabba byten/nytt omslag under utgående rörelse: senaste bild, omedelbar ACK, korrekt art2 och responsiv touch utan halvbilder.
4. DJ in/ut, meny/panel, Fokus-layout mitt i flip samt befintliga gester/Fokus-touch/progress. Seek behåller separat uppskjuten fysisk acceptans.
5. Samma låt med okänd→känd längd och senare resync/cache/reconnect/reset: ingen onödig flip. Faktisk ny låtnyckel med lika text ska fortfarande växla.
6. Sleep/resume, mörka timerväckningar och återställt UI/omslag utan ljusblixt. Detta är inte provat på det nya paret.
7. Mät framekostnad, minheap/största block och serial/art2 under belastning. OOM-logik är hostprovad, ingen riktig lågminnessituation har framtvingats.


# Integrerad Fokus-status UI3 – kandidat 2026-10-12

## Status och avgränsning

**Implementerad, byggverifierad och fryst. Player och provade funktioner är fysiskt godkända; Bongos stil blockerar slutacceptans.**
Designen följer Leads godkända
[UI3-specifikation](../visuals/focus-countdown/ui-integrated-2026-10-12/SPEC.md).
Förhandsbilderna nedan är simulationer från aktuell källkod och verkliga
LVGL-glypher; de är inte fotografier eller fysisk verifiering.

Lead har flashat exakt denna kandidat som app vid `0x10000`/115200.
Kodskrivaren har inte flashat. Uppstart och seriell kontakt är verifierade
hos Lead. Användaren har godkänt Player och de hittills provade
funktionerna, inklusive pausfas/avslut och återställd fullstor cirkel.
Bongos stil är enda UI-blockeraren. Art2-/heap-insamlingen för 08A är
avslutad; dess data är historik inför kommande Bongo- och touchändring.
Ingen companionkontroll, installation, commit eller release har gjorts här.
Alla tidigare fysiska resultat gäller tidigare binärer och överförs inte
till UI3. Den sena bekräftelsen om Spotify-väntestatus är ingen UI3-kontroll.

## Implementerad presentation

| Del | Absolut ruta x,y,bredd,höjd | Stil |
| --- | --- | --- |
| Bongo fas | 139,42,80,17 | Unscii 16, vänster, `505860` |
| Bongo tid | 139,63,96,17 | Unscii 16, höger, `40484F` |
| Bongo pausstreck | 224/230,45,3,11 | `505860`, bara vid fryst timer |
| Avskiljare | 135,42,1,38 | `D5D9DE` |
| Bongo kompakt FocusDone | 139,60,96,2 | Understrykning i temaaccent |
| Spelare statuspanel | 40,20,160,26 | Radie 10, `15191E`, kant `292E35` 1 px, padding 0 |
| Spelare fas | 52,25,52,16 | Vanlig Montserrat 14, centrerad, temaaccent |
| Spelare tid | 112,24,56,18 | Vanlig Montserrat 16, centrerad, `F2F4F7` |
| Spelare pausstreck | 176/182,28,3,10 | `F2F4F7`, bara vid fryst timer |

Spelarens barn har relativa positioner 11,4 / 71,3 / 135/141,7.
LVGL 8.3.11 lägger till förälderns 1 px kant, vilket ger de absoluta
positionerna ovan. Exportern räknar med samma kant.

Fasnamnet är `FOKUS` eller `PAUS`; paus visas med separata staplar.
Klocka, CPU/RAM/WPM, Bongo-canvas, låtpanel och progress är kvar på samma
platser. Kontrollerna skyddar hela Bongo-canvasen från y82, samt CPU/RAM
100 % och WPM 200. Alla tillåtna tidsvärden upp till 120/30 minuter ryms:
maximal fas/tid är 80/96 px på Bongo och 51/54 px på Spelare.

| Omslag / DJ | Synlig Fokus-status | Dold Fokus-status |
| --- | --- | --- |
| Cirkel | 48,54,144,144, radie 72 | 34,26,172,172, radie 86 |
| RGB-zoom | 320, 112→140 px | 384, 112→168 px |
| DJ-zoom | 560, 64→140 px | 672, 64→168 px |

`refreshFocusMediaLayout()` ändrar position, storlek, radie, zoom och
centrering endast när statusens synlighet ändras. Nytt omslag använder
aktuell zoom i `activateMediaArtwork()`; DJ-byte återanvänder redan korrekt
canvas och bild. Samma 112×112-buffertar, descriptor, CRC, kvittens,
bildcache, serialprotokoll och panelgester bevaras.

Kompakt FocusDone på Bongo/Spelare använder den integrerade markeringen;
den gamla fristående PAUS-badgen är dold samtidigt. Spelarens kort får
`focusDarkAccentHex()`/`focusAccentHex()` som bakgrund/kant. Fas och tid
flyttas inte. Stora notiser, andra panelers notiser, livstid, kvittering
och LED använder samma befintliga cue-state. Byte av panel eller
kvittering återställer markeringen genom befintligt cue-flöde.

Lokal `focus_state`, avrundning uppåt till sekund och cache bevaras.
Faslabel skrivs endast vid fas/synlighetsbyte, tid endast vid ändrad
visad sekund/synlighet, staplar endast vid paus/synlighetsbyte. De fyra
labelobjekten delar en livslång 12-byte tidsbuffert och konstanta fasnamn.
Alla 11 nya UI-objekt skapas en gång och är inerta. Idle, Prepared och
Completed döljer statusen och återställer Spelarens cirkel.
Ingen ny timer, seriell trafik eller companionkod tillkommer.
UI2:s numeriska fontwrapper och Unscii 8 behövs inte längre; deras äldre
källor finns kvar i de frysta baslinjerna. `lv_conf.h` matchar åter HEAD.

## Fryst app och manifest

| Fält | Värde |
| --- | --- |
| Arbetsyta | `D:\DEV\Ai\Github\Bongo-Cat-Screen` |
| Miljö | `esp32-024r-spotify-fastserial` |
| App | `.pio/candidates/focus-countdown-ui3-08A78748.bin` |
| Storlek | 928528 byte |
| SHA-256 | `08A78748E4FE7ED4A99F9496DFC089680AAEB34BA5C36A58AEDC8285CB8E8D7A` |
| Byggtid | 56,505 s |
| Statisk bygg-RAM | 112080 / 327680 byte, 34,2 % |
| Bygg-flash | 927793 / 1966080 byte, 47,2 % |
| Drift / appflash | 230400 / 115200 baud, appadress `0x10000` |
| Kandidat- och källmanifest | `build/focus-countdown-ui3-2026-10-12/candidate.json` |
| UI2-baslinje före UI3 | `build/focus-countdown-ui3-2026-10-12/baseline/manifest.json` |

### Verifierad appflash hos Lead

Efter användarens ”Sure håller” kontrollerade Lead åter kandidatens
SHA-256 och storlek och skrev exakt 08A78748 till COM6 vid `0x10000`,
115200 baud med esptool 4.9.0, `before/after no_reset`.
Resultat: 928528 byte (428437 komprimerade) skrivna på 38,0 sekunder,
`Hash of data verified`, exit 0. Endast appområdet skrevs; NVS-området
är orört. Bara processer med exakt den installerade companionens
executable-sökväg stoppades före skrivningen.

Enheten stannade först i bootloadern. Lead bad användaren släppa BOOT
när stubben körde. Användaren bekräftade därefter RESET/EN med ”start”;
uppstarten redovisas nedan. Flashningen ensam verifierar inte UI,
funktion eller omslagsöverföring på 08A78748.

### Uppstart och första färska data, 2026-10-12

Lead startade installerad companion 68CC5BC1 dolt med `--startup`
kl. 18:15:54.478 (PID 34916). `APP_START` kom 18:15:55.660.
Första `serial_open` misslyckades 18:15:57.828; återförsöket lyckades
18:16:01.987. `ART_CAPABILITY` bekräftade art2 18:16:14.530.
Tiderna är lokal tid i Stockholm.

| Färsk status | Uptime | Ansluten | Fri heap | Minsta heap | Total heap |
| --- | --- | --- | --- | --- | --- |
| 18:16:15.327 | 14 s | Ja | 179876 | 179072 | 261504 |
| 18:16:16.345 | 19 s | Ja | 179876 | 179072 | 261504 |

Detta verifierar uppstart, återförsök till seriell kontakt och aktuella
skärmdata. Värdena är uppstartsdata; de är inte en färdig art2-/heap-
jämförelse eller en mätning av enbart UI3:s minneskostnad.
Lead startade en separat, skrivskyddad 600-sekunders insamling omkring
18:15:54 (PTY 64934), med kontroll av filfärskhet, uptime under 120 s vid
inledningen och statusålder under 8 s. Äldre stale-data tas inte med.
Insamlingen är nu avslutad med exit 0; slutresultatet redovisas nedan.

Uppstartens äldre överföring 18:16:05.301–18:16:14.485, duration 9188 ms,
och nästa queued 18:16:14.494 utesluts från art2-jämförelsen.
Art2-förmåga är påvisad; första jämförbara art2-överföringen och
användarens senare återkoppling för 08A78748 redovisas nedan.

### Avslutade art2-/heap-efterdata för 08A78748

Fyra färska art2-överföringar finns i den avslutade 600-sekunderssamplern
PTY 64934 (exit 0). Tiderna är 2026-10-12, Stockholm; duration är loggens
rapporterade värde, ACK-fördröjning räknas från sent. Uppstartens
legacy-överföringar ovan är uteslutna.

| Queued | Sent | Duration | Lyckad ACK | ACK efter sent |
| --- | --- | --- | --- | --- |
| 18:18:01.923 | 18:18:07.250 | 5328 ms | 18:18:07.299 | 49 ms |
| 18:18:52.412 | 18:18:57.652 | 5250 ms | 18:18:57.683 | 31 ms |
| 18:20:14.646 | 18:20:19.872 | 5234 ms | 18:20:19.879 | 7 ms |
| 18:23:14.396 | 18:23:19.542 | 5155 ms | 18:23:19.558 | 16 ms |

| Sample, 2026-10-12 Stockholm | Läge | Uptime | Fri heap | Minsta heap | Total heap |
| --- | --- | --- | --- | --- | --- |
| 18:18:02.3383196 | Under art2-överföringen | 124 s | 179688 | 176004 | 261488 |
| 18:18:56.8128836 | Under andra art2 | 179 s | 179684 | 176004 | 261488 |
| 18:20:17.5052709 | Under tredje art2 | 259 s | 179692 | 176004 | 261488 |
| 18:23:17.9535329 | Under fjärde art2 | 440 s | 179696 | 176004 | 261488 |

Alla samtidiga prover ovan är anslutna. Senare output 18:18:31.592
hade fri 179688 / minsta 176004 / total 261488, uptime 154 s.
Stabila slutprover från 18:23:57.285 till 18:25:53.3395374 hade exakt
fri 179680 / minsta 176004 / total 261488; sista uptime var 595 s och
anslutning true. Lägsta **samplade fria** heap under hela insamlingen var
179500 byte. Det är ett annat mått än minimum sedan boot, 176004 byte.

NEXT success 18:18:51.491 föregick andra överföringen. PLAY_PAUSE success
18:23:18.513 kom under fjärde överföringen; separata success finns även
18:22:49.607, 18:22:50.977 och 18:23:23.550. Detta är normal mediestyrning
i loggen, **inte** Fokus-status-tap; den funktionen finns ännu inte i 08A.

| Jämförelse | Före, 6A5366C1 | Efter, 08A78748 |
| --- | --- | --- |
| Fyra art2-durationer | 5030–5188 ms | 5155–5328 ms |
| Samtidig fri heap | 182288–182296 | Senare tre: 179684–179696 |
| Minsta heap sedan boot | 178456 | 176004 |
| Stabil fri heap efter | Referens 182288 | 179680 |

Senare samtidig fri heap är 2592–2612 byte lägre inom dessa intervall;
stabilt eftervärde är 2608 byte lägre än referensen 182288.
Minimum sedan boot är 2452 byte lägre. Arbetsmoment och uptime skiljer
sig: detta isolerar inte labelkostnad och bevisar inte läckage eller
en exakt prestanda-/FPS-förändring. Användarsvaren styrker upplevd
jämnhet under omslagsöverföring.

Detta är avslutade efterdata från den frysta 08A-versionen.
Värdena kan inte användas som slutmätning för en framtida Bongo- och
Fokus-status-tap-kandidat, som behöver egna mätningar.
Ingen CPU-, FPS- eller exakt touchlatensmätning har gjorts.

### Användarens fysiska återkoppling på 08A78748

| Gate | Bedömning |
| --- | --- |
| Player: stil, placering och läsbarhet | **Godkänd**, användaren säger ”ser bra ut” |
| Bongo: blockering av befintligt innehåll | Ingen blockering rapporterad: ”Inget täcks” |
| Bongo: visuell stil | **Blockerare**: användaren tycker inte att statusen matchar startsidans stil |
| Timer paus/fortsätt, NEXT/rätt omslag omkring 5 s | Godkända enligt samlat användarsvar ”Ja allt är rätt” |
| Text/skiva/touch, DJ-svep och långtryck | Godkända enligt samma samlade användarsvar |
| Mindre cirkel under aktivt Fokus | Godkänd enligt samma svar; ingen fysisk pixelmätning |
| Fokus→PAUS/rätt tid på båda vyerna, pausad paustimer och fortsätt | Godkända enligt samlat svar ”Ja” på Leads följdfråga |
| Completed och Nollställ: status dold, omslag/DJ tillbaka till större 172 px-layout | Godkända enligt samma samlade svar; ingen fysisk pixelmätning |

Detta är kvalitativ återkoppling för den nya kandidaten, inte separata
instrumenterade delprov. Användarens senare ”Ja” gäller hela Leads
frågeflöde om fasbyte, pausad paustimer/fortsätt, Completed och Nollställ
med dold status och återställd omslags-/DJ-storlek. Funktionella gates
i dessa frågor är därmed gröna på 08A78748. Lead har valt en avgränsad Bongo-anpassning till
befintlig svart pixelstil och beställt en ny Bongo-spec från UI-chatten.
Player ändras inte i det uppdraget. Ingen ny design är implementerad här;
08A-källan och binären förblir frysta i väntan på specifikationen.
Användaren har även beställt lokal paus/fortsätt genom korttryck på
synlig Fokus-status på Bongo och Player, med bevarade vanliga gester.
Detta kommande uppdrag är ännu inte implementerat eller testat på 08A.

Bygg-RAM är 40 byte och bygg-flash 800 byte lägre än UI2/8BB91836.
Detta säger inget om fri/minsta heap i drift: UI3 har fler LVGL-objekt och
måste få egna runtime-mätningar under omslagsöverföring och fasbyte.
Befintliga TFT_WIDTH/TFT_HEIGHT-omdefinitionsvarningar kvarstår i bygget.

## Verifiering

| Kontroll | Resultat |
| --- | --- |
| Firmwarebuild fastserial | PASS |
| Python: verkliga fonter, alla tidsvärden, mått/parent-insets | PASS |
| Python: negativa kontroller för statistik/canvas/card-kollision | PASS |
| Python: 22 bilders dimensioner/hash och aktuella källhashar | PASS |
| Python: omslags-/DJ-zoomvägar, layoutguard och integrerad cue-väg | PASS |
| Host-C++: stateful cache och verkliga UI-adaptrar med recorder | **SKIP**, ofullständig lokal MSVC/setup/includes; inte körd |
| Xtensa C++14, `-Wall -Wextra -Werror` | PASS; 10 static_assert-grupper och verkliga adapterfunktioner kompilerar |
| `git diff --check` | PASS, inga whitespacefel; äldre LF/CRLF-notis i `companion/settings-view.ps1` |

Det kompilerade C++-provet innehåller cache/sekundgränser, paused/running,
Idle/Prepared/Completed, layout/zoom endast vid synlighetsbyte, nytt
omslag, DJ-byte, cue/panelbyte och återställning. Dessa stateful
recorder-kontroller har **inte exekverats** i den ofullständiga hostmiljön.
De tio `static_assert`-grupperna utvärderas däremot vid kompilering.
Pythonkontrollerna exekverar font-/geometrivalidering och granskar de
faktiska firmwarevägarna; de ersätter inte ett fysiskt LVGL-prov.

[Normal Bongo](../visuals/focus-countdown/ui3-implemented-2026-10-12/composed/bongo_focus.png),
[normal Spelare](../visuals/focus-countdown/ui3-implemented-2026-10-12/composed/player_focus.png)
och 20 ytterligare tillstånd finns i den separata UI3-mappen, inklusive
120:00/pausad, båda faserna, kompakt cue/pausad cue, idle, aktiv/inaktiv
DJ och cyan. [Bildmanifestet](../visuals/focus-countdown/ui3-implemented-2026-10-12/manifest.json)
anger glyphrutor, färger, zoom och källhashar.
Kodskrivaren har granskat normal-, lång/pausad-, cue-, idle-, DJ- och
cyan-bilder i 240×320. Lead har också granskat de implementerade bilderna.
UI-specialistens slutgranskning är **GODKÄND**: samtliga 22 bilder och
bild-/källhashar matchar. Bongo med maximal statistik och skyddad canvas,
Spelarens fontbredder och insets, aktiv/inaktiv omslags- och DJ-layout
samt cue/cyan är godkända utan designavvikelser. Granskad featured-hash är
`ED54326102FC05D85F82BE7D7483D5F7EE1FFD10217977DE1790DAA6485B4C4D`,
samma källa som den frysta 08A78748-kandidaten. Den godkända UI- och
källgranskningen gäller källhärledda simulationer. Fysisk återkoppling
godkänner Player och provade funktioner, men underkänner Bongos stil
enligt avsnittet ovan. Paus-/avslutsproven är nu samlat bekräftade på
08A78748. Art2-/heap-sammanställningen ovan är nu avslutad för denna
version; Bongo-stilen återstår.

## Fysiskt prov hos Lead – återstående UI3-gates väntande

1. Uppstart/kontakt och Player är godkända enligt ovan. Bongos stil
   blockerar leveransen och har ett separat UI-uppdrag hos Lead.
2. Timer paus/fortsätt samt Fokus→PAUS/rätt tid på båda vyerna och
   pausad paustimer/fortsätt är samlat godkända på 08A78748.
3. Nytt omslag, DJ och mindre aktiv cirkel är godkända. Användaren har
   även samlat bekräftat att Completed och Nollställ döljer statusen
   och återställer omslag/DJ till större 172 px-layout.
4. NEXT, jämn text/skiva/touch, DJ-svep och långtryck är samlat godkända.
   Enkel/dubbel/trippeltap, båda sidsvepen och temaändring är inte
   separat bekräftade i detta 08A-prov.
5. Art2-start/slut/ACK och fri/minsta/total heap med uptime är redovisade
   ovan från denna uppstart, inklusive stabila slutdata och jämförelse
   med 6A. CPU/FPS/latens är omätta. Kommande Bongo-/touchkandidat får
   egna efterdata; 08A-mätningen bevaras som historik.

## Diffomfattning och bevarande

UI3 ändrar `src/bongo_cat_featured.inc`, `src/focus_countdown.h`,
`tools/export_ui_visuals.py`, `tools/focus_countdown_visuals.py`,
`tests/focus_countdown_test.cpp` och `tests/test_focus_countdown.py`.
`src/focus_countdown_layout.h`, denna rapport och den separata UI3-preview-
mappen tillkommer. Den tidigare otrackade fontwrappern är borttagen från
aktiv källa men bevarad i UI2/UI3-baslinjer.

De 15 äldre adaptiva companion-/dokumentfilerna är SHA-verifierat
byteidentiska med `build/focus-countdown-2026-10-12/baseline/manifest.json`.
6A5366C1 (926432 byte), BD666797 (926976 byte) och 8BB91836 (929328 byte)
är hashverifierat bevarade. Båda tidigare rapporterna och baslinjerna är
oförändrade. Äldre releasefiler, companion, Fokus-logik, touchrouting och
serialprotokoll är inte ändrade av UI3.

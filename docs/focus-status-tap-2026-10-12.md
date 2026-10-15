# Bongo fjärde Fokus-rad och status-tryck – kandidat 2026-10-12

## Status

**Implementerad, byggverifierad, fryst och flashad. UI-granskning och
fysisk huvudacceptans godkända på F406C485. Egna art2-/heapdata är avslutade.**
Tre avgränsade hörnfall saknar separata fysiska prov och redovisas nedan.

Designen följer godkända
[Bongo-specifikationen](../visuals/focus-countdown/bongo-native-row-2026-10-12/SPEC.md).
Användaren såg designens normalbild i Lead-chatten och svarade
”Ja, den passar bättre”. Detta är **godkännande av designpreview**,
inte fysisk acceptans av den nya firmwarekandidaten.
Player var fysiskt godkänd på 08A78748 och dess presentation bevaras.
Den nya touchfunktionen och Bongo-raden har därefter fått egen fysisk
huvudacceptans på F406C485 enligt användarsvaren nedan.

Kodskrivaren har inte flashat, styrt companion, gjort commit eller release.
Lead har genomfört appflash vid `0x10000`/115200 och de nya
skärm-/touch-/art2-/heap-proven på samma frysta kandidat.
[08A-rapporten](focus-countdown-ui3-2026-10-12.md), dess färdiga mätningar
och de äldre kandidaterna förblir separat historik.

## Bongo och bevarad Player

| Del | Absolut ruta x,y,bredd,höjd | Stil |
| --- | --- | --- |
| Bongo fas | 5,65,96,17 | `FOKUS:`/`PAUS:`, Unscii 16, svart, vänster |
| Bongo tid | 117,65,96,17 | Samma Unscii 16, svart, vänster |
| Bongo pausstreck | 221/227,69,3,11 | Svarta, bara vid fryst lokal timer |
| Bongo touchyta | 5,62,230,20 | Höger/nederkant exklusiva, ingen synlig ram |
| Player touchyta | 36,16,168,37 | Höger/nederkant exklusiva, ingen synlig ram |

Divider och understrykning är borttagna ur aktiv Bongo-UI. Kompakt
FocusDone använder enbart tillfällig temaaccent på fastexten; tid och
staplar är svarta. Fasfärgen återställs vid cue slut, panelbyte eller
dold status och följer temaändring, inklusive cyan.
Fasnamnen med kolon är två statiska strängar; Players `FOKUS`/`PAUS`
är oförändrade. Samma lokala state, ceil-regel, visningscache, 12-byte
tidsbuffert och engångsskapade objekt används.

Maximala Bongo-fas-/tidsbredder är 96/96 px; Players är fortfarande
51/54 px. Alla tillåtna sekunder upp till 120/30 minuter ryms.
CPU/RAM 100 %, WPM 200, klocka och hela Bongo-canvasen från y82 är
skyddade. Bildkontrollerna bekräftar pixelidentiska skyddade områden.
Den 20 px höga Bongo-touchytan är begränsad av WPM och canvas;
användaren har bekräftat att statusen är lätt att träffa på enheten.

Players elva kompletta förhandsbilder är pixel-/hash-identiska med 08A.
`createMediaScreen`, `refreshFocusMediaLayout`, `activateMediaArtwork`,
`toggleMediaCatMode` och `refreshMediaUi` är källidentiska med 08A.
Statuspanel, standardfonter, cue och aktiv/inaktiv cirkel/zoom är
bevarade: 144 px / RGB320 / DJ560 respektive 172 px / RGB384 / DJ672.
Omslagsbuffertar, descriptor, cache/CRC/kvittens och serialprotokoll
är oförändrade. Inga nya Fokus-kommandon eller companionändringar.

## Central hantering av korttryck

`handleTouchFeature()` är ensam eventägare. Statusobjekten är inerta och
har inga LVGL-clickcallbacks. Vid press registreras om trycket börjar i
en aktiv statusyta på Bongo/Player utanför menyn. Running och Paused i
båda faserna ger en yta; Idle, Prepared och Completed gör det inte.

Korttryck använder befintliga 35–649 ms, draggräns 180 raw units och
befintlig koordinatmappning. Om fingret någon gång lämnar ytan eller
passerar draggränsen avbryts status-trycket även om det återvänder.
Ett sådant drag konsumeras utan bonk/media-tap. Start utanför ytan
följer ordinarie routing. Player-svep prövas först, med oförändrad
420-tröskel och DJ/NEXT/PREVIOUS. Långtryck från status använder samma
650 ms och globala panelmeny på båda vyerna.

Ett giltigt status-release kräver samma start-/slutyta, panel och aktiv
timer. Timern uppdateras först genom befintlig `serviceFocusTimer()`;
panel och Running/Paused kontrolleras igen. En naturlig fasgräns följer
befintliga cue/auto-show-regler. Completed eller automatiskt panelbyte
under trycket kan inte återstartas eller togglas genom en gammal hit.
Ett därefter accepterat tryck använder `focusToggle()`/`setFocusState()`
för lokal Running↔Paused och stannar i aktuell vy.

En väntande vanlig media-1/2/3-grupp rensas **inte vid press-start**.
Vid giltig status-release sätts dess deadline till nu och befintlig
`serviceMediaTaps()` slutför gruppen en gång **före** lokal toggle.
Ingen separat kommandomapp införs. Normal→status→normal får därför två
separata vanliga grupper och en lokal toggle. Ett rent status-tryck utan
tidigare vanlig grupp ger noll serial/bonk. Befintlig cancellation vid
svep, långtryck och naturligt panelbyte bevaras.

## Fryst kandidat

| Fält | Värde |
| --- | --- |
| App | `.pio/candidates/focus-status-tap-F406C485.bin` |
| SHA-256 | `F406C485C775E3D907A04BC82620CB305E4EC48FAC10F0CF52754DB508EA2984` |
| Storlek | 928960 byte |
| Miljö / byggtid | `esp32-024r-spotify-fastserial` / 54,905 s |
| Statisk RAM | 112080 / 327680 byte, 34,2 % |
| Bygg-flash | 928217 / 1966080 byte, 47,2 % |
| Drift / appflash | 230400 / 115200 baud, `0x10000` |
| Kandidat-/källmanifest | `build/focus-status-tap-2026-10-12/candidate.json`, 15 källhashar |
| 08A-source/report-baslinje | `build/focus-status-tap-2026-10-12/baseline/manifest.json`, 14 filer |
| Preview-manifest SHA-256 | `26ACCD97B4523EE41DDCAC1F9CD8CEC7ED1987A7B6AF128CD61C7803C5698631` |

Bygg-RAM är lika med 08A; bygg-flash är 424 byte större. Detta mäter
inte runtime-heap. Två Bongo-objekt har tagits bort; kandidatens egna
heap-/art2-data redovisas nedan. Befintliga TFT_WIDTH/TFT_HEIGHT-varningar kvarstår.

## Fokuserad verifiering

| Kontroll | Resultat |
| --- | --- |
| Firmwarebuild | PASS |
| Verkliga fonter, samtliga tidsbredder, bounds och touchytor | PASS |
| Negativa kontroller: stats/canvas/card-kollision | PASS |
| 22 PNG, dimensioner/hash och aktuella källhashar | PASS |
| Pixelbevaring av Bongo stats/klocka/canvas och cue endast på fas | PASS |
| Player-PNG och centrala Player-/omslagsfunktioner mot 08A | PASS |
| Befintliga layout-/zoom-/cuevägar i källan | PASS |
| Host-C++ cache/UI-adapterruntime | **SKIP**, ofullständig lokal MSVC/setup/includes |
| Host-C++ faktisk central-handler/dispatch/timer-runtime | **SKIP**, samma begränsning |
| Båda C++-fixturer, Xtensa C++14/Wall/Wextra/Werror | PASS, 14 static_assert-grupper och faktisk firmwarekod kompilerar |
| `git diff --check` och nya rapportens whitespacekontroll | PASS |

Sex Pythonkontroller är exekverade; två C++-körprov är uttryckligen
**inte exekverade**. Kompilering är inte samma sak som ett kört handlerprov.
De 14 `static_assert`-grupperna utvärderas vid kompilering.
Ingen toolchain har installerats eller reparerats.

Den nya lilla handler-fixturen extraherar verklig `handleTouchFeature`,
`handleFocusStatusTap`, media-queue/dispatch, meny-toggle samt
`setFocusState`/`serviceFocusTimer`. Fejkad TFT och UI/Serial-recorder
förbereder kontroll av båda paneler/faser, pause/resume, dold status,
vanliga 1/2/3-grupper, pending→status→normal, rent status utan sidoeffekt,
drag/ut-och-tillbaka, svep och långtryck från status, meny/panelbyte,
Completed/naturligt auto-show vid fasgräns och millis-wrap.
Cache/UI-fixturen bevarar omslags-/DJ-/layoutövergångskontrollerna och
kontrollerar ny kolontext/fasfärg. Dessa stateful fixturer har inte körts;
här redovisas deras godkända kompilering. Fysisk huvudacceptans och de
kvarvarande fysiska avgränsningarna redovisas separat nedan.

## Förhandsbilder och UI-granskning

[Normal Bongo](../visuals/focus-countdown/status-tap-implemented-2026-10-12/composed/bongo_focus.png),
[normal Player](../visuals/focus-countdown/status-tap-implemented-2026-10-12/composed/player_focus.png)
och övriga 20 tillstånd finns i separat preview-mapp. Källhärledda
240×320-bilder använder verkliga LVGL-glypher och fontmått. Orange
`touch_map_bongo.png`/`touch_map_player.png` är enbart granskningsöverlägg;
de syns inte i produkten. Kodskrivaren har granskat normal, lång/pausad,
grön/cyan cue och touchyta. UI har nu **godkänt de faktiska
implementationsbilderna och touchregionerna**, med samma källhashar
som F406C485-manifestet. Lead har verifierat kandidatens storlek/SHA,
samtliga 15 källhashar, preview-manifestet och de fyra äldre
firmwarebilderna utan avvikelser. Companion är fortsatt 68CC5BC1.
Detta gäller granskning av källhärledda förhandsbilder och regioner.
Den senare fysiska acceptansen gäller exakt F406C485 och redovisas separat.

## Verifierad appflash och uppstart, 2026-10-12

Lead verifierade binärens hash/storlek och flashade exakt F406C485 som
app-only vid `0x10000`, COM6/115200 med esptool 4.9.0. 928960 byte
(428696 komprimerade) skrevs på 38,0 s; `Hash of data verified`, exit 0.
Installerad companion är fortsatt 68CC5BC1 och startades
18:50:32.490 +02:00. COM6 anslöt på andra försöket 18:50:40.109;
art2 capability bekräftades 18:50:52.667. Två boot-legacyöverföringar
på 9203/9202 ms utesluts från art2-jämförelsen. Alla tider nedan är
2026-10-12 lokal tid i Stockholm, UTC+02:00.

## Fysisk huvudacceptans på F406C485

| Delprov enligt Leads frågeflöde | Användarbekräftelse |
| --- | --- |
| Dold status utan pass, nytt 5/1-pass, Bongo-stil och god Player | ”Japp allt funkar” |
| Status lätt att träffa; rent korttryck på båda vyer växlar lokal paus/fortsätt utan musik-/vybyte | Samma samlade svar |
| Rätt omslag omkring 5 s, jämn text/skiva/touch, DJ-svep och panelmenylångtryck | ”Japp” |
| Normal musik-tap → direkt statustryck → normal musik-tap: musik pausas/fortsätts utan oavsiktligt NEXT, status styr bara timern | ”Japp” |
| Större mediasvep som börjar på Players Fokus-status | Fungerar och är uttryckligen önskat beteende |
| Pausfas | ”Paus funkar också som den ska” |
| Avslutad paus och Nollställ: status dold på Bongo/Player, omslag och DJ större igen | ”Ja båda” på den explicita slutfrågan |

Detta är kvalitativ huvudacceptans enligt det samlade frågeflödet,
inte instrumenterade separata delprov eller fysisk pixelmätning.
Användaren beskriver drag på Player-status som samma svep som på skivan
och säger att det är önskat. Det styrker bevarad mediasvepprioritet.

Loggens MEDIA_CONTROL visar normal PLAY_PAUSE/NEXT/PREVIOUS med result
success. Användarens fysiska bedömning är underlaget för rena status-tryck
utan musikbiverkning; godtyckliga loggintervall tillskrivs inte dessa tryck.

### Avgränsade fall utan särskild fysisk observation

- Mindre drag ut ur och tillbaka till statusytan, utan att bli mediasvep.
- En redan väntande grupp med specifikt två eller tre vanliga mediatryck
  före status-trycket. Den bekräftade normal→status→normal-sekvensen
  verifierar inte dessa grupper var för sig.
- Finger nedtryckt precis vid naturligt fas-/automatiskt panelbyte.

Dessa fall har källgranskning och kompilerade handler-kontroller, men
hostruntime är SKIP och ingen särskild fysisk observation finns.
Det större önskade mediasvepet används inte som bevis för mindre drag.

## Egna avslutade art2-/heapdata för F406C485

Den skrivskyddade 600-sekunderssamplern, session 1227, avslutades med
exit 0. Den gav 117 giltiga färska heaprader, uptime 14–595 s; initial
nullrad utesluts. Första och sista rad:

| Sample | Fri heap | Minsta sedan boot | Total heap | Uptime |
| --- | --- | --- | --- | --- |
| 18:50:53.3460694 | 180264 | 179404 | 261624 | 14 s |
| 19:00:30.7658113 | 180124 | 175916 | 261608 | 595 s |

Sista raden är connected=true. Sista åtta proverna
18:59:55.4218530–19:00:30.7658113 hade fri heap 180124, utom
19:00:05.5215426 med 180112. Minsta heap 175916 och total 261608 var
oförändrade i dessa åtta prover. Lägsta **samplade fria** heap under
hela insamlingen var 179932; detta är ett annat mått än bootminimum.
Bootminimum sjönk senare under fas-/slutproven. Olika arbetsmoment
ger ingen ensam slutsats om läckage eller objektkostnad.

Tre art2-sändningar är verifierade. Inga nya art2-fail/reject observerades
i den inspekterade runloggen. Duration är loggens rapporterade värde;
ACK-fördröjning räknas från sent.

| Art2 | Queued | Sent | Duration | Lyckad ACK | ACK efter sent |
| --- | --- | --- | --- | --- | --- |
| A | 18:52:01.342 | 18:52:06.469 | 5125 ms | 18:52:06.521 | 52 ms |
| B | 18:52:35.818 / 18:52:38.600 | 18:52:43.965 | 5343 ms | 18:52:43.988 | 23 ms |
| C | 18:57:10.181 / 18:57:13.418 / 18:57:16.648 efter NEXT | 18:57:21.802 | 5139 ms | 18:57:21.811 | 9 ms |

B räknas som en avslutad överföring med ersatt köinnehåll, inte två
skickade omslag. C är en avslutad överföring efter snabba byten,
inte tre sändningar. Spannet för de tre är 5125–5343 ms.

| Samtidigt prov | Art2 | Fri heap | Minsta sedan boot | Total heap | Uptime |
| --- | --- | --- | --- | --- | --- |
| 18:52:04.9634344 | A | 180016 | 177008 | 261592 | 89 s |
| 18:52:39.2997863 | B | 180008 | 176912 | 261592 | 124 s |
| 18:57:20.9385652 | C | 180128 | 176508 | 261608 | 405 s |

Samplad fri heap under dessa överföringar är 180008–180128 och
minimum sedan boot i samma rader är 176508–177008.

| Mått | Ursprunglig 6A5366C1 | Historisk 08A78748 | Nu F406C485 |
| --- | --- | --- | --- |
| Art2-duration | 5030–5188 ms | 5155–5328 ms | 5125–5343 ms |
| Fri heap under art2 | 182288–182296 | Senare tre: 179684–179696 | 180008–180128 |
| Minsta heap i dessa rader | 178456 | 176004 | 176508–177008 |
| Sista/stabila fria heap | 182288 | 179680 | 180124 |
| Minsta heap vid slut | 178456 | 176004 | 175916 |

F406:s sista fria heap är 2164 byte (2,11 KiB) lägre än 6A, och
minimum 2540 byte (2,48 KiB) lägre. Mot 08A är fri heap 444 byte högre
och minimum 88 byte lägre. Uptime, handlingar, bilder och faser skiljer
sig; detta isolerar inte labelkostnad och ger ingen exakt FPS- eller
prestandaslutsats. Användaren bekräftar upplevd jämnhet och fungerande
touch. 08A-data är historik; F406-raderna ovan är kandidatens egna prov.

## Scope och bevarande

Ändrat mot 08A: `src/bongo_cat_featured.inc`, `src/focus_countdown.h`,
`tools/focus_countdown_visuals.py`, `tests/focus_countdown_test.cpp` och
`tests/test_focus_countdown.py`. Nya `src/focus_status_touch.h`,
`tests/focus_status_touch_test.cpp`, denna rapport och separat preview.

De 15 äldre adaptiva filerna är byte-/hash-bevarade. Frysta 6A5366C1,
BD666797, 8BB91836 och 08A78748 är bevarade; 08A-källorna/rapporten är
backade före ändring. Tidigare rapporter/baslinjer, Player-presentation,
Fokus-logik, övriga gester, companion och releasefiler är bevarade.

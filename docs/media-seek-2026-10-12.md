# Spelare: relativa tidslinjesvep ±15 sekunder

## Status och användning

**Implementerad, byggverifierad och fryst: 57894EE0 / A52946E5.**
Fysisk installation och seek-verifiering är **uppskjutna på användarens
begäran 2026-10-12**: ”Nej, vi får ta skärmprovet senare”.
Installerat par är fortsatt F406C485 / 68CC5BC1. Lead har inte flashat,
startat kandidaten, ersatt EXE:n eller stoppat den installerade companionen.
F406C485 och installerad companion 68CC5BC1 är bevarade rollbackfiler.
Inget har flashats, installerats, startats/stoppats, committats eller släppts
av Kodskrivaren i denna uppgift. Lead sköter fysisk installation och prov.

På Spelare: börja ett kort horisontellt svep på **låtens nedre stapel eller
tider**, släpp åt höger för +15 s eller vänster för −15 s. En gest ger ett
relativt hopp oavsett svepets längd. Två snabba svep räknas i ordning.
Låten kan spela eller vara pausad; seek ändrar inte pausläget.
Båda nya kandidatdelarna behövs för denna funktion.

Startytan är halvöppen **(16,262,210,31)**, inclusive
`TouchRect{16,262,225,292}`. Faktisk stapel är (19,264,204,6) och tiderna
ligger på y278–288. Ytan har 2 px marginal ovanför stapeln och 4 px under
tidstexten. Artist, titel, omslag, uppspelningsstatus och övre Fokus-status
ingår inte. Ingen ny synlig kontroll har lagts till.

## Gesture och bevarande

`handleTouchFeature()` är fortsatt ensam eventägare. Start i tidsytan
låses för gesten. Raw Y **minskar åt skärmhöger** → +15 s; ökande raw Y
ger −15 s. Vid release krävs minst 420 raw horisontell förflyttning och
minst dubbelt så stor horisontell som vertikal slutdelta, inom befintlig
kortgest 35–649 ms. Inget kommando skickas under touchsamples.

Release får lämna startytans kanter. Modest uppåt-/nedåtdrift tillåts;
mer än 180 raw vertikal förflyttning avbryter seek permanent, även efter
återgång. Därmed fungerar exempelvis start på stapeln y264 med drift
till y261. Små brusdrag ger vanlig tap; större ofullbordat/ut-och-tillbaka
drag konsumeras. Start utanför ytan behåller skivans NEXT/PREVIOUS.

Dominant nedsvep behåller DJ-prioritet och långtryck behåller panelmenyn.
Fokus-statusens korttryck och flush av tidigare normalmediatryck är
oförändrade. Ett accepterat seek avbryter däremot väntande vanlig 1/2/3-
tapgrupp, precis som befintliga mediasvep, och skickar **endast SEEK**.
Panel-/meny-/mottaget metadata- eller kontextbyte avbryter tidslinjegesten.
UI/progress ändras först när vanlig snapshot bekräftar en ny position.

## Minimal kontextbunden serialväg

- Companion skickar `MEDIA_SEEK_CONTEXT:<uint32>` sist i det befintliga
  metadata-paketet, efter source/title/artist/state/time och eventuell
  `MEDIA_ART_DEFAULT`. Id:t härleds som en opak CRC32 av källa/låtnyckel;
  varken låtnyckel eller titel följer med seek-kommandot eller diagnostiken.
  Noll betyder att inget aktuellt seek-sammanhang finns.
- Markören skickas bara vid verkligt låt-/källbyte, första synk eller
  återsynkning. Den befintliga regelbundna trafiken får ingen extra markör.
  Skickad-id-cachen ändras först efter lyckad metadata-sändning.
- Firmware validerar kanonisk uint32-decimal inklusive overflow och svarar
  vid ett accepterat svep med `MEDIA_CMD:SEEK:+15:<id>` respektive
  `MEDIA_CMD:SEEK:-15:<id>`. Companion accepterar exakt dessa två steg och
  ett giltigt icke-noll-id. Gamla vanliga MEDIA_CMD är bevarade.
- Markörens placering som slutrad hindrar det nya id:t från att bli giltigt
  före motsvarande title/artist/time på firmware. Om metadata väntar under
  ett omslag behåller skärmen sitt gamla id; companion nekar det mot sin
  nyare snapshot. Under pågående gesture fångas även lokala metadata-byten.
- Bridge använder befintlig worker med högst fyra seek-requester totalt,
  inklusive den väntande/exekverande. Varje request gäller i fem sekunder,
  ägs av sin källa/låtnyckel och slängs vid byte, expiry eller API-spärr.
  Begränsning/misslyckande loggas utan låtdata. Ingen extra tråd införs.

Art2-format, råa omslag, corefördelning, buffertar, cache/CRC/ACK och
befintlig progressankring är bevarade. Ingen Windows-inställningsvy ändras.

## Windows och Spotify Connect

Lokal Windows-Spotify använder den aktuella GSMTC-sessionen: färska
properties måste matcha låtnyckeln, `is_playback_position_enabled` måste
vara true och aktuell timeline måste ha giltiga seek-gränser. Position
extrapoleras från `last_updated_time`/playback rate när den spelar och
klampas till start/min/max-seekable, strikt före end. SDK-anropet är
`try_change_playback_position_async(Int64 ticks)` med 10 000 000 ticks/s
och ett bool-svar. Nekat/ej stöd/exception ger ingen falsk position och
ingen fallback till en annan mediekälla.

Connect gör en färsk paced playback-läsning före en enda
`PUT /me/player/seek?position_ms=...&device_id=...`. Den kontrollerar faktisk
låtnyckel, device-id, restriction/disallows och millisekundslängd. Spelande
position extrapoleras under väntan till PUT. Målet klampas 0..duration_ms−1
för att inte begära NEXT vid slutet; inga NEXT-anrop görs av seekvägen.
Ett lyckat PUT ritar ingen optimistisk position. Den vanliga bekräftande
snapshoten skickar sedan MEDIA_TIME genom den befintliga vägen.

Förberedande read, PUT och bekräftande read delar ordinarie gate med
pollning/kontroller/art-fallback. Aktivt minimum 0,5 s, installerad idle-
preferens 15 s, sparad Retry-After/429-historik och kvotåterhämtning bevaras.
En lokal pacing-väntan håller en tidsbegränsad request; 429 slänger dess
seek i stället för att köra den efter lång cooldown. Nekat/HTTP-fel kraschar
inte bridgen och skapar ingen ny seek-köflod.

Primärkällor: [Microsofts ticks/bool-kontrakt](https://learn.microsoft.com/en-us/uwp/api/windows.media.control.globalsystemmediatransportcontrolssession.trychangeplaybackpositionasync?view=winrt-26100),
[Spotifys seek-endpoint och slutgräns](https://developer.spotify.com/documentation/web-api/reference/seek-to-position-in-currently-playing-track).
Installerad Python/WinRT **3.2.1** har kontrollerats skrivskyddat: den
faktiska Python-signaturen tar Int64 och timeline-gränserna är timedelta.
Ingen riktig media-control eller API-seek har körts av Kodskrivaren.

## Verifiering

| Körda kontroller under denna uppgift | Resultat |
| --- | --- |
| Nya seektester: parsing, clamp, Windows/Connect, expiry, source/track, två snabba svep, queue, 429, ordning/resync, gammal skärm/ny companion, faktisk snapshot/engine-tidsuppdatering | 19 PASS |
| Adaptiv Connect och delad gate | 6 PASS |
| Lokal normalmedia utan API-överskrivning | 2 PASS |
| Cooldown/Retry-After/urgent/idle/kvot | 11 PASS |
| Art2, kvittens, snabb ändring, tidsankring och touch under omslag | 16 PASS |
| Återanslutning/återsynkning/serial under omslag | 13 PASS |
| Diagnostik och thumbnail-/fallbackregression | 8 PASS |
| Fonters bounds, preview, skyddade Bongo-pixlar, Player-bevaring och layout | 6 PASS |
| Faktisk central-handler/dispatch/timer hostruntime samt cache/UI hostruntime | **2 SKIP**, ofullständig lokal MSVC/setup/includes |

Totalt **81 exekverade Pythonkontroller PASS, 2 C++-körprov SKIP**.
Båda verkliga C++-fixturer kompilerar med Xtensa/Wall/Wextra/Werror.
Touchfixturen kompilerar även i firmwarens C++11. **19 static_assert-grupper**
utvärderas vid kompilering, inklusive verklig context-parser,
riktning/tröskel/dominans, kanter och modest uppåtdrift.

Den stateful central-handlerfixturen innehåller även en-per-release,
pending-grupp, edge/outside-start, drag/cancel, panel/meny/contextbyte,
DJ/långtryck och Fokus-fall. Dessa runtime-fall är **kompilerade men inte
körda**; de är inte fysisk eller exekverad touchacceptans. Ingen toolchain
har installerats/reparerats. En parservariant som krävde C++14 anpassades
till C++11 före det sista firmwarebygget.

Companionpaketet kontrolleras mot kompilerade aktuella Pythonkodobjekt
(filnamn normaliserade) och fyra byteidentiska resurser. Detta verifierar
paketinnehåll; kandidaten har inte startats på COM6 av Kodskrivaren.

## Bilder och UI-granskning

Källhärledda 240×320-vyer ligger i
`visuals/media-seek-implemented-2026-10-12/`: 22 ordinarie bilder och fem
orange seek-overlays för vanlig/pausad/idle/DJ. Alla 22 ordinarie bilder
är hashidentiska med F406. Orange ramar syns bara i granskningsbilder.
`createMediaScreen()` och tidigare Player-/Bongo-presentation är bevarade.
UI/Lead har godkänt exakt startyta, riktningar, sidorelease och driftfix.
Senare numerik-/kontextvalidering ändrar ingen geometri eller bild.

## Fryst par och bevarande

| Del | Fil, bytes och SHA-256 |
| --- | --- |
| Firmwareapp | `.pio/candidates/media-seek-57894EE0.bin`, 929984 byte |
| App SHA-256 | `57894EE0D9249A6651F9210BD24ED1548CFD7E784E6DF20A1DC0919B534B6CEC` |
| Companion | `dist/companion-2026-10-12-seek-dev/BongoDeskSpotify.exe`, 19303449 byte |
| EXE SHA-256 | `A52946E59180390D892A80909E66002F8C3F92CC9CACD2D2540CEC7C4CBC55A6` |
| Firmwarebuild | `esp32-024r-spotify-fastserial`, PASS 41,772 s |
| Bygg-RAM / flash | 112096/327680 (34,2 %) / 929253/1966080 (47,3 %) |
| Companionbuild | PASS 12,756 s |
| Drift / appflash | 230400 / 115200 baud; app-only `0x10000` |
| Källmanifest, 52 filer | `source-frozen.json`, SHA `39704D1BB197826F208B67B94D91E121BEE3B357799636593C9070DBDD0419C5` |
| Previewmanifest SHA-256 | `F025C75453ADD50AED55DEB2CB376997E9E7E5826F7DB23C2BB9CDB73B7520CB` |

Statisk bygg-RAM är 16 byte större än F406. Detta mäter inte runtime-heap.
Befintliga TFT_WIDTH/TFT_HEIGHT-varningar kvarstår; slutbygget har inga fel.

Lead har oberoende verifierat båda kandidatfilerna, alla 52 källhashar,
käll-/previewmanifest och 29 bevarade artifacthashar/bytes utan avvikelse.
Installerat par är fortfarande F406/68CC. Appflash och tillfälligt
kandidatprov är uppskjutna enligt användarens besked ovan; denna
filverifiering är inte fysisk seek-acceptans. Exakt fryst par, källmanifest
och färdiga tester behålls till det senare skärmprovet.

Exakta bytes/SHA/buildtal och samtliga källhashar finns i
`build/media-seek-2026-10-12/candidate.json` och `source-frozen.json`.
Separat före-baslinje innehåller 43 filer samt hashinventering av 29
äldre artifacts. Sju befintliga filer ändrades inom uppgiften:

- `src/bongo_cat_featured.inc`
- `companion/engine.py`, `companion/media_bridge.py`, `companion/spotify_api.py`
- `companion/diagnostics.py`
- `tests/focus_status_touch_test.cpp`, `tests/test_focus_countdown.py`

Nya: `src/media_seek_touch.h`, `companion/media_seek.py`,
`tests/test_media_seek.py`, `tools/media_seek_visuals.py`, denna rapport
och separat preview. Övriga 36 baslinjefiler är bytebevarade; äldre adaptiva
ändringar i bridge/API finns i före-snapshoten och deras pacingregressioner
passerar. Gamla källmanifest/rapporter/kandidater, F406/68CC rollback och
publicerade releasefiler är bevarade. Git-diff/whitespace är kontrollerade.

## Kvarstående begränsningar och fysisk provplan

Riktig SDK-/API-källa kan neka seek, exempelvis utan stöd/rättigheter eller
vid restriction/429; då ska befintlig bild/position inte hoppa falskt.
Spotify erbjuder ingen atomisk villkorad "seek bara denna låt". Ett
externt byte mellan färsk läsning och PUT kan därför fortfarande inträffa.
Den mycket korta slutpositionen kan nå naturligt låtslut när uppspelning
fortsätter; klampningen hindrar ett avsiktligt NEXT från seekbegäran.

Följande är **väntande på detta nya par**, även om äldre F406 normal-UI
och tidigare sleep-/omslagsprov är godkänd historik:

1. Connect först och lokal Windows-Spotify separat: höger/vänster ±15,
   två snabba höger ≈30 s, höger/vänster tillbaka, både spelande och pausad.
   Prova vid början/slutet och observera att inga seek-kommandon ger NEXT.
2. Kanter/tidstext, modest uppåtdrift, start utanför, större drag tillbaka,
   avbruten gesture och låtbyte under omslag. Gammalt sammanhang ska nekas.
3. Vanlig enkel/dubbel/trippeltap, väntande tap→seek→tap, skivsvep,
   DJ-nedsvep och långtryckmeny. Prova separat övre Fokus-status.
4. Bekräftad progress/tid efter seek, samma omslag, jämn skiva/touch under
   art2 och nytt omslag efter snabba byten; jämför heap/art2 med F406.
5. Återsynkning efter reset/sleep samt normal släckning/väckning. Observera
   bakbelysning och UI. Inga nya tids-/ström-/blixtkrav är fysiskt hävdade.

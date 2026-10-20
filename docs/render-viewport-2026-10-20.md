# Spelarens bildklippning och renderprov – 2026-10-20

## Drift och bevisgräns

Installerat är **C42112AD/EBB334A9 vid 921600**. Lead provade tillfälligt den
tidigare mätbinären **D7DA9953** med syntetiskt innehåll och återställde sedan
den verifierade ursprungliga appsektorbackupen. Nya viewportkandidater nedan
är **endast byggda, inte flashade eller fysiskt accepterade**. Ryckig textrullning
under uppspelning är fortfarande ett öppet hårdvaruproblem.

Återställningen omfattade 942 080 byte vid `[0x10000,0xF6000)`, inklusive exakt
EBB-prefix och ursprunglig sektorsvans. Backup-SHA:
`855CAF3A40715512E46D4B1EC5FA0367E75E0AFD35A8940897E48E1F233DD896`.
Esptool verifierade skrivningen; 43,047 s, exit 0. Bootloader/NVS skrevs inte.
C421, aktuella profiler/auth/budget, Run och två genvägar bevarades.

Start via vanliga Startmenyn följdes av manuell RESET. Första serieanslutningen
misslyckades medan bootstubben låg kvar; andra lyckades. Leads säkra kvitto
**14:56:25,996 svensk tid** visar ansluten ESP, uptime 70 s, statusålder 0,957 s,
ESP-statusålder 0,596 s, Windows Spotify aktiv och API `ready`. CPUdiagnos är
åter avstängd. Resync, fullbilds-ACK och kompaktkapabilitet loggades. Tre fulla
37 632-bytejobb tog 4960/4990/5069 ms på sändarsidan: inga nya kompakta fartprov,
LCD-tider eller generell ensekundsgaranti. Ny fysisk acceptans efter återställning
väntar på användarens prov.

## Varför en avgränsad ändring görs

D7DA:s syntetiska mätning gav följande stabila fönster. **G** är gap mellan
handleranrop, **H** tid i `lv_timer_handler`, **F** tid för en enskild synkron flush.

| Fas | G antal / max | H antal / max | H över 66 ms | F antal / max |
| --- | --- | --- | --- | --- |
| Paus före, två 15 s-fönster | 1841 / 72,825 ms | 1841 / 62,685 ms | 0 | 2524 / 4,597 ms |
| Uppspelning, två fönster | 373 / 96,204 ms | 373 / 85,524 ms | 347 (93,029 %) | 2601 / 4,572 ms |
| Separat paussupplement, ett fönster | 704 / 86,639 ms | 704 / 76,445 ms | 5 (0,710 %) | 1255 / 4,581 ms |

Första försöket väntade ut reset utan timingdata. I trefasförsöket saknades
giltiga rader för sista pausen; det var **inte ett komplett trefas-PASS**.
Paussupplementet togs separat utan reset i samma bekräftade vinylvy med stängd
meny. Sex respektive en diagnosrad avvisades. D7DA har egen mätkostnad och är
inte en EBB-baslinje eller ett mått på panelens FPS. Enskilda flushmax får inte
subtraheras från handlermax. Även paus hade några långa anrop.

Det äldre tvåkärniga idle-tick-provet gav ungefär 0–2 % paus och 47–48 % spelande.
Det är en grov aktivitetsindikator, ingen exakt CPU-/task-/FPS-mätning.
Underlaget motiverar att minska ritområdet vid rotation, men bevisar inte att
alla ryck kommer från samma orsak eller att den nya kandidaten löser dem.

## Källändring

- Bilden är permanent barn till en **transparent rektangulär viewport** på
  art-boxens plats. Tonarm och tass är fortsatt syskon på skärmen ovanför bilden.
- Endast `frame.changing` tillåter `OVERFLOW_VISIBLE`, så komplett uttag och
  skivflip kan lämna viewporten. Stadig rotation klipps till bildytan.
- Gamla transformerade bildgränser invalidieras **före** ändring av viewportens
  läge, storlek eller overflowflagga. Det sker även före dold/annan panel-returen.
  Ny yta invalidieras efteråt. Befintlig full invalidiering av art-boxen bevaras.
- Bildens lokala position motsvarar den gamla absoluta formeln, inklusive
  `dx/dy`, båda Fokus-layouterna och dubbelzoom för 56-pixels OOM-fallback.
- 60 ms/18 vinkelenheter, 112-/80-format, refinement, bildkvalitet/fonter,
  svensk text, touch, Fokus, DJ, core-0-RX/drain/CRC/cache och normal serialtrafik
  bevaras. Ingen companion-, baud-, SPI-, generell LVGL-period- eller releaseändring.

## Riktig LVGL-raster och testport

Testerna kompilerar LVGL **8.3.11** från arkivverifierad upstreamcommit
`74d0a816a440eea53e030c4f1af842a94f7ce3d3`. Arkiv-SHA:
`9a28236db180e5634c32acaef10ffaf242f2b52c71ad63db82f238b8b76a1936`.
355 C/headerfiler under `src` och fyra rotfiler verifieras separat från projektets
källmanifest. Fresh worker får bara den verifierade kopian; ingen nedladdning
sker i worker och saknad/felaktig dependency ger fel, inte SKIP.

Den verkliga mjukvaruritaren, fontdata, animationstimer och 40-raders
displaybuffer används. Bara TFT-transporten ersätts av en RAM-bild på 240×320;
klocka och serialnotis är hostadaptrar. DJ använder ett uttryckligt syntetiskt
testmönster för klippning, inte en ny verifiering av kattens sprites. Aktuella
viewport-/rotations-/projektions-/arm-/tass-/Fokusfunktioner och Spelarens
relevanta objektbygge extraheras från firmware. Produktionskonfigurationen
behålls med manuell hosttick och en effektiv `abort`-assert i stället för evig loop.

Den befintliga Windows-kompilatorn och riktiga CRT används. Små testlokala
C-ABI-deklarationer ersätter saknade lokala SDK-headers; de innehåller ingen
ersättningsritare. Implicita C-funktionsdeklarationer är kompileringsfel.
Fontbryggan använder exakta produktglypher/metrics och samma fallbackfält.
Byggcache/DLL är bunden till utmatningsmapp, dependency och faktiska inputhashar.
Ingen ny SDK installerades. Linuxgrenen är inte lokalt verifierad.

**Oracles hålls åtskilda:**

1. Varje komplett scen rekonstruerad från inkrementella flushar måste vara
   **bitexakt lika en full omritning av samma nya scen**. Ingen tolerans finns.
   Negativkontrollen fyller hela den synliga 112×112-bildslotten vit utan
   invalidiering och ska upptäcka den avvikelsen. Enpixelskänslighet provas inte.
2. Globala bildkoordinater, storlek, pivot och zoom kontrolleras exakt mot den
   gamla oberoende formeln. Parent, overflow och arm-/tassordning kontrolleras.
3. Gammal/ny hel scen jämförs exakt i projektionsposer och på returframen efter
   avbrott. Själva avbrottsframen (`pose(..., false)`) jämförs bitexakt mot **ny
   full omritning**, utan legacy-jämförelse. Vid stadig rotation ger LVGL:s
   clipberoende heltalssteg små samplingdifferenser. Bilden
   isoleras då från antialiasad arm/tass/rundad bakgrund; varje avvikande pixel
   måste ha samma färg högst **en displaypixel** bort i båda riktningarna, och
   högst **32 pixlar per bild** får skilja. Ingen flyttning eller skalning tillåts.

Den första strikta rotationsjämförelsen underkändes med tre skillnadspixlar.
Diagnostik över hela varvet i båda layouterna för 112 och 56 pixlar gav 3802
skillnadspixlar totalt, max 30 per bild; alla rymdes inom en displaypixel.
LVGL:s `lv_draw_sw_transform` räknar heltalssteget från klippta radens båda
ändpunkter. Gammal/ny rotationsraster är alltså **inte bitidentisk**.
De första underkända provkvittona bevaras; inget fysiskt kvalitetspåstående görs.

### Slutlig ren kontroll

**388 funna/379 PASS/nio klassade SKIP/noll fel och noll blockerade operationer**,
84,428 s, från en ny kopia med syntetiska profiler och verifierad dependency.
Undantag: sex saknade historiska arkiv, ett privat foto och de två befintliga
lokala fulla C++-/SDK-fixturerna. Inga nya rasterprov hoppas över.
De senare två kördes i tidigare faktisk GitHub-CI; ny CI efter denna ändring
är ännu inte körd. Den nya porten kör däremot faktisk LVGL lokalt med befintlig cl.

Sex nya prov PASS: cacheidentitet, riktig formatter/varargs, rotation/OOM,
flip/fullt uttag/snabba identiteter/slots, Fokus/DJ/meny/panelavbrott/retur samt
svensk marquee och negativ pixeloracle. **2930 inkrementella bildjämförelser**
passerade bitexakt: 805 rotation/layout/OOM, 1442 byten, 562 avbrott och 121
marquee/oracle. Dessutom upptäcktes den avsiktliga negativa kontrollens enda
bildavvikelse när hela 112×112-slotten fylldes vit utan invalidiering; ingen
separat enpixelskänslighet provades. Alla positiva jämförelser har noll tolerans
mot ny full omritning.

400 normala rotationsbilder i två layouter gav **11 368 000** flushpixlar
med viewport mot **17 828 796** med tidigare screen-parent. Det mäter endast
den syntetiska mjukvaruritningens skickade yta, **inte FPS, CPU eller TFT-tid**.
Ytterligare 400 bilder provar 56-fallback i båda layouterna. Isolerad gammal/ny
sampling: totalt 3802 diffpixlar, 661 bilder med skillnad, max **5/30 pixlar**
per bild för 112/56; alla inom den symmetriska enpixelgränsen och taket 32.

Kvitton: `build/product-committee-2026-10-20/viewport-clean-final-r3/check-g5wnwd2z/`.
Summary-SHA:
`03493A67B394627435494DBB30C78215244E4A3F9707C556C84229D272B9D323`.
Snapshotens källmanifest-SHA, före denna slutliga resultattext:
`C7D4592DAF4B70BD0A0DC6B397E50AC44E2CF8BDFFE8B5CD4D2CBCAE4BC9F001`.
Separat dependency-manifest-SHA:
`3CE93ACCB207A3E209E97733E91E4D48A8E31EB606C1E4853976A4C2E3F964AE`.
Rastermätkvitto `native/lvgl/rotation-raster-measures.json`, SHA:
`7C17A12A4E5247FB70162350FE2B794C82D424C8CE38032FCB4AEA542A86EF38`.

## Nya firmwarekandidater – endast byggda

| Profil | Appbinär vid 0x10000 | SHA-256 |
| --- | --- | --- |
| `esp32-024r-spotify-compact80` | 937 600 byte | `61BE3B633AF700B27F0DDF55F9B26D41E1B9E0916F187848A470B50988701440` |
| `esp32-024r-spotify-renderdiag` | 938 400 byte | `1252EBAC2C3CBFEC4915DADB172CC06DB5799DF7E0482B17710E474DD4274C33` |

Båda byggen PASS, 67,55/67,39 s. RAM 112 448/112 856 byte; programflash
936 857/937 661 byte. Fryst källa och nya build/cache/libdeps ligger i
`build/product-committee-2026-10-20/render-viewport-r1/`.
38-filskällmanifestets SHA:
`3D535775DEC303DF452ED9534EC09AA7595EEF275A710D7FD50E83371ACAA414`.
Leverans: `dist/firmware-2026-10-20-render-viewport-dev/` med
`normal-compact80.bin`, `render-diagnostics.bin` och `candidates.json`.
Alla 38 källpins matchar både byggkälla och arbetsyta. 3042 kopierade bibliotekspins
och ursprungliga LVGL/TFT-filer verifierades oförändrade. Normalbinären saknar
diagnossträng/symboler; diagnosbinären har dem. Offline esptool `image_info`
gav giltig checksumma och valideringshash för båda. Ingen COM användes.
Byggverifieringskvitto `render-viewport-r1/firmware-verification.json`, SHA:
`41F456AADFFB156136AE0463689B1FA8391523C304243944B45CA681F87DDF96`.

Äldre B846/D7DA-byggkvitton och alla release-/källfrysningar är bevarade.
Två genererade testfixturefiler i en äldre ignorerad testcache skrevs om under
ett fokuserat prov; det är inte en ändring av frysta binärer eller manifest.
Det gäller `build/turntable-arm-tempo-2026-10-18/focus-fixtures/` med
`focus_countdown_test_fixture.inc` och `focus_status_touch_test_fixture.inc`.
Ingen rekonstruktion gjordes utan äldre bytepin. Slutproven använder nya isolerade
mappar. Skyddade r2:s 38 källpins, 3042 bibliotekspins, manifest och båda
leveransbinärer kontrollerades separat oförändrade; release/previewfiler ändrades inte.

## Faktisk CI och återstående fysisk kontroll

På **5a5db844** passerade båda riktiga GitHub-körningarna före viewportändringen:
[PR-körning](https://github.com/Bratwurst04/Bongo-Cat-Screen/actions/runs/39420415058)
och [push-körning](https://github.com/Bratwurst04/Bongo-Cat-Screen/actions/runs/39420408069).
Varje körning gav **368 funna/361 PASS/sju klassade SKIP/noll fel**; GCC-/SDK-
fixturer kördes faktiskt där. Det är tidigare CI, inte CI för den nya viewporten.

Efter Leads granskning och ett separat godkännande för konkret ny firmwarehash:

1. Jämför flera stabila 15-sekundersfönster i normal Player: paus/spelande,
   utan pågående omslag, samma syntetiska text/bild. Kontrollera ryck och
   kvarlämnade pixlar. Mätprofilen har egen kostnad; håll den skild från normalbinären.
2. Prova hela varv, normala byten, komplett uttag, snabba låtbyten och senare
   refinement. Kontrollera tass/arm, skärpa och att gamla halvor verkligen rensas.
3. Avbryt rörelse med meny, Fokus-layout, DJ och annan panel och återvänd.
   Kontrollera svenska långa texter, alla mediegester och Fokus-touch.
4. Kontrollera fortsatt omslagsmottagning och återanslutning; sleep/resume och
   långdrift är separata fysiska prov. Ingen förbättrad FPS/jämnhet godkänns av hosttest.

Code har inte öppnat COM, bytt runtime/profiler eller flashat i detta arbete.

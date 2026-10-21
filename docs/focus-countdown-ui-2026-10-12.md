# Fokus-nedräkning – godkänd UI-design, kandidat 2026-10-12

## Status

Den av Lead beställda UI-ändringen av utseende, placering och storlek är
implementerad och byggverifierad. Lead har granskat de implementerade
förhandsbilderna. UI-specialisten har därefter lämnat **GODKÄND simulerad
UI-granskning**: källhash/spec, font, fas, markörer, kompakt signal och
120:00 med maximal statistik matchar utan visuell blockering.

**Flashning, uppstart och vissa funktioner är fysiskt verifierade; slutleverans är öppen.**
Användaren bekräftar Fokus `||`/återupptagning, omslag/text/skiva/touch/DJ/meny
med ”Funkar”. UI:t uppfattas bättre men behöver integreras med övriga delar
av skärmen; ny helhetsdesign är beställd från UI-chatten. 8BB91836 bevaras
fryst som historisk kandidat. Användaren har därefter samlat bekräftat
paus/avslut på 8BB91836 med ”Paus klar, den funkar som den ska ser det ut som”.
Lead bedömer funktionella gates som gröna enligt användaren. Detta är
samlad kvalitativ återkoppling, inte separata instrumenterade delprov.
Lead har flashat exakt 8BB91836 och avslutat dess egen heap-/art2-sampler. Ingen flash,
companionändring eller publicering är gjord av Kodskrivaren. De 15 tidigare
ocommittade filerna är fortsatt byteidentiska med ursprunglig jämförelsebas.

BD666797 är bevarad som fryst föregående kandidat. Dess efterdata och
användarbekräftelser finns separat i [BD-rapporten](focus-countdown-2026-10-12.md)
och gäller **inte** denna nya UI-version. BD:s funktioner är delvis fysiskt
verifierade; dess visuella lösning behövde ändras före leverans.

## Implementerad geometri

| Del | Ruta x, y, bredd, höjd | Font / stil |
| --- | --- | --- |
| Bongo fas | 171, 28, 64, 9 | Befintlig Unscii 8, `505860`, höger |
| Bongo tid | 139, 44, 96, 17 | Befintlig Unscii 16, `303840`, höger |
| Spelare fas | 68, 15, 36, 11 | Montserrat 10, befintlig temaaccent, mitten |
| Spelare tid | 109, 15, 48, 11 | Separat numerisk Montserrat 14, `E6EBEF`, mitten |
| Spelare paus | Staplar x163/x168, y17, 2×7 vardera | `E6EBEF`, bara vid pausad timer |
| Spelare tid under kompakt PAUS-signal | 96, 15, 48, 11 | Faslabel dold, siffror centrerade vid x120 |
| Pausmarkör under kompakt signal | Staplar x147/x152, y17, 2×7 vardera | Samma färg och pausvillkor |

Bongo visar fasnamnet `FOKUS`/`PAUS`, med ` ||` vid fryst timer, och separat
`MM:SS`/`120:00`. Spelaren visar samma lokala fas/tid med separat pausmarkör.
Idle, Prepared och Completed döljer informationen. Lokal Fokus-state,
avrundning, fasbyte, touchgester, meny, DJ, omslag och serialflöde är bevarade.

Alla sekunder upp till 120/30 minuter är kontrollerade med verkliga
LVGL-fontmått: största Bongo-fastext 64 px, Bongo-tid 96 px, Spelare-tid
46 px inom 48 px. CPU/RAM 100 % och WPM 200 är med i kontrollen.
WPM slutar vid x133, sex pixlar före största Bongo-tidsruta. Ingen
kontrollruta/glyph överlappar reserverad statistik, header, omslag eller
kompakt Player-signal. Stora övergående fasslutssignaler får fortsatt
avsiktligt täcka headern. Spelarens tidigare kompakta 70×14-signal bevaras.

## Font, buffertar och uppdatering

`lv_conf.h` aktiverar befintlig Unscii 8. Vanlig Unscii 16 används direkt;
inga nya eller avsmalnade Bongo-glypher införs.

`src/focus_countdown_font.h` skapar ett separat statiskt `lv_font_t`-objekt
som återanvänder Montserrat 14:s originaldescriptor, glyph-/bitmapcallbacks,
advance och kerning. Wrappers accepterar endast 0–9 och kolon. Objektets
line-height är 11 och baseline 1; de numeriska glypherna har ofs_y=0 och
ryms med högst 10 px höjd. Global Montserrat 14 ändras inte och ingen
fontatlas dupliceras.

Fyra labels och två stapelobjekt skapas en gång utan CLICKABLE/SCROLLABLE.
Fasbufferten är 9 byte, tidsbufferten 12 byte, med konstant livstid och
`lv_label_set_text_static()`. Bongo/Spelare delar tidsbufferten. Fastext
skrivs bara vid ändrad fas/paus/synlighet; siffror bara vid ändrad visad
sekund/synlighet. Spelarens fasnamn skrivs inte om enbart för pausmarkören.
Ingen återkommande `String`/textbuffertallokering, serialtrafik eller ny
timer tillkommer.

Spelarens presentation flyttas och döljer/visar fasnamnet endast när
villkoret för kompakt Player-signal ändras. Upprepade loopanrop utan ändrat
villkor återvänder före positions-/synlighetssetters. Temaaccenten uppdateras
genom befintlig `refreshAccentTheme()`, inte per bildruta.

## Fryst app

| Fält | Värde |
| --- | --- |
| Arbetsyta | `D:\DEV\Ai\Github\Bongo-Cat-Screen` |
| Miljö | `esp32-024r-spotify-fastserial` |
| App | `.pio/candidates/focus-countdown-ui-8BB91836.bin` |
| Storlek | 929328 byte |
| SHA-256 | `8BB91836F941B22B9664DE942553E48FA451E8F0B241DE55BE52A47BF2E76F10` |
| Verifierad appflash hos Lead | `0x10000`, 115200 baud, NVS bevarad |
| Drift | 230400 baud, oförändrad companion 68CC5BC1 |
| Statisk bygg-RAM | 112120 / 327680 byte, 34,2 % |
| Bygg-flash | 928593 / 1966080 byte, 47,2 % |

Statisk bygg-RAM är 64 byte större och bygg-flash 2352 byte större än BD.
Detta är byggmått, **inte** en eftermätning av fri/minsta heap. Källhashar
och metadata finns i `build/focus-countdown-ui-2026-10-12/candidate.json`.
Ingen firmwarekälla ändrades efter byggstart eller efter frysningen.
Fryst BD-app och ursprunglig 6A53-backup är bevarade; Lead verifierar
kandidat/rollback före flash.

## Flashning och färsk uppstart hos Lead

Lead omverifierade kandidatens 929328 byte/SHA-256, samtliga
`candidate.json`-källhashar, den tidigare återlästa 6A53-backupen och
oförändrad companion 68CC5BC1. Companion stoppades före BOOT.
På COM6 skrev esptool 4.9.0, `no_reset/no_reset`, enbart app vid `0x10000`
och 115200 baud: 929328 byte, 428942 byte komprimerat, 38,1 sekunder.
Skrivningen verifierades med `Hash of data verified`. NVS är orörd enligt
Lead. Inget nytt readback gjordes; tidigare återläst 6A53-backup och fryst
BD-app är bevarade.

Användaren bekräftade RESET med ”iklar”. Oförändrad companion 68CC5BC1
återstartades med dolt fönster och `--startup`. Färsk statusfil 2026-10-12
17:21:41.103 (Stockholm) visade ESP32 ansluten, uptime 19 s, fri heap
180792 byte, total heap 261776 byte och minsta heap 179956 byte.
Detta är **uppstartsstatus**, inte ett verifierat art2-/Fokus-efterprov.

Art2-capability bekräftades 17:21:35.392. Legacy-omslag under uppstart
utesluts ur art2-jämförelsen. Leads nya sampler kräver färsk statusfil och
den nya bootens uptime; gamla stats får inte användas som efterdata.
Efterföljande användarsvar och deras begränsningar dokumenteras nedan.

## Fysiskt funktionsprov och beställd helhetsdesign

Lead rapporterade användarsvaret ”Funkar” för just 8BB91836: Fokus pausad
med `||`/återupptagning, omslag, text/skiva, touch, DJ och meny. Detta är
kvalitativ funktionsbekräftelse; inga exakta FPS-/touchlatensmått tillkommer.
Heap-/art2-samplern är nu avslutad; dess resultat redovisas separat nedan.
Uppstartsstatusen ovan ersätter inte denna mätning och BD:s mätningar får
inte ersätta 8BB91836:s efterdata.

Om pausfas, pausad pausfas och Completed-hide sade användaren ”Den gjorde de
på förra, återkommer här också”. Lead anger detta som retrospektiv
bekräftelse av tidigare BD666797; prov på 8BB91836 var då fortfarande
väntande. Tidigare kandidatens bekräftelse överfördes inte till denna.

Användaren har sedan svarat för installerad 8BB91836: ”Paus klar, den funkar
som den ska ser det ut som”. Svaret följde den samlade frågan om Fokus→PAUS,
pausmarkör/fryst tid vid pausad pausfas, Completed/dold rad och Nollställ.
Det dokumenteras som **användarens samlade bekräftelse av paus/avslut**.
Lead anger att funktionella gates nu är gröna enligt användaren. Det finns
ingen separat instrumenterad observation av varje del och inga nya exakta
tidsmått. Visuell integration kvarstår som hinder för slutleverans.

UI:t uppfattas bättre men fortfarande otillräckligt integrerat. Användaren
vill att UI-chatten matchar övriga delar och tänker på användarvänlighet,
placering och storlek. UI-chatten har fått helhetsuppdraget och ska lämna
en ny konkret design. Leads tidigare egna snäva geometrirestriktioner är
borttagna; små motiverade lokala layoutflyttar är tillåtna inom användarens
ursprungliga krav. Den godkända simulationen ovan är en genomförd granskning
av 8BB91836, **inte fysisk UI-slutacceptans**.

8BB91836, dess källhashar och efterdata bevaras som historisk kandidat.
Ingen egen parallell redesign görs innan nästa UI-specifikation kommer.
**Ny UI-justering krävs före leverans; slutacceptans är öppen.**

## Avslutad heap-/art2-mätning för 8BB91836

Lead avslutade samplern efter egen färsk boot på 8BB91836 med oförändrad
companion 68CC5BC1 och 230400 baud. Samplern läste endast statusfilen och
krävde filfärskhet samt den nya bootens uptime. Samtliga uppstarts-/legacy-
omslag är uteslutna ur följande art2-jämförelse. Tiderna är Stockholm,
2026-10-12; sändningstiden är det rapporterade loggvärdet.

| Art2 QUEUED → SENT | Sändning | ACK-tid / efter SENT | Heap-sample | Fri / minsta heap | Total / uptime |
| --- | --- | --- | --- | --- | --- |
| 17:22:06.413 → 17:22:11.433 | 5015 ms | 17:22:11.466 / 33 ms | 17:22:08.460 | 180776 / 179924 byte | 261776 byte / 49 s |
| 17:24:56.394 → 17:25:01.552 | 5155 ms | 17:25:01.559 / 7 ms | 17:24:57.903 | 180604 / 176888 byte | 261760 byte / 219 s |
| 17:28:23.841 → 17:28:29.066 | 5219 ms | 17:28:29.106 / 40 ms | 17:28:27.642 | 180604 / 176888 byte | 261760 byte / 430 s |
| 17:29:07.763 → 17:29:12.835 | 5077 ms | 17:29:12.877 / 42 ms | 17:29:07.958 | 180608 / 176888 byte | 261760 byte / 470 s |

Den sista överföringen följde användarens lyckade NEXT-kommandologg
17:29:06.830. Lead rättade den första samplen efter återläsning av den fulla
sparade samplerbufferten: `At=2026-10-12T17:22:08.4604158+02:00`,
heap180776/min179924/total261776/uptime49, `Connected=true`. Samplen är exakt;
den tidigare ungefärliga .338-tiden var en referensmiss och är ersatt.
Ingen extrapolering har gjorts. Övriga angivna rader/tider är oförändrade.

Efter samtliga överföringar och pausavslut var fri heap stabilt 180616 byte
och minsta heap 176888 byte från 17:29:12.994 till sista prov 17:31:13.930.
Slutprovet var anslutet med uptime 595 s.

Före-baseline 6A53 hade art2-sändningar 5030–5188 ms, fri heap under
överföring 182288–182296 byte och minimum 178456 byte. 8BB91836:s
sändningar ovan är 5015–5219 ms; senare samtidiga samples 180604–180608
är cirka 1680 byte lägre i fri heap. Bootminimum är 1568 byte lägre.
Det stabila eftervärdet 180616 är 1672 byte lägre än före-sessionens
eftervärde 182288. Olika uptime och tidigare UI-/mediearbete innebär att
detta **inte är isolerad labelkostnad eller en slutsats om minnesläckage**.
Det begränsade urvalet bevisar inte ändrad överföringsprestanda.

Användarens ”Funkar” stöder upplevd jämnhet och respons. Inga numeriska
FPS-/touchlatensmått finns; ACK efter SENT är protokollkvittens.
Dessa data är **historiska efterdata för 8BB91836**. UI3 behöver egna
senare fysiska prov och egen färsk heap-/art2-mätning.

## Verifiering

- Firmwarebuild: **SUCCESS**, 58,55 s. Befintliga TFT_WIDTH/TFT_HEIGHT-
  omdefinitionsvarningar är kvar.
- `tests/test_focus_countdown.py`: **3 PASS, 1 uttrycklig SKIP**. Faktiska
  font-/sifferradsbredder, geometri, avsiktliga kollisionsfall och 20
  240×320-bilder med aktuella source/font/bildhashar verifierade.
- `tests/focus_countdown_test.cpp` kompilerar med Xtensa GCC,
  `-std=gnu++14 -Wall -Wextra -Werror`. Åtta `static_assert` kontrollerar
  visningslägen, ceil/sekund-/minutgränser, båda pausade faser, cache-nyckel,
  fas/slut/hide och numeriskt teckenfilter.
- C++ runtime-formatter/cache/UI-recorder är **inte körd** på host:
  ofullständig lokal MSVC saknar setup/includes. Den normala hosttestvägen
  finns kvar för komplett compiler; ingen toolchain-reparation gjordes.
  Testet kompilerar de fyra verkliga UI-adapterfunktionerna och innehåller
  prov för separata textsetters, staplar samt 10000 oförändrade cueanrop.
- Befintlig Fokus-logik är oförändrad; dess tidigare compiletimeprov är
  bevarade. Den nya versionen av firmware är en riktig full build.
- `git diff --check`: inga whitespacefel; befintlig companion LF/CRLF-notis.
- Ursprungliga 15 filer och frysta BD-appens SHA-256: fortsatt oförändrade.

## Förhandsbilder och reproduktion

```text
python tools/export_ui_visuals.py --focus-countdown --output visuals/focus-countdown/ui-implemented-2026-10-12
python -X utf8 -m unittest discover -s tests -p test_focus_countdown.py -v
```

20 exakta 240×320-filer finns under
`visuals/focus-countdown/ui-implemented-2026-10-12/composed/`, med kontaktkarta
och manifest i dess föräldramapp. De täcker båda faser, båda pausade faser,
120:00/maxstatistik, dold rad, kompakt signal, pausad kompakt signal,
DJ/lång källrubrik och cyan-tema på båda vyer.

Exportern använder aktuell firmwaregeometri, originalglypher, separat
numerisk radmetrik och LVGL:s heltalscentrering i de fasta labelrutorna.
Övrig text/kanter approximeras med Pillow; omslaget är syntetiskt.
Detta är **simulerade bilder**, inte skärmfoton eller fysiska prestandaprov.
Godkänt designunderlag i `ui-proposal-2026-10-12/` och BD-bilderna är orörda.

## Referens och väntande fysisk acceptans

BD:s äldre mätningar finns i BD-rapporten. Lead rapporterade dessutom BD
181668/min177912 byte 16:53:53–16:54:53 och efter ytterligare UI/cue-steg
181748/min177840 vid 16:58:39, total262160 och uptime591 s. Detta är bara
**BD-referens**. Det får inte användas som efterbevis för 8BB91836.

Fokus `||`/återupptagning, omslag/text/skiva/touch/DJ/meny är bekräftade
på 8BB91836. Paus/avslut har nu också samlad användarbekräftelse enligt
frågeflödet ovan; funktionella gates är gröna enligt Lead, utan separata
instrumenterade delprov. Heap-/art2-underlaget för 8BB91836 är nu avslutat
och redovisat ovan. Nästa konkreta
helhetsdesign ska granskas och implementeras innan ny fysisk UI-acceptans;
regression på den kommande versionen får inte ersättas av äldre kandidatprov.
**UI-justering och slutacceptans är fortfarande öppna.**

## Ändringar jämfört med BD-källan

- `src/bongo_cat_featured.inc`: fyra labels/två staplar, separata textsetters,
  cache för cuepresentation, temaaccent på Player-fasen.
- `src/focus_countdown.h`: separata fasta fas-/tidsbuffertar, numeriskt filter.
- Ny `src/focus_countdown_font.h`: statisk numerisk fontwrapper.
- `lv_conf.h`: befintlig Unscii 8 aktiverad.
- `tools/export_ui_visuals.py`, ny `tools/focus_countdown_visuals.py`:
  sourcebaserad export och glyph-/rutkontroller för den nya UI:n.
- `tests/focus_countdown_test.cpp`, `tests/test_focus_countdown.py`: anpassade prov.
- Nya bilder/manifest i `visuals/focus-countdown/ui-implemented-2026-10-12/`
  samt denna separata rapport.

BD-källa/rapport före ändringen är även bytekopierade i
`build/focus-countdown-ui-2026-10-12/baseline/`. Companion, main.cpp,
focus_logic.h, platformio.ini, releasefiler och ursprungliga 15 filer är orörda.

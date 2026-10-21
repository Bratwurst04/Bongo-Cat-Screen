# Lokal Fokus-nedräkning – kandidat 2026-10-12

## Status

Detta är historik för BD666797. Nyare kandidat och fortsatt UI-arbete finns
i [8BB91836-rapporten](focus-countdown-ui-2026-10-12.md); kandidaternas prov
och heapdata hålls separata.

Byggverifierad, fryst och lokalt flashad firmwarekandidat. Layouten är granskad av Lead
i simulerade förhandsbilder. **Delvis fysiskt provad, ingen slutacceptans.**
Lead har verifierat backup, appflash och färsk uppstart samt samlat efter-heap
under art2. Användaren bekräftar aktiv rad på båda vyerna utan täckning,
pausad Fokus med `||`/återupptagning, rätt omslag och jämn text/skiva/touch.
DJ-svep, meny och dold rad vid nollställning (Prepared) är också bekräftade.
Användaren kräver ändrat utseende, placering och storlek med befintliga bilder
som underlag. UI-chatten tar fram konkret 240×320-design för båda vyerna;
Code2 implementerar efter Lead-granskning. **UI-ändring krävs före leverans.**
Fryst BD666797 bevaras som kandidat med verifierade delfunktioner tills
designspecifikationen finns. Ingen parallell redesign görs här.
Lead har senare rapporterat retrospektiv användarbekräftelse av BD:s
pausfas, pausad pausfas och Completed-hide. Detta gäller BD, inte 8BB91836.
Kodskrivaren har inte flashat eller ändrat companion, installerad profil,
releasefiler eller den publicerade app-v1.3-releasen.

De 15 tidigare ocommittade filerna från adaptiv Connect är byteidentiska
med jämförelsebasen i `build/focus-countdown-2026-10-12/baseline/manifest.json`.
Denna separata rapport bevarar dem utan dokumentändringar i det tidigare arbetet.

## Funktion och placering

Två labels skapas en gång och använder befintliga `focus_state`. Ingen ny
timer, seriell trafik eller companionfunktion tillkommer. Båda visar samma
lokala tid, avrundad uppåt till hel sekund, exempelvis `FOKUS 04:59` eller
`PAUS 00:59`. ` ||` visar pausad timer i båda faserna; tiden förblir fryst.
Idle, Prepared/nollställd och Completed döljer raden. Fasbyte ger pausens
nya tid direkt, och avslutad paus lämnar ingen gammal nedräkning.

| Vy | Ruta x, y, bredd, höjd | Stil |
| --- | --- | --- |
| Bongo | 153, 25, 82, 11 px | Högerjusterad under klockan, Montserrat 10, `0x747B84` |
| Spelare | 79, 15, 82, 11 px | Centrerad under brand/källraden, Montserrat 10, `0xC7CCD2` |

`RAM: 100%` med faktisk Unscii 16 upptar x5–149, y25–42; fyra pixlar
skiljer statistikens ruta från nedräkningen. Spelarens header upptar y4–15,
omslagsrutan börjar vid y26. Nedräkningen har ingen rektangelöverlappning
med dessa. Katten, omslagsboxen, statistik, titel och touchkontroller är
orörda. Längsta texten över alla tillåtna sekunder och båda pausade faserna
är 81 px enligt aktuella LVGL-glypher och kerning, inom labelns 82 px.

Efter Leads layoutbeslut är endast **Spelarens kompakta fasslutssignal**
ändrad från 70×22 till 70×14 px vid x85,y0. Dess 11 px textrad ryms och
har en pixels mellanrum till nedräkningen vid y15. Text, kvittering och
tidsförlopp är bevarade; Bongo/övriga paneler och stora signaler är
oförändrade. Stora övergående signaler täcker fortfarande headern avsiktligt.

En gemensam 24-byte textbuffert har samma livstid som båda labels och lånas
med `lv_label_set_text_static()`. Cachen skriver om texten endast när
visad sekund, fas eller pausläge ändras; synlighet ändras vid tillståndsbyte.
Labels saknar CLICKABLE/SCROLLABLE. Ingen återkommande `String` eller
textbuffertallokering införs. Den befintliga huvudloopen driver uppdateringen.

## Kandidat

| Fält | Värde |
| --- | --- |
| Arbetsyta | `D:\DEV\Ai\Github\Bongo-Cat-Screen` |
| Bas | `codex/runtime-artwork-speed`, HEAD `a2cf99812ac0abb451fb3c4e946cd489ceee85ce` + bevarat tidigare arbete |
| Miljö | `esp32-024r-spotify-fastserial` |
| Drift / flash | 230400 / 115200 baud |
| Fryst app | `.pio/candidates/focus-countdown-BD666797.bin` |
| Adress vid eventuell appflash | `0x10000`; ingen fullbild/NVS-skrivning |
| Appfilens storlek | 926976 byte |
| SHA-256 | `BD666797A9430D95681C47A3CAF9E8E5B313CD3DE2D613BC0051E4CAAEB70EB5` |
| Statisk bygg-RAM | 112056 / 327680 byte, 34,2 % |
| Bygg-flash | 926241 / 1966080 byte, 47,1 % |

Bygg-RAM är inte en mätning av fri/minsta runtime-heap. Det frysta appbygget
och källornas hash finns även i `build/focus-countdown-2026-10-12/candidate.json`.
Praktisk rollback är firmware `6A5366C1E56E1137AEBC08E6675CBB12E1A49AE106D2DBD03B30132C6A7D2302`
och companion `68CC5BC1D90E0AB734D0997D03980653858C717F88AB4B97E42648E6DC93FE97`.

## Kod- och filverifiering

- `python -m platformio run -e esp32-024r-spotify-fastserial`: **SUCCESS**.
  Befintliga TFT_WIDTH/TFT_HEIGHT-omdefinitionsvarningar finns kvar.
- `python -X utf8 -m unittest discover -s tests -p test_focus_countdown.py -v`:
  **3 kontroller passerade, 1 uttryckligen överhoppad**. Faktiska fontmått,
  alla sekunder upp till 120/30 minuter inklusive pausmarkör, verkliga
  kollisionsfall, 240×320-bilder och aktuella käll-/bildhashar verifieras.
- `tests/focus_countdown_test.cpp` kompilerad med befintlig Xtensa GCC,
  `-std=gnu++14 -Wall -Wextra -Werror`: godkänd. Sju `static_assert` verifierar
  synlighet, ceil vid sekund-/minutgräns, båda pausade faser, oförändrad
  visningsnyckel inom samma sekund, fas-/pausändring samt fasslut/hide.
- Hela befintliga `tests/focus_logic_compile.cpp` kompilerad med samma
  varningsflaggor: godkänd; det är kompilering och konstantevaluering.
- **C++ runtime-testet är inte kört.** Den lokala MSVC-installationen saknar
  `vcvarsall.bat` och C++-headers. Ingen hostverktygskedja har installerats
  eller reparerats. Testet finns för en komplett normal hostkompilator och
  provar faktisk formatter/cache, båda pausade faser, wrap/phase/reset samt
  de två verkliga UI-adapterfunktionerna med en LVGL-anropsrecorder.
- `git diff --check`: inga whitespacefel. Befintlig LF/CRLF-notis för
  `companion/settings-view.ps1` påverkar inte kontrollens resultat.
- Alla 15 tidigare ocommittade filer verifierade med SHA-256: oförändrade.

## Flashning hos Lead

Lead rapporterade 2026-10-12 att den tidigare appen först lästes tillbaka
från COM6 vid 115200 baud, `no_reset/no_reset`, adress `0x10000`.
Backupen `.pio/device-backups/focus-countdown-20261012-preflash-app-0x10000-6A5366C1.bin`
är 926432 byte med SHA-256
`6A5366C1E56E1137AEBC08E6675CBB12E1A49AE106D2DBD03B30132C6A7D2302`,
identisk med rollback-appen. Kandidaten BD666797, 926976 byte, skrevs sedan
enbart vid `0x10000` på COM6 vid 115200 baud. esptool 4.9.0 verifierade
skrivningen med `Hash of data verified`; flashningen tog 37,9 sekunder.
NVS är orörd enligt Lead och companion 68CC5BC1 bevarad.

Backup- och kandidatfilernas storlek/SHA-256 är även kontrollerade lokalt
av Kodskrivaren. Detta verifierar filerna och den rapporterade skrivningen;
det är **inte slutacceptans av gränssnittet**. Lead har därefter rapporterat
färsk uppstart och begränsade efterprov enligt nedan.

## Förhandsbilder

Genereras med:

```text
python tools/export_ui_visuals.py --focus-countdown --output visuals/focus-countdown
```

14 exakta 240×320 PNG-filer i `visuals/focus-countdown/composed/`: Bongo och
Spelare med fokus, pausfas, pausad fokus, pausad pausfas, inaktiv/dold rad,
120 minuter pausad med RAM 100 % samt kompakt PAUS-signal och nedräkning.
Kontaktkarta: `visuals/focus-countdown/contact_sheet_composed.png`.
`manifest.json` innehåller rutor, bildhashar och aktuella källhashar.

Detta är **simulation**, inte fotografi eller hårdvarubevis. Header,
statistik/klocka och countdown använder LVGL:s faktiska ASCII-glyphbitmappar,
advance och kerning. Övrig typografi/kanter approximeras med Pillow. Omslaget
är syntetiskt DEMO-material; timing, touch, LCD och verklig överföring ingår
inte i bilderna. Historiska bilder i `visuals/composed/` har inte skrivits över.

## Fysisk jämförelse – före ändringen

Lead rapporterade nedan från gamla 6A53, oförändrad companion 68CC5BC1,
230400 baud och ingen PSRAM. Användaren bekräftade jämn text/skiva och
responsiv touch under art2. CPU-estimatorn var avstängd i firmware;
ingen CPU-procent eller uppmätt FPS/touchlatens finns att jämföra.

| Art2-start, Stockholm 2026-10-12 | Sändning | ACK efter sändning | Heap under överföring | Minsta heap sedan boot |
| --- | --- | --- | --- | --- |
| 16:28:06.658 | 5061 ms | 27 ms | 182296 byte vid 16:28:07.167 | 178456 byte |
| 16:28:41.152 | 5030 ms | 20 ms | 182288 byte vid 16:28:42.579 | 178456 byte |
| 16:28:48.072 | 5032 ms | 8 ms | 182296 byte vid 16:28:51.647 | 178456 byte |
| 16:28:55.449 | 5188 ms | 83 ms | 182288 byte vid 16:28:56.688 | 178456 byte |

Fri heap efteråt var 182288 byte. Före-sessionens uptime var cirka
3312–3423 sekunder. Minsta heap är ett bootminimum och påverkas av
sessionens tidigare arbete; före/efter är inte en isolerad minnesbenchmark.
ACK-tiden är protokollkvittens, inte touch- eller renderlatens.

## Fysisk jämförelse – efter ändringen

Lead rapporterade efterdata på installerad BD666797 och oförändrad
companion 68CC5BC1, fortsatt 230400 baud. Färsk statusfil 2026-10-12
16:49:14.736 (Stockholm), uptime 24 s, visade fri heap 182012 byte,
total heap 262160 byte och minsta heap 181144 byte. Ett gammalt sample
med uptime 4251 s direkt vid companionstart var stale och är **uteslutet**.
Art2-capability bekräftades 16:49:05.965. De första två omslagen efter boot
använde legacy-protokollet och ingår **inte** i art2-jämförelsen.

| Art2-start, Stockholm 2026-10-12 | Sändning | ACK efter sändning | Heap under överföring | Minsta heap sedan denna boot |
| --- | --- | --- | --- | --- |
| 16:49:21.907 | 5186 ms | 8 ms | 181984 byte vid 16:49:23.026 | 181144 byte |
| 16:52:12.715 | 5359 ms | 30 ms | 181788 byte vid 16:52:13.326 | 178344 byte |
| 16:52:27.352 | 5250 ms | 18 ms | 181804 byte vid 16:52:28.465 | 178028 byte |

Från 16:52:53 till 16:53:33 låg fri heap stabilt på 181668 byte och minsta
heap på 177912 byte. Jämfört med före-sessionens eftervärde 182288/min178456
är detta 620 byte mindre fri heap och 544 byte lägre bootminimum. Rapporterad
total heap är 184 byte mindre än före-sessionens 262344 byte. Sessionerna
har olika bootålder och tidigare UI-/mediearbete; skillnaderna visar inte
isolerad kostnad för labels eller ett konstaterat minnesläckage.

Före-sändningarna låg på 5030–5188 ms och efter-sändningarna på 5186–5359 ms.
Det lilla, okontrollerade urvalet bevisar ingen förändrad överföringsprestanda.
Användaren bekräftade aktiv rad på båda vyerna utan täckning samt pausad
Fokus med `||` och återupptagning. Rätt omslag och jämn text/skiva/touch
bekräftades med ”Japp”. Det är kvalitativ evidens, inte uppmätt FPS/touchlatens.

I ett senare svar bekräftade användaren även DJ-svep, meny och dold rad
efter nollställning med ”Ja”. För pausfas, pausad pausfas och Completed-hide
svarade användaren först ”Återkommer”. Vid senare prov av 8BB91836 sade
användaren ”Den gjorde de på förra, återkommer här också”. Lead anger detta
som retrospektiv bekräftelse av BD:s tre tillstånd. Exakta tider tillkommer
inte, och motsvarande prov på 8BB91836 är fortfarande väntande.

Samtidigt sade användaren ”de märks att du inte kollade ui” och förtydligade
att utseende, placering och storlek ska ändras med befintliga bilder som
underlag. De positiva funktionsobservationerna är **inte** ett godkännande
av den visuella lösningen. UI-chatten tar fram en konkret 240×320-design
för båda vyerna; Code2 implementerar efter Lead-granskning. BD666797 behålls
fryst tills designspecifikationen kommer, utan parallell redesign här.
UI-ändring krävs före leverans och slutacceptans är öppen.

## Återstående fysiskt prov och UI-granskning

Efter de begränsade proven behöver Lead:

1. Granska UI-chattens konkreta design för utseende, placering och storlek,
   därefter låta Code2 implementera den och prova den nya kandidaten.
   120 minuter + pausmarkör och lång källrubrik är bara simulerat granskade.
2. BD:s pausfas, pausad pausfas och Completed-hide har fått retrospektiv
   användarbekräftelse enligt Lead. Prepared-hide var redan bekräftat på BD.
   Motsvarande återstående prov för 8BB91836 redovisas i dess separata rapport.
3. Slutföra de övriga gestproven, exempelvis Bongo-bonk och Spelarens flera
   tap/mediesvep, samt kontrollera regression efter designändringen.
   DJ-svep och meny är bekräftade på BD666797; detta täcker inte varje gest.

**Ovanstående kriterier och slutacceptans är väntande.**

## Nya ändringar jämfört med sparad bas

- `src/bongo_cat_featured.inc`: två labels, delad cache/uppdatering,
  endast kompakt Player-signals höjd.
- `src/focus_countdown.h`: ren visningsnyckel och fast formatter/cache.
- `tools/export_ui_visuals.py`: aktualiserade headerfontmått och separat export.
- `tests/focus_countdown_test.cpp`, `tests/test_focus_countdown.py`: avgränsade prov.
- `visuals/focus-countdown/`: 14 PNG, kontaktkarta och manifest.
- Denna rapport. Bygg-/bas-/kandidatfiler finns i ignorerade `build/` och `.pio/`.

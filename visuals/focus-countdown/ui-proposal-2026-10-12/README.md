# Fokus-nedräkning: UI-förslag 2026-10-12

Detta ersätter UI-specialistens tidigare preliminära förslag. Det är ett
granskat **designförslag med 240×320-simulationer**, inte aktuell firmware,
fotografi eller ett fysiskt acceptansprov. Code2 implementerar firmware
efter Leads beslut. Inga befintliga källfiler har ändrats av förslaget.

## Vald utformning

Bongo använder samma normala `lv_font_unscii_16` som klockan för tiden.
Ett litet fasnamn i `lv_font_unscii_8` ligger ovanför, båda högerjusterade.
Det ger sammanhållen pixeltypografi och tydliga siffror utan en ny ruta,
kortpanel eller färgad bakgrund. Fullständiga FOKUS/PAUS kan behållas.
Förslaget använder inte den testade, för smala komprimerade pixelvarianten.

Spelaren har en kompakt grupp centrerad kring x120: litet fasnamn i sin
befintliga Montserrat 10, större ljusa siffror samt separat pausmarkör.
Det behåller Spelarens typografi och ger tiden större vikt än fasnamnet.
Gruppen håller sig i det befintliga utrymmet mellan header och omslag.

| Del | Exakt kontrollruta x,y,b,h | Typsnitt / stil / justering |
| --- | --- | --- |
| Bongo, fas | 171,28,64,9 | Unscii 8, `505860`, höger |
| Bongo, tid | 139,44,96,17 | Unscii 16, `303840`, höger |
| Player, fas | 68,15,36,11 | Montserrat 10, befintlig `focusAccentHex()` (här `1ED760`), mitten |
| Player, tid | 109,15,48,11 | `focus_digits_14_tight`, `E6EBEF`, mitten |
| Player, pausmarkör | 163,17,7,7 | Två 2×7 px staplar vid x163 och x168, `E6EBEF` |

Tiden är fortsatt `MM:SS` eller `120:00`. Bongo visar `FOKUS`, `PAUS`,
`FOKUS ||` eller `PAUS ||` på fasraden. På Spelaren står samma fasnamn
och en separat `||`-markör. Pausmarkören visas bara när timern är fryst,
oberoende av om musik spelas. Pausfas och pausad timer är skilda tillstånd.

Under Spelarens befintliga kompakta PAUS-notis försvinner det duplicerade
fasnamnet: notisen anger fasen och tiden centreras vid x120. Dess tidsruta
är då 96,15,48,11; pausmarkören ligger vid x147 och x152, y17, 2×7 px.
Ingen timerinformation döljs. Notisen själv flyttas inte eller ändrar funktion.
Den befintliga stora övergående fasnotisen får fortsatt täcka headern.

## Det större Player-typsnittet

`focus_digits_14_tight` är ett **separat sifferdeltypsnitt**, inte en ändring
av projektets vanliga Montserrat 14. Det använder de oförändrade verkliga
LVGL-glyphbitmapparna, advance och kerning från Montserrat 14 för `0–9` och
kolon, med line-height 11 och base-line 1. Dessa glypher är högst 10 px höga
och har ofs_y=0; de får därför plats i y15–25 med en tom sista pixelrad.
Det ger 10 px höga siffror, jämfört med kandidatens 7 px.

`font-player.json` beskriver exakt fontdata och mått för renderingen.
Endast siffror och kolon ska användas i den kompakta firmwarefonten;
andra glypher i referensdata är inte godkända för dessa radmått. Code2 får
generera ett separat statiskt LVGL-subset för dessa tecken. Ingen fontfil
i `.pio/` ska ändras. Unscii 8 finns i LVGL men är avstängt i aktuell
`lv_conf.h` och behöver aktiveras om detta Bongo-förslag implementeras.

## Utrymme och bevarande

Klocka, CPU/RAM/WPM, katt, omslag, låttext och touchytor har inte flyttats.
RAM 100 % slutar vid x149; fasraden börjar vid x171. Den största tidens
96 px börjar vid x139 först på y44, efter RAM-radens slut y42.
WPM 200 slutar vid x133 och lämnar 6 px till den största nedräkningen.
Det befintliga companionintervallet är 0–200 WPM; även andra tresiffriga
värden har samma bredd. Godtycklig serialtext utanför den kontrakten är
inte ett nytt garanterat layoutfall.

Player-gruppen börjar vid y15, efter headerns y4–15 och den kompakta
notisens y0–14. Den slutar före omslagets y26. Numeriska glypher är högst
46 px breda över alla sekunder i 120 minuter, inom den 48 px breda rutan.
Pausfas upp till 30 minuter ryms också. Längre källrubrik och DJ är med
i förhandsbilderna; nedräkningen ligger på en separat rad.

Rendereraren kontrollerar alla giltiga tidsbredder och varje ritad
glyphruta mot skyddade header-/statistik-/omslags-/notisrutor. Alla 16
bilder är exakt 240×320. Den är läst och granskad i originalstorlek.
Övriga element använder projektets befintliga simulerade exporterare;
fontkontroller är inte ett fysiskt LVGL-/LCD-bevis.

Lokal Fokus-state, fasbyte, avrundning, fryst paus, hidden vid Idle,
Prepared/nollställning och Completed ska bevaras. Fortsatt cache på
visad sekund/fas/paus; nya labels och textbuffertar skapas en gång.
Inga touchflagor, gester, serialpaket, companionfunktioner eller nya
timers tillkommer. Synlighet/placering av Player-fasnamnet uppdateras
bara vid notisens tillståndsbyte, inte varje bildruta.

## Bilder

- `bongo-focus.png`, `player-focus.png`: vanlig aktiv fokusfas.
- `bongo-long-paused.png`, `player-long-paused.png`: 120:00, pausad,
  CPU/RAM 100 % och WPM 200 på Bongo.
- `*-break.png`, `*-break-paused.png`, `*-focus-paused.png`: båda faser
  och tydlig fryst timer.
- `*-idle.png`, `*-cue.png`, `*-dj.png`: dold, fasnotis, DJ/lång källa.
- `contact-sheet.png`: samtliga 16 bilder.
- `manifest.json`: käll-/font-/bildhashar och exakta glyphrutor.

Reproduktion från projektroten:

```powershell
python -B visuals/focus-countdown/ui-proposal-2026-10-12/render_proposal.py
```

Före leverans ska Code2 skapa native LVGL-fonten och synka firmware,
tester och förhandsbilder. Lead granskar samma frysta kandidat och gör
det redan begärda fysiska provet av läsbarhet, tillstånd, gester,
omslag och heap/jämnhet. Detta förslag gör ingen build eller flash.

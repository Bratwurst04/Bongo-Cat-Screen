# Integrerad Fokus-status – slutligt UI-förslag

Denna enda utformning ersätter det tidigare `ui-proposal`-förslaget och
8BB91836-presentationen. Förslaget gäller den nya Fokus-statusen på Bongo
och Player; Code2 implementerar efter Leads granskning. Detta är en design
med exakta 240×320-simulationer, inte firmware eller ett fysiskt prov.

## Visuell riktning och motivering

På Bongo är statistik och klocka svart pixeltypografi. Fokus följer samma
typsnitt med ett **fullt läsbart fasnamn**, en tydligt sammanhörande tid
under och en separat pausmarkör efter fasnamnet. Fasnamn och tid får
mörka neutrala toner så att den svarta väggklockan behåller första vikt.
En diskret pixel-linje skiljer gruppen från WPM även vid 200 WPM.

Fasen flyttas från y28 till y42 och tiden från y44 till y63. Den större
fastexten börjar efter RAM-raden; tiden får egen rad efter statistiken
i stället för att se ut som en fortsättning på WPM. Gruppen är fortfarande
under klockan och helt ovanför kattens canvas. Statistik, klocka och katt
flyttas inte, och statistikens innehåll/format ändras inte.

På Player blir Fokus en liten centrerad **statuspanel** med samma mörka
yta, kant, rundning, accent och vanliga Montserrat-typsnitt som befintlig
låtpanel och Fokus-/menykomponenter. Fas, återstående tid och paus hör
ihop i en stabil grupp med verkliga insets. Inga beskurna sifferfonter
eller små reservrutor används som designmål.

När Fokus pågår blir omslagets cirkel 144×144 vid y54, mot tidigare
172×172 vid y26. Det frigör 28 px vertikalt för statusen. Header till
status har 5 px och status till omslag 8 px. Cirkelns nederkant ligger
kvar på y198, så låtpanel, tidslinje och uppspelningsstatus ligger kvar.
Det är en cirka 16 % mindre cirkel under ett aktivt pass, inte ett mindre
överfört omslag. När statusen döljs återgår cirkeln till ordinarie 172 px.

## Bongo: exakta mått

Alla mått är x,y,bredd,höjd; alla nya objekt är inerta och transparenta.

| Del | Ruta | Stil |
| --- | --- | --- |
| Fas | 139,42,80,17 | `lv_font_unscii_16`, `0x505860`, vänsterjusterad |
| Tid | 139,63,96,17 | `lv_font_unscii_16`, `0x40484F`, högerjusterad |
| Paus, stapel 1 | 224,45,3,11 | `0x505860` |
| Paus, stapel 2 | 230,45,3,11 | `0x505860` |
| Statistikavskiljare | 135,42,1,38 | `0xD5D9DE` |
| Kompakt fasnotis, understrykning | 139,60,96,2 | `focusAccentHex()` |

Fastext är `FOKUS` eller `PAUS`, utan `||` i textbufferten. Staplarna
anger fryst timer i båda faserna. Tiden är `04:59`, `00:59` eller
`120:00`, fortsatt avrundad uppåt till visad sekund.

RAM 100 % har ruta 5,25,144,17 och slutar på y42. WPM 200 har bredd
128 vid x5 och slutar på x133. Gruppen börjar till höger därom, och
den största tiden är nedanför statistikens y62. Tiden slutar på y80;
kattens fulla canvas börjar på y82. Kontrollen skyddar hela canvasen,
inte bara kattkonturen i ett exempel. Ingen ny statusdel täcker katten
eller något statistikfält. WPM-kontraktet är fortsatt companionens 0–200.

## Player: exakta mått

| Del | Ruta | Stil |
| --- | --- | --- |
| Statuspanel | 40,20,160,26 | Bakgrund `0x15191E`, kant `0x292E35` 1 px, radie 10, padding 0 för explicita barnmått |
| Fas | 52,25,52,16 | `lv_font_montserrat_14`, `focusAccentHex()`, centrerad |
| Tid | 112,24,56,18 | Vanliga `lv_font_montserrat_16`, `0xF2F4F7`, centrerad |
| Paus, stapel 1 | 176,28,3,10 | `0xF2F4F7` |
| Paus, stapel 2 | 182,28,3,10 | `0xF2F4F7` |
| Omslagscirkel med aktiv status | 48,54,144,144 | Befintlig cirkelstil, radie 72 |
| Omslagscirkel när statusen är dold | 34,26,172,172 | Befintlig cirkelstil, radie 86 |

Fastext är `FOKUS` eller `PAUS`. Pausmarkören visas bara när den lokala
Fokus-timern är fryst; musik kan samtidigt spela normalt. Alla faser och
pauslägen har samma mått. Längsta sifferraden över samtliga tillåtna
sekunder är 54 px, inom den 56 px breda tidsrutan.

Art/DJ-transformer ändras **bara när Fokus-statusens synlighet växlar**:

| Visning | Status synlig | Status dold |
| --- | --- | --- |
| RGB-omslagsbild, LVGL-zoom | 320, alltså 112→140 px | 384, alltså 112→168 px |
| DJ-canvas, LVGL-zoom | 560, alltså 64→140 px | Befintliga 672, alltså 64→168 px |

Återanvänd samma bild/canvas, centrum, metadata och bildbuffertar.
Överförd 112×112-bild, CRC/kvittens/cache och protokoll ändras inte.
Alla vägar som återställer zoom, inklusive nytt omslag/DJ-byte, måste
använda aktiv layout så att ett låtbyte inte gör cirkeln för stor igen.
Gester gäller samma befintliga panel och ingen ny statusyta tar touch.

## Fasnotis och synlighet

Stora befintliga fasnotiser, tidsförlopp, LED och kvittering behålls.
När en befintlig kompakt FocusDone-notis visas på Bongo/Player integreras
dess visuella signal i den redan synliga statusen:

- Bongo: accentunderstrykningen i tabellen visas. Fas och tid flyttas inte.
- Player: panelen får `focusDarkAccentHex()` som bakgrund och
  `focusAccentHex()` som kant. Fas, tid och pausmarkör ligger kvar.
- Den gamla fristående kompakta PAUS-badgen ritas inte samtidigt på dessa
  två vyer. Därmed täcks inte CPU/klocka och ingen fastext dubbleras.
- Notisens befintliga livstid och kvittering styr även denna markering.
  Andra panelers notisdesign ändras inte. Ingen ny animation krävs.

Running och Paused visar status i båda faserna. Idle, Prepared/nollställning
och Completed döljer hela gruppen och återställer Player-layouten.
Fasbyte eller paus/fortsätt flyttar inte innehåll. Bildlayout ändras aldrig
per sekund eller som följd av Spotify-aktivitet.

## Implementerings- och verifieringsgräns

Använd standardfonterna som redan är aktiverade. Det tidigare kompakta
sifferfont-adaptern behövs inte för den här statusen. Behåll lokalt
focus_state, ceil-regeln, cache på sekund/fas/paus och engångsskapade
labels/statiska textbuffertar. Använd befintlig cue-state för markeringen.
Ingen ny timer, serialtrafik, companionkod, gesture eller menydesign.

`render_design.py`, 14 PNG och `manifest.json` i samma mapp är referens.
Alla tidsbredder upp till 120/30 minuter och samtliga ritade rutor mot
skyddade områden kontrolleras. Hela normal-, lång/pausad-, cue-, idle-,
DJ/långkälla- och cyan-vyer har visuellt granskats i 240×320.

`comparison.png` jämför detta förslag med source-derived 8BB-bilder,
inte fotografier. `contact-sheet.png` visar alla nya tillstånd. Bilden
och annan mediastil är simulerade; glypher och fontmått är verkliga LVGL.

Code2 synkar firmware och preview med dessa konkreta mått och verifierar
även nytt omslag, DJ-byte, active→idle och cue-övergång utan fel zoom eller
gammal markering. Lead gör det begärda fysiska läsbarhets-, funktions-,
gesture-, art2-/heap- och jämnhetsprovet på samma frysta kandidat.

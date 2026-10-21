# Player: liten träffyta för sökning ±15 sekunder

Förslaget gäller låtens nedre progressbar/tidsetiketter. F406:s godkända
utseende, övre Fokus-status/taps och övriga vyer behålls.

## Rekommenderad startyta

**Halvöppna skärmmått: x16, y262, bredd210, höjd31.**
Det betyder x16–225 och y262–292 inklusive. Befintlig inclusive
`TouchRect` får `{16, 262, 225, 292}`. Ingen synlig ram eller större
kontroll läggs till; orange i bilden är bara granskningsöverlägg.

| Faktisk del | Externa skärmmått |
| --- | --- |
| Låtpanel | 8,205,224,90; 1 px border, padding 0 |
| Progressbar | **19,264,204,6**, slut x223/y270 exklusivt |
| Tid till vänster | x19, y278, automatisk textbredd, höjd11 |
| Tid till höger | Högerkant x221 exklusivt, y278, automatisk bredd, höjd11 |
| Artistlabel | 19,238,204,16, slut y254 exklusivt |
| PLAYING/PAUSED/NO MEDIA | 8,300,224,16 |

LVGL lägger panelens 1 px border till child-positionerna. Progressbarens
child(10,58) blir alltså (19,264), och tidslabels child-y72 blir y278.
Högerjusterad tid använder panelens innehållsbredd 222 px och slutar x221.
`lv_font_montserrat_10` har faktisk line height 11; tiden slutar y289.

Startytan har **2 px marginal ovanför stapeln och 23 px under dess slut**,
inklusive tidslabels och 4 px under dem. Sidomarginalerna är 3 px. Det ger
en 31 px hög yta runt just tidsdelen. Artisten har 8 px luft till ytan;
PLAYING har 7 px luft från ytans slut. Rutan ligger helt innanför panelen
och tar inte artist, titel, omslag eller övre Fokus-träffruta 36,16,168,37.

## Gestens ägare och riktning

- Gesten måste **börja** i startytan på Player med menyn stängd. Sökning
  ska vara möjlig när en giltig låt/position finns; Code hanterar stödet.
- Ett fullbordat kort horisontellt svep höger ger **+15 s**, vänster **−15 s**,
  en gång vid release. Befintlig rörelsetröskel och tydlig horisontell
  dominans avgör svepet; inga nya UI-knappar eller långtryck krävs.
- Startytan äger ett giltigt horisontellt svep fram till release.
  Release behöver inte vara innanför dess vänster-/högerkant. Annars
  skulle vänstersvep från vänstra tidslabeln vid x19 lätt avbrytas. Detta
  förstorar inte start-hitboxen. Slutpunkten behöver inte heller klara
  ett nytt point-in-rect-prov; använd befintlig axeldominans/rörelsetröskel
  för att skilja svep från vertikal eller tvetydig dragning. Ingen sådan dragning ska omtolkas
  till sökning; Code ansvarar för central gesture arbitration.
- Ett vanligt korttryck utan svep behåller den befintliga mediavägen.
  Vertikala svep och långtryck behåller skiv-/DJ-/menybeteendet. Svep
  som börjar utanför tidsytan behåller befintlig NEXT/PREVIOUS-routing.
  Giltig sökning får inte samtidigt skicka NEXT/PREVIOUS/play/pause.
- Panelbyte/meny/avbruten gesture ger ingen försenad seek. Fokus-statusen
  har separat träffyta och behåller sina redan godkända tryck och svep.

På den befintliga stående touchmappningen är **raw X skärm-Y**, medan
raw Y är omvänd skärm-X. Skärmhöger betyder raw_y minskar → +15 s;
skärmvänster betyder raw_y ökar → −15 s. Befintliga kalibreringsgränser
och trösklar återanvänds; denna spec ändrar inte touchmappningen.

## Underlag och avgränsning

`player-seek-overlay.png` är 240×320. `player-original.png` är en exakt
kopia av den tidigare godkända source-derived F406-bilden; `touch-map.png`
visar dem sida vid sida. Inga äldre snapshots eller firmware-/companion-
källor ändras. Nuvarande metadata-rendering i basbilden är approximativ;
de normativa rutorna ovan kommer från faktisk LVGL-geometri med border.

`render_preview.py` skriver bara denna nya mapp. Det verifierar bar/tiders
mått och att startytan ligger inom låtpanelen utan skyddade överlapp.
Skyddade bildregioner är oförändrade även i granskningsöverlägget.
`manifest.json` innehåller geometri och hashvärden. Detta är en
ergonomirekommendation; Code äger funktion och Lead nästa fysiska prov.

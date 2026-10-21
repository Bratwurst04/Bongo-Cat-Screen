# Bongo: Fokus som en fjärde textrad

Ett Bongo-only förslag efter faktisk återkoppling på installerade UI3
08A78748. Player är fysiskt godkänd och lämnas helt orörd.

Statusen blir en vanlig fjärde rad under CPU, RAM och WPM och kan tryckas
för att pausa/fortsätta den lokala timern. Samma svarta
`lv_font_unscii_16`, samma vänsterkant x5 och samma 20 px radavstånd:
y5, y25, y45, **y65**. Kolon efter fasnamnet följer statistikens skrivsätt.
Fas och tid ligger på samma baslinje och läses som `FOKUS: 04:59`.
Tiden är en del av raden, utan en egen stor klocka eller komponentgrupp.
Ingen grå ton, avskiljare, bakgrund, kant eller understrykning används.

## Exakta externa mått

Mått är x,y,bredd,höjd. Alla labels är vänsterjusterade, transparenta,
inerta och använder oförändrade `lv_font_unscii_16`, line height 17.

| Del | Ruta | Text och stil |
| --- | --- | --- |
| Fas med kolon | 5,65,96,17 | `FOKUS:` eller `PAUS:`, svart `0x000000` |
| Återstående tid | 117,65,96,17 | `04:59`, `00:59`, `120:00`, svart `0x000000` |
| Paus, stapel 1 | 221,69,3,11 | Svart `0x000000`, bara när lokal timer är fryst |
| Paus, stapel 2 | 227,69,3,11 | Svart `0x000000`, samma regel |

Fasfältets kolon följs av 16 px mellanrum till tidsfältet. Tiden har
samma fasta x117 i båda faserna, även vid 120 minuter; de två staplarna
flyttas inte när sekunder eller fas ändras. Normal `04:59` använder 80 px;
`120:00` använder hela 96 px och slutar x213. Därefter finns 8 px till
pausmarkören. Högersta stapeln slutar x230 och lämnar 10 px till skärmkant.
`PAUS:` är 80 px och får ett naturligt större mellanrum före samma tidkolumn.

CPU/RAM 100 %, WPM 200 och väggklockan har samma innehåll, placering,
typsnitt och färg som tidigare. WPM-kontrollen slutar y62. Den nya raden
börjar y65 och slutar y82 exklusivt, precis före kattens fulla transformerade
canvas som börjar y82. Rutorna överlappar inte. Faktiska textpixelrader
har samma luft som de befintliga statistikraders 20 px rytm. Katten och
dess canvas flyttas eller beskärs inte.

## Tillstånd och befintlig fasnotis

- Running och Paused visar raden i både fokus- och pausfas. Fasnamnet
  beskriver passet; de två separata staplarna beskriver en fryst timer.
- Idle, Prepared/reset och Completed döljer hela raden och staplarna.
  Den befintliga Bongo-vyn återkommer exakt.
- Under den befintliga **kompakta FocusDone-notisen på Bongo** får bara
  fasnamnet med kolon tillfälligt `focusAccentHex()`. Tiden och staplarna
  förblir svarta och inget flyttas. När notisen upphör återgår fasen till
  svart. Detta ersätter UI3:s Bongo-understrykning; ingen ny linje skapas.
- Den gamla fristående kompakta PAUS-badgen förblir dold när notisen
  integreras i den synliga Bongo-raden. Stora notiser, livstid, LED,
  kvittering och andra panelers presentation behålls.

Normalstatusen använder enbart Bongo-vyns svarta pixeltypografi.
Notisens korta färgskifte finns i samma fastext och använder projektets
befintliga accent. Det ger fortsatt synlig återkoppling utan en extra ruta
eller ett andra fasnamn; bilder finns i både grön och cyan accent.

## Tryck för att pausa/fortsätta

Träffrutor är x,y,bredd,höjd, med höger/nederkant exklusiv. De finns bara
när statusen är synlig och rätt panel visas. Inga synliga touchramar tillförs.

| Vy | Aktiv träffruta | Motivering |
| --- | --- | --- |
| Bongo | **5,62,230,20** | Täcker hela fas/tid/paus-raden och all fri höjd mellan WPM och full kattcanvas |
| Player | **36,16,168,37** | Godkänd panel 40,20,160,26 plus 4 px åt sidorna/uppåt och 7 px nedåt |

Bongos träffruta börjar där WPM-kontrollen slutar och slutar där
kattcanvasen börjar; CPU/RAM/klocka ligger ovanför. Player-träffrutan har
minst 1 px mellanrum till headern som slutar y15 och till aktivt omslag som
börjar y54. Den når inga metadata-, transport- eller andra kontrollområden.
Den inaktiva Player-cirkeln behöver ingen marginal eftersom statusen då
är dold och hela träffrutan avstängd. `touch-map.png` visar enbart en
granskningsöverlagring; orange färg ingår **inte** i produkten.

Ett **enkeltryck** i aktiv ruta växlar lokal `Running` ↔ `Paused` i samma
fas och stannar i samma vy. Befintliga två staplar visas direkt i pausat
läge och försvinner vid fortsätt. Ingen Spotify play/pause, bonk eller
annan vanlig tryckåtgärd ska utlösas samtidigt. Statusens Running-läge
behåller det enkla utseendet; inga nya knappar eller textrader krävs.

Code2 använder central gesture arbitration: först ett fullbordat
enkeltryck utan att det blivit ett befintligt svep eller långtryck får
växla timern. Svep och långtryck som startar i rutan fortsätter till
ordinarie navigation/panelmeny och växlar inte timer. Vanliga tryck/gester
utanför rutan behåller sitt beteende. Använd befintliga trösklar; inga
nya generella gesture-regler. Dold/inaktiv status ger ingen träffruta.

Bongos 20 px höjd är den största möjliga under de frysta skyddade måtten;
bredden är 230 px. Den är en faktisk begränsning, inte ett 44 px fingermål.
Lead ska särskilt verifiera att raden är lätt att träffa på enheten. En
högre ruta kräver en annan Bongo-layout eller intrång i skyddad canvas.

## Avgränsad implementation för Code

Återanvänd Bongo-labels och pausobjekt, ändra deras mått/färg/position och
lägg kolon i **Bongos** fastext. Använd två statiska strängar `FOKUS:` och
`PAUS:`; ändra inte Player-texten eller dess cachekontrakt. Ta bort eller
permanent dölj Bongo-divider och Bongo-cue-line. Befintlig integrerad
cue-state styr i stället Bongos fasfärg; återställ svart vid cue slut,
panelbyte eller dold status. Ett temabyte under aktiv Bongo-cue uppdaterar
fasfärgen till aktuell accent. Ingen ny animation, timer eller serialtrafik.

Behåll ceil-regeln, sekund/fas/paus-cache, statiska tidsbuffertar och
engångsskapade objekt. Ändra inte Player, omslags-/DJ-mått eller zoom,
albumöverföring/cache/CRC, meny eller Fokuslogik. Enda nya gesturebeteendet
är det ovan explicit auktoriserade enkeltrycket på synlig status; befintliga
gester prioriteras som beskrivet. Delade helpers
får inte ändra den godkända Player-presentationen.

## Bilder och verifiering

`render_design.py` skriver endast i den här mappen och läser befintliga
spritebilder samt de faktiska LVGL-glypherna. Åtta kompletta 240×320-bilder
visar normal Focus, Focus fryst, 120:00 fryst/maxstatistik, aktiv pausfas,
fryst pausfas, grön fasnotis/fryst/maxstatistik, cyan fasnotis och idle.
`before-after.png` jämför original Bongo, installerade UI3:s simulering och
det här enda förslaget. `contact-sheet.png` visar alla tillstånd.

Alla tillåtna tider 0–7200 sekunder har kontrollerats: högst 96 px.
Kontroller, träffrutor och faktiska glyphrutor kontrolleras mot hela
kattcanvasen/statistik/klocka. Skyddade bildområden är pixelidentiska
med rendererbasen i varje tillstånd. `manifest.json` innehåller mått,
glyphrutor och hashvärden. Bilderna är designsimuleringar, ingen ny
firmware och inget fysiskt godkännande. Lead granskar förslaget före Code.

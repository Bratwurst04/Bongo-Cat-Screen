# Bildkvalitet, kontrast och mättnad – utredning 2026-10-21

**Utredningssnapshot före dagens normalflash.** Senare installerades normal
61BE med partiell rullningsförbättring och snävt godkänt bildprov enligt
[driftrapporten](render-viewport-runtime-2026-10-21.md). Bildkedjans auditresultat
nedan är oförändrade; normalkandidaten ändrar inte färgkedjan.

## Slutsats och avgränsning

Det finns **ingen påvisad generell avmättning i konverteringen av vanlig opak
RGB/sRGB**. Elva enfärgade syntetiska bilder behöll exakta RGB-värden i den
81×81 stora omslagsetiketten. Avsiktligt dämpade bilder förblev dämpade.
Det bevisar inte att panelen återger färgerna korrekt.
Det täta svartvita provmönstret blandades däremot till nästan grått vid
nedskalningen till 81×81. Färre detaljer och lägre lokal kontrast i täta mönster
kan alltså uppstå före panelen utan en generell mättnadsändring.

Två konkreta programbegränsningar är bekräftade: **grönt albuminnehåll kan
bli transparent genom färgnyckeln**, och omslaget har högst **81×81 verkliga
etikettpixlar** före kompaktsteget. ICC/gamma, EXIF och alpha har separata
korrekthetsluckor. De är inte bevisad förklaring till vanlig opak sRGB eller
användarens upplevda generella blekhet. En paneluppgradering kan inte motiveras
av detta hostunderlag; fysisk kontrollramp och vinkeljämförelse behövs först.

**Ingen produktkod, inställning eller färgboost har ändrats.** Ingen app eller
firmware har byggts/installerats, ingen COM-/profil-/Spotifyåtkomst har gjorts.
Ett litet separat native hostreferensbibliotek kompilerades för färgmakro och
bildexpansion; det är inte ESP32-firmware, full LVGL eller ett TFT-prov.

Senast installerat utvecklingspar är **C42112AD/EBB334A9 vid 921600**. Lead 5
har den 21 oktober separat läst den kanoniska EXE:ns storlek/hash och bekräftat
C421 samt båda nya kandidatfilerna. Ingen enhets-/runtime-/profilstatus lästes
idag. Driftobservationen **20 oktober 14:56:25,996** är historisk och fysisk
återställningskontroll väntar. **61BE3B63/1252EBAC är endast byggda/oflashade**;
bild-/rullningsacceptans återstår. Se [handoff](lead-handoff-2026-10-21.md) och
[viewportens bevisgränser](render-viewport-2026-10-20.md).

## Syntetisk överblick

Schackmönstret i färdiga skivbilder visar pixlar som blir transparenta genom
grönnyckeln. Källans alpha visas däremot som normal compositing på schackbakgrund.
Vinylkolumnen visar den verkliga RGB888-bilden med ännu synlig grön nyckelfärg.
Sista kolumnens zoom är en **Pillow-nearest-modell**, inte exakt LVGL-raster,
fysisk LCD, gammakurva eller bild av användarens skärm.

![SIMULERING: källbild, vinyl, kompakt, refinement och zoom](../build/artwork-quality-2026-10-21-r3/pipeline-overview.png)

[Alla åtta mönster, inklusive mörka/ljusa steg och alpha](../build/artwork-quality-2026-10-21-r3/pipeline-contact-sheet.png).
Bilderna är lokala ignorerade auditoutputs. Verktyget nedan kan återskapa dem
utan privata omslag eller extern runtime.

## Granskad källa

- Companionens faktiska publika C421-frysning:
  `build/product-committee-2026-10-20/app-package-r5/source/`. Manifest-SHA:
  `1D430C1178BA0F9D62419B13D766C6F23C850F5488B8B9093AF71C69A7F9A5FE`.
  `media_bridge.py`, `artwork_crop.py`, `artwork_codec.py`, `engine.py` och
  `spotify_api.py` verifierades mot pins och är byteidentiska med aktuell källa.
- EBB:s faktiska källfrysning:
  `build/artwork-refinement-2026-10-19/source-frozen/`. Manifest-SHA:
  `AA5668E97EEAE865C6048C53C2F1633F2C51AB18FE9AD56F0C3DAFA5A710F792`.
  Compact-/turntable-/record-headers, `User_Setup.h` och `lv_conf.h` är oförändrade.
  Huvudfilen skiljer sig genom senare label-/diagnos-/viewportarbete; färgkedjan
  har granskats mot EBB. Ingen aktuell huvudfil förväxlas med installerad binär.
- Lokal TFT_eSPI **2.5.43**: init/rotation/defines/flushimplementation matchar
  motsvarande skyddade bibliotekspins i `render-measurement-r2`. Det bekräftar
  programinställningen, inte vilken panelrevision som faktiskt sitter på kortet.
- Samlade pins och jämförelser finns i auditens `source-inputs.json`.

## Kedjan och vad varje steg gör

Fil/rad nedan avser aktuell arbetskälla på basen `5305057`; companionfilerna
ovan är också exakt C421. Alla programobservationer är skilda från panelhypoteser.

| Steg och kodreferens | Observerat | Betydelse/gräns |
| --- | --- | --- |
| Windows: `companion/media_bridge.py:1066` | Kodad thumbnail läses från WinRT-stream, högst 8 MiB | Ingen rå WinRT-pixelbuffer eller bevisad premultiplicerad bitmap hanteras här. Faktisk thumbnailupplösning kan variera |
| Spotify API: `companion/spotify_api.py:427`, `:758`; `media_bridge.py:849` | Första bild-URL i svaret hämtas utan Bearer/redirect; samma konverterare används | Ingen uttrycklig begäran om färgprofil/upplösning. Faktisk nätbild lästes inte i auditen |
| Avkodning: `media_bridge.py:1088` | JPEG/PNG, dimensionsgränser; sedan `.convert("RGB")` på rad 1094 | Ingen ImageCms-transform, EXIF-transpose eller uttrycklig alpha-compositing |
| Selektiv crop: `companion/artwork_crop.py:22`, anrop på `media_bridge.py:1093` | Endast Windows Spotify opt-in; strikt alpha-/footer-/geometrisignatur | Igenkänd syntetisk 300×300-wrapper ger exakt albumruta `(33,0,267,234)`; ingen extra inset |
| Generisk crop: `media_bridge.py:1098` | Sex procent av minsta dimension på varje kant om wrapper inte känns igen | Gäller **även API och andra spelare**, trots Windowsbadgekommentaren. 512×512 blev 452×452; ingen färgförbättring, ytterinnehåll försvinner |
| Etikett/vinyl: `media_bridge.py:1103`, `:1113`, `:1133` | LANCZOS-fit till `round(112*.72)=81`, cirkelmask, rillor/nav och gröna hörn i 112×112 RGB888 | Detalj förloras redan före transport. Payload är 37 632 byte; ingen generell saturation-/contrast-setter |
| Kompakt: `companion/artwork_codec.py:7` | Center-nearest 112→80 och RGB565 big endian, 12 800 byte | Etiketten motsvarar ungefär 58 kompaktpixlar i diameter. Nearest skyddar nyckeln men ger kantsteg |
| ESP32: `src/media_art_compact.h:10`; `src/bongo_cat_featured.inc:1253` | Verklig 80→112 center-nearest expansion i befintlig inaktiv slot; full RGB konverteras med LVGL | Ingen återvunnen detalj av uppskalningen; båda vägar slutar som RGB565 |
| Refinement: `artwork_codec.py:25` | Samma 112-cache skickas senare; coarse-mask bevaras där någon variant är nyckel | Mer detalj än kompakt, men aldrig mer än ursprungliga 81 etikettpixlar. Nyckelhål i coarse repareras inte av refinement |
| LVGL: `src/bongo_cat_featured.inc:953`, `:1029`; `src/focus_countdown_layout.h:11` | Chroma-key-format, ingen bildantialias; zoom 384/256 normalt, 320/256 i Fokus | 112-bilden motsvarar 168/140 displaypixlar; etiketten cirka 121,5/101,25. Ingen extra information skapas av zoom |
| Flush: `src/bongo_cat_featured.inc:580`; `lv_conf.h:30` | `LV_COLOR_16_SWAP=1`, `pushColors(..., false)` | Byteordningen är avsiktligt redan rätt för SPI. Nativeprovet matchar Pythonpackning mot LVGL-makrots faktiska minnesbyte |
| Panelinit: `User_Setup.h:40`, `:110`; `src/bongo_cat_featured.inc:2302` | ILI9341_2_DRIVER, inversion ON, rotation 0 | Inställningar i källa; ingen panelkalibrering eller elektrisk mätning utförd |

### Bekräftad färgnyckelkollision

`LV_IMG_CF_TRUE_COLOR_CHROMA_KEYED` och `LV_COLOR_CHROMA_KEY=0x00FF00`
använder logiska RGB565-koden **0x07E0** som transparent. Både `(0,255,0)` och
`(3,253,5)` blir samma kod. Hela mängden `R=0..7, G=252..255, B=0..7` omfattar
256 RGB888-färger med den koden. Det gäller även full/refine-konverteringen.

I det syntetiska färgrutemönstrets inre etikett-ROI blev **478 pixlar** nyckel;
grönt syns därför som hål i schacksimuleringen. Omslagsmaskens gröna hörn är
avsiktliga, grönt albuminnehåll är en annan sak. Detta förklarar specifika
gröna bortfall, **inte generell låg kontrast eller avmättning**.

Minsta tänkbara framtida rättning: skydda albuminnehåll som kvantiseras till
0x07E0 med en nära icke-nyckelkod **efter resampling och före mask/vinyl/codec**,
med exakt bevarad yttre nyckel och verifierad coarse/refine-mask. Val av kod och
regressioner behöver granskas separat. Ingen remap är implementerad nu.

### ICC, gamma, alpha och EXIF

- Opak vanlig RGB och sRGB-taggad samma RGB gav identisk vinyl. En särskilt
  konstruerad **linjär TRC-profil** med kodvärden `(64,128,192)` gav också samma
  produktresultat, medan en uttrycklig ImageCms-transform till sRGB gav
  `(137,188,225)`. Det visar ett verkligt profilhanteringsgap för sådana bilder;
  det är inte belägg för att normala Spotifybilder använder den profilen.
  [Pillows ImageCms](https://pillow.readthedocs.io/en/stable/reference/ImageCms.html#PIL.ImageCms.profileToProfile)
  beskriver den explicita profiltransformen.
- Ett PNG-gAMA-värde på 1,0 förändrade inte produktens pixelresultat. Det finns
  ingen generell gamma-/kontrastkorrigering i denna konverterare. Att öka gamma
  utan referens kan samtidigt förstöra avsiktligt mörk bild och högdagrar.
- Helt transparent PNG med lagrad RGB `(255,32,16,0)` blev synlig röd etikett.
  Compositing på neutral grå bakgrund skulle ha givit `(128,128,128)`.
  Här **kastas alpha**, den normaliseras inte. Det gäller även delvis transparenta
  kanter utanför den strikt igenkända wrappern.
- PNG lagrar enligt [W3C:s alphaavsnitt](https://www.w3.org/TR/png-3/#6AlphaRepresentation)
  alpha utan premultiplikation. Pillow skiljer `RGBA` och premultiplicerad
  `RGBa` i [sin modespecifikation](https://pillow.readthedocs.io/en/stable/handbook/concepts.html#modes).
  Här läses kodad JPEG/PNG, så **ingen generell unpremultiply ska införas** utan
  belägg för ett avvikande indataformat. Ingen sådan WinRT-källa observerades.
- JPEG med EXIF-orientation 6 gav samma vinyl som samma JPEG utan flaggan;
  orienteringen tillämpas inte. Det är främst ett orienterings-/cropgap,
  ingen förklaring till generell avmättning.

## Syntetiska resultat och reproducerbarhet

Verktyg: [run_audit.py](../tools/artwork_quality_audit_20261021/run_audit.py),
[native_reference.cpp](../tools/artwork_quality_audit_20261021/native_reference.cpp),
[körinstruktion](../tools/artwork_quality_audit_20261021/README.md).
Den exakta frysta statiska C421-konverteraren extraheras med AST; companionen
importeras/startas inte. Verkliga codec-funktioner körs. Nativeprovet innehåller
bara det pin-verifierade LVGL-färgmakrot och EBB:s riktiga expansionsheader.
Slutzoom och checkercompositing är uttryckliga hostmodeller, inte full LVGL/TFT.

**14 avgränsade auditkontroller PASS** i både r3 och r4, med befintlig Python
3.13.16/Pillow 13.0.0/LittleCMS 2.19. Åtta mönster kör verklig konvertering,
kompakt, native expansion och refinement med exakt bevarad key-mask. De övriga
kontrollerna täcker elva solida färger, samtliga 256 kodvärden i var och en av
RGB-kanalerna, ICC, PNG-gamma, alpha och EXIF. Ingen bred produktsvit kördes om.

- Alla elva solida etiketter behöll exakta RGB innan kvantisering, inklusive
  dämpad färg och neutral grå. Ren röd/blå/vit/svart packades till förväntad
  logisk RGB565-kod; ingen extra kanalswap påvisades i programkedjan.
- Över **768 kanalvärden** matchade Pythonpackning native LVGL-byte exakt.
  Maxfel vid digital full-range bitutvidgning var **7/3/7 kodsteg av 255**.
  RGB565 ger färre tonsteg/bandning och viss kanalobalans i gråskalor; det är
  precision, **inte ett mått på färgomfång eller fysisk kontrast**. Maxvitt blir
  fortfarande full kod, så enkel bittrunkering bevisar ingen generell grå slöja.
- I samma inre etikett-ROI var den avsiktligt dämpade bildens medel-HSV-mättnad
  cirka **0,149 kompakt/0,150 refine**. Neutral grå luma-proxy var cirka
  **126,982/127,013**. Dessa är kodvärdesmått; inte cd/m², uppmätt gamma eller
  kontrastförhållande. Resampling och olika samplingspunkter kan ändra dem något.
- **95** syntetiska indata-/bild-/råbyte-/metricoutputs var byteidentiska mellan
  r3 och r4. Nativebinärer, kompilatorloggar och övergripande manifest undantogs
  från den jämförelsen eftersom de kan innehålla byggtid eller utmatningssökväg.

Slutunderlag: `build/artwork-quality-2026-10-21-r3/` och motsvarande `r4/`.
Metrics-SHA i båda:
`4D8CFAA24F61B0ECA1A3206FF7B29A79995A47495A2A9E9F4B231E53DCE67BB6`.
R3-manifest-SHA:
`CD574F47EA27CA56DB8E754759A4D2F7A8A5403DB15A85F4757667F562EAAD9E`.
R4-manifest-SHA:
`F269A8F6C5E55A0A5B8ECC46416FE37801EC1A3A1D4C55CD757165B9A013F426`.
R1 är ett bevarat tidigt prov med felaktig inset-annotation; r2 stoppade i
auditverktygets nya slutkontroll av bibliotekssökväg före manifest. Dessa är inte
slutkvitton. Gamla produktbuilds/cache/dist har inte återskapats eller ändrats.

## Panel och rekommenderad nästa ordning

Den lokala alternativa ILI9341-initsekvensen sätter **0x3A=0x55**, väljer
gamma via **0x26=0x01** och skriver fasta **E0/E1-tabeller**
(`TFT_Drivers/ILI9341_Init.h:173`, `:191`, `:194`, `:211`). Driverdefinitionen
väljer BGR som standard; projektets flush är anpassad för den byteordningen.
GPIO 27 är aktiv hög och används LOW/HIGH, ingen PWM-ljusstyrka hittades.
Dessa val är inte en mätning av korrekt gamma, svartnivå eller panelens ljusstyrka.

[Tillverkarens familjespecifikation](https://www.guition.com/icms/upload/fb081940d6fc11f09850077a33e1404f/FTPData/UEditor/file/2026121/1768961091252/ESP32-2432S024%20Specifications-EN.pdf)
anger 240×320, TFT, ILI9341, RGB 65K och `View >60°`. Den anger inte verifierad
TN/IPS-typ, gamut eller kontrastförhållande för vår faktiska panelrevision.
**Controller-ID identifierar inte panelens optiska kvalitet.** Ingen köprekommendation
eller drop-in-kompatibilitet för annan skärm kan härledas ur detta.

1. **Separera det bekräftade gröna bortfallet.** Eventuell liten innehållsremap
   planeras som egen korrekthetsfix med key-/mask-/refineprov, inte en allmän boost.
2. **Fysisk neutral referens behövs.** UI:s konsulterade förslag är opakt direkt-
   ritade RGB/CMY/svart/vitt, 16 separata RGB565-gråsteg samt mörka/ljusa steg,
   först rakt framifrån och sedan i normal arbetsvinkel. Håll init/gamma oförändrad
   i första jämförelsen. Mät/observera svart, vitt, tonsteg, kanalordning och vinkel.
   Detta är en provplan, **inte ett utfört prov**.
3. Panelreferensen får **inte gå genom grönkeyat omslag**: grönt skulle då ge
   falsk slutsats om panelen. Ingen ny diagnosfirmware ingår här; om direkt
   opak ritning kräver sådan kod behövs separat uppgift och konkret flashgodkännande.
4. Jämför sedan samma kända bild genom kompakt/refine, stilla och roterande.
   Det skiljer informationsförlust/aliasing från uppmätt panelbeteende.
5. ICC-/alpha-/EXIF-härdning kan planeras separat med neutralt sRGB-standardläge
   och validerad fallback. Större etikett eller annan resampling är valbara
   design-/detaljkompromisser och måste bevara mask, fart och animationer.
6. Dithering kan utredas mot bandning men riskerar brus/twinkle vid rotation.
   Kontrast/mättnad/gamma bör vara försiktiga och valbara först efter referensprov;
   klippta svärtor/högdagrar och avsiktligt dämpad originalbild ska kunna bevaras.
7. Om direktpanelen fortfarande är otillräcklig: fastställ faktisk panelmodell,
   optiska data, vinklar, anslutning/spänning, mekanik, drivrutin och touch före
   jämförelse av uppgraderingar. Ingen ny panel eller produktändring väljs nu.

UI och Lead har granskat resonemanget oberoende; deras syntetiska/primärkälle-
bedömningar är konsulterade underlag, inte ytterligare hårdvaruacceptans.
Denna audit ändrar inte gårdagens CI-kvitton; en ny fjärrkontroll var enligt
Lead blockerad av nätproxy vid denna audit. Senare Git-publicering och dess
faktiska CI redovisas i draft-PR 1. Fortsätt nästa beslut i Lead 5.

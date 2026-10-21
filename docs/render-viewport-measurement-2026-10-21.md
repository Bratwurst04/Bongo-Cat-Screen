# Viewportmätning med 1252 och återgång till normal 61BE – 2026-10-21

**Mätcykeln är avslutad. Installerat är C42112AD / normal 61BE3B63 vid 921600,
CPU meter av.** Lead 5 flashade tillfälligt mätprofilen 1252EBAC inom användarens
uttryckliga tillstånd, genomförde syntetisk paus/spelande/paus och återställde
normalfirmwaren. Användaren bekräftade därefter: **”Ja, vanlig låt och omslag
är tillbaka”**. 1252 är inte kvar på enheten.

Detta är ett instrumenterat syntetiskt tidsprov, **inte panel-FPS eller exakt
CPU-/prestandamätning av normal 61BE**. Det tidigare kvalitativa resultatet
”Bättre men fortfarande skillnad mot när den är pausad” kvarstår som separat
användarobservation. Ingen fullständig rullningsfix eller ny bred fysisk
regressionsacceptans följer av mätningen.

Alla tider är svensk tid, UTC+02. Code har enbart läst de uttryckligen angivna
säkra kvittona, kontrollerat deras innehåll/hashar och förberett dokumentdiffen.
Ingen produktkod, ny build, COM-/profil-/runtimeåtgärd eller flashning har
utförts av Code. Dokumentunderlaget är granskat av Lead.

## Avgränsning och tidigare underlag

- [Bygg-/hostunderlag från 20 oktober](render-viewport-2026-10-20.md) beskriver
  de frysta kandidaterna och deras dåvarande föreflashstatus.
- [Normalflash och snävt bildprov tidigare 21 oktober](render-viewport-runtime-2026-10-21.md)
  beskriver C421/61BE, två låtbyten, senare skärpning och menyretur.
- [Överlämning till Lead 5](lead-handoff-2026-10-21.md) och
  [bildkvalitetsutredningen](artwork-quality-2026-10-21.md) är separata underlag.

Äldre rapporter och frysta build/dist-/källkvitton bevaras som historiska
ögonblicksbilder. Ingen ny produktbinär, release, merge eller tagg ingår.

## Exakta versioner och verifierad återgång

| Del | Byte | SHA-256 |
| --- | --- | --- |
| Bevarad companion C42112AD | 22 856 796 | `C42112AD2C774B0814B40B688AE8FA80BD0858D1308DA9130719362492CAC135` |
| Tillfälligt mätt 1252EBAC | 938 400 | `1252EBAC2C3CBFEC4915DADB172CC06DB5799DF7E0482B17710E474DD4274C33` |
| Återställd normal 61BE3B63 | 937 600 | `61BE3B633AF700B27F0DDF55F9B26D41E1B9E0916F187848A470B50988701440` |
| Ny backup av normallägets appsektorer | 942 080 | `113424C8966778445559A91F5DB0DDF1D0D7B77ABD779553C53CC89E654FCA5D` |

Appoffset är **0x10000**, backupintervallet **[0x10000,0xF6000)**.
Flashbaud **115200**, normal seriell drift **921600**. **Ingen bootloader eller
NVS skrevs.** Detta är en ny backup av normalläget 61BE; den ska inte förväxlas
med den äldre EBB-backupens SHA 855CAF3A….

| Leadoperation | Tid | Kvittotid | Resultat |
| --- | --- | --- | --- |
| Läsa backup | 87,234 s | 12:06:54,543 | exit 0 |
| Separat verifiera backup mot enheten | 3,347 s | 12:07:15,557 | exit 0, digest verifierad |
| Flasha tillfällig 1252 | 42,708 s | 12:08:19,343 | exit 0, skrivning verifierad |
| Återgå till normal 61BE | 42,627 s | 12:15:21,915 | exit 0, återställning verifierad |

Manuella BOOT/RESET-bekräftelser ingick i Leads arbetsflöde. C421 och fyra
aktuella profiler bevarades; app/config, Run och genvägar verifierades efter
omstart. **17 beständiga privata arkivkopior** verifierades av Lead. Dessa
privata filer/journaler/loggar har inte öppnats eller publicerats av Code.

## Protokoll och urval

Companionen var stoppad under det syntetiska provet. Harnessen gjorde **noll
Spotify-API-anrop**. Den använde en syntetisk kompaktbild på 12 800 byte, SHA
`961FB0804278706D08827CC9CDEC85D496E7B149285697CEB51A69FA58FCE1CA`,
och syntetisk text. Användaren bekräftade rätt testbild/text före mätfaserna.

Tre faser om **60 s** planerades och genomfördes: paus, spelande, paus.
Harnessen använder **18 s warmup/urvalsgräns** och markerade **3/2/2**
diagnosfönster som godkända för sammanställningen. 15 diagnosrader var giltiga,
fem missformade rader avvisades och 58 icke-diagnosrader sorterades bort.
Inget rått serieinnehåll publiceras.

Urvalet återges exakt från `eligible_stable_window` i kvittot. Första godkända
pausraderna har fasålder **20,575 respektive 20,613 s**. Detta är en gräns vid
rapporttidpunkten, **ingen garanti att varje helt cirka 15 s långt ackumulator-
fönster började efter 18 s**. Rapporten omklassar inte kvittots fönster.
Rader före fasstart/urval och övergångsgrupper utelämnas från tabellerna.

Mätningen löpte från harnessstart **12:08:30,627** till avslut
**12:13:32,154**, inklusive väntan på användarens panelbekräftelse
**12:10:32,067**. Fasstarterna finns separat i råa, men innehållsbegränsade,
JSON-data. Alla sju valda fönster har `transfer=0`.

## Uppmätta tider

**G**: gap mellan handleranrop. **H**: tid inne i `lv_timer_handler`.
**F**: tid för en enskild synkron flush. Histogramgränser: ≤1, ≤4, ≤16, ≤33,
≤66 och >66 ms. Maxvärden nedan är per respektive provtyp, inte samma händelse.

| Fas | Godkända fönster | H antal | H max | H >33 ms | H >66 ms |
| --- | --- | --- | --- | --- | --- |
| Paus före | 3 | 2655 | 65,555 ms | 15 | 0 |
| Spelande | 2 | 430 | 71,304 ms | 430 | 57 (13,2558 %) |
| Paus efter | 2 | 1780 | 65,834 ms | 10 | 0 |

| Fas | G antal | G max | G >66 ms | F antal | F max |
| --- | --- | --- | --- | --- | --- |
| Paus före | 2655 | 75,216 ms | 10 (0,3766 %) | 3786 | 4,560 ms |
| Spelande | 430 | 80,934 ms | 426 (99,0698 %) | 2616 | 4,524 ms |
| Paus efter | 1780 | 69,369 ms | 7 (0,3933 %) | 2506 | 4,553 ms |

Sammanlagt hade de två pauserna **0 av 4435 H-prov över 66 ms**. Alla 430
spelande H-prov var över 33 ms, 57 över 66 ms. Även paus hade enstaka anrop
över 33 ms. Gap och handler är olika mått; de ger inte direkt en fysisk bildfrekvens.

### Vad siffrorna medger

- I just detta instrumenterade scenario är handlerbelastningen tydligt större
  vid uppspelning än vid paus. Kvarvarande skillnad är förenlig med användarens
  tidigare kvalitativa observation, men provet isolerar inte dess alla orsaker.
- Flera flushar kan förekomma under ett handleranrop. **Max H minus max F**,
  eller summor/multiplar av oparade maxvärden, ger ingen kausal uppdelning av
  transform-, rit-, SPI- eller annan kostnad.
- Diagnosprofilen har egen kostnad, bland annat gles numerisk rapportering.
  Det är inte normalfirmwarens exakta CPU eller panel-FPS.
- D7DA-siffrorna från föregående dag finns i den äldre viewport-rapporten.
  Det är **separata körningar**, ingen kontrollerad parad A/B och ingen
  EBB-baslinje. Skillnaden får inte omsättas till en garanterad fysisk
  förbättringsprocent.

Nästa renderarbete behöver ett konkret avgränsat underlag för den kvarvarande
kostnaden och en egen verifieringsplan. Denna dokumentation väljer ingen ny
implementation, ändrar inga perioder/baud och ger inget nytt flashgodkännande.

## Återställd vardagsdrift och användarbekräftelse

Lead startade åter den vanliga Startmenygenvägen via Explorer. `APP_START`
loggades **12:17:16,207**, första serieöppningen misslyckades
**12:17:18,372**, försök två lyckades **12:17:22,502**. Resync, två fulla
legacy-ACK och bas-/kompakt-/refinementkapabilitet finns i kvittot. De första
37 632-bytejobben tog 4966/4959 ms på sändarsidan; de är inte LCD-/refinementmått.

Senast dokumenterad status **12:17:53,571**: filålder **0,655 s**, ESP ansluten,
uptime **34 s**, ESP-statusålder cirka **1,680 s**, heap **154 164 byte** och
CPU meter **false**. Windows Spotify var tillgänglig/aktiv, C421-hash och config
mot backup matchade, Run och genvägar var oförändrade.

Grundkvittots `physical_restoration_confirmation: pending` var korrekt när
det skapades. **Det separata senare kompletteringskvittot styr slutstatusen**:
**12:19:34,916** svarade användaren **”Ja, vanlig låt och omslag är tillbaka”**.
Det bekräftar vanlig låt/bild efter återgång, inte en ny full acceptans av
rullning, gester, sleep/resume, Fokus/DJ eller långdrift.
Den separata användarobservationen om en grå yta som ersätter delar av
Quitter-motivet är fortsatt öppen och förklaras inte bort av återställningssvaret.

Ingen färgmätning, mobilfilm eller ny färgtestfirmware ingick. Det öppna
Quitter-fallet och föreslagen kvalitativ mobiljämförelse beskrivs separat i
[bildkvalitetsrapporten](artwork-quality-2026-10-21.md).

## Publika säkra kvitton och integritet

Följande fem uttryckligen godkända JSON har kopierats **byteidentiskt** från
`build/render-viewport-measurement-20261021-r1/` till
`docs/evidence/render-viewport-measurement-2026-10-21/`. Inga andra buildfiler,
privata journaler, profiler, loggar, säkerhetskopior eller råa omslagsbilder ingår.
Quitter-kvittot innehåller bara identifiering och begränsade numeriska mått.

| Kvitto | SHA-256 |
| --- | --- |
| [measurement-safe.json](evidence/render-viewport-measurement-2026-10-21/measurement-safe.json) | `FFA744466BB341609655AE5DDE02386AC1FE61530873EEB7AF64173F2589564C` |
| [render-timings.json](evidence/render-viewport-measurement-2026-10-21/render-timings.json) | `01EE3D69CAE861C4F9E163F91773BF155943759140A6181EF7CF73F3DDB3D1BB` |
| [render-summary.json](evidence/render-viewport-measurement-2026-10-21/render-summary.json) | `B004AACCE242AD78B17049B7648913B374065D6A2BA4DBF90904AB53A5AAAE90` |
| [restoration-confirmation-safe.json](evidence/render-viewport-measurement-2026-10-21/restoration-confirmation-safe.json) | `2A93214FFCB5E0C7EEC9C058E0A24DDCD8F91475BC520E0291F91A95FE754ECC` |
| [quitter-reference-safe.json](evidence/render-viewport-measurement-2026-10-21/quitter-reference-safe.json) | `B2AC9132584BC4C693DE2A3D4479FEDC09D89AA775814C279BAF0A20AFFD75C1` |

Kvittonas ursprungliga CRLF-radbrytningar bevaras. Katalogens lokala
`.gitattributes` stänger av Git-textnormalisering endast för dessa JSON så att
SHA-pins kan kontrolleras även efter framtida publicering/check-out.
Summeringen har verifierats mot de markerade fönstrens antal/max/histogram;
ingen ny mätning eller bred produktsvit har körts för dokumentdiffen.

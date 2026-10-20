# Återhämtning från partiella kapabilitetssvar – 2026-10-20

## Status

Installerat är fortsatt **94145746/EBB334A9 vid 921600**. Lead verifierade
att båda normala processerna kör den senaste installerade companionen.
Ny separat companion är **byggd och paketkontrollerad, inte körd eller
installerad**:

- `dist/companion-2026-10-20-capability-partial-dev/BongoDeskSpotify.exe`
- 19 664 148 byte, SHA-256
  `B7019579DD272A78DBBD59661447D35FB50A2C386A78B065F98288ABF0B2B6A6`.
- Firmware återanvänds exakt, 937 184 byte:
  `EBB334A926709E047DA1D930684C76D02DFA162332C508E775F062AE492E2FF3`.
  Ingen firmwarebyggning, protokolländring, flash eller release ingår.

## Evidens och avgränsad orsaksbedömning

Efter APP_START 11:29:15 och resync 11:29:58 kom bas- och REFINE-svar,
sedan en omsändning med samma två svar. Ingen COMPACT registrerades.
Överföringsunderlagets 139 innehållsfria händelser visar **24 ART_SENT,
samtliga 37 632 byte**, två frames/15 ms. Senaste sändningen tog 4 687 ms;
MEDIA_TRACK→ART_READY var samtidigt cirka 10–15 ms. Den långa överföringen
är alltså förenlig med det valda fullformatet.

Verklig reader och sender reproducerade exakt den syntetiska partiella
svarsekvensen: base/refine aktiva, compact tom, en retry och fullheader
`112:112:37632`. Det säkra appfelet är att denna partiella kapabilitetsbild
låser sessionen i fullformat trots tillräckligt stödbevis. Firmware annonserar
REFINE endast från samma kompaktprofil/serial-RX-gren som RGB56580.
**Varför just kompakt-raden saknas är fortfarande obevisat.** Varken fysisk
radförlust, UART-korruption eller interleaving har reproducerats eller fastställts.

## Minsta rättning och verifiering

`engine.py` låter färsk bas + REFINE bekräfta kompaktstöd för samma
**connection/epoch/nonce vid 921600 och aktiv app**. Basens challenge sparas
uttryckligen. De befintliga cap-grenarna använder generationen som fångades
före läsningen. Båda svarens ordningar fungerar; ensamt REFINE, gammal bas,
fel nonce/baud/connection/epoch och stop ger ingen sådan bekräftelse.
`ART_COMPACT_INFERRED` är innehållsfri diagnostik.

Direkt COMPACT utan REFINE, FAST och äldre peers bevarar sina vägar.
Ingen extra frågeloop, baud-/bursthöjning eller köning införs. Sender,
metadata, codec, crop, animationer och API/auth/config är oförändrade.

- **12 nya riktade PASS**.
- **121 relevanta upptäckta: 120 PASS, ett avsiktligt fotoreferens-SKIP**,
  noll fel/externa nätförsök, isolerade profilmappningar.
- Verklig native parser/CRC/slot kvitterar 12 800 följt av 37 632 byte
  från samma cache. Befintliga lifecycle/resync/legacy/refinementprov ingår.
- Code och Root har separat verifierat paketets 13 moduler/fyra resurser
  mot källan utan kandidatstart. Övriga engine-metoder
  jämförs med 45a0be8; äldre frysta källor, rapporter, previews och binärer bevaras.

## Väntande fysiskt prov och källor

Efter Roots granskning och nytt exakt appgodkännande: starta appen, kontrollera
färska cap-svar/inference, byt låt och kontrollera kompakt-ACK samt senare
SLOT/full-ACK utan extra hopp. Upprepa efter appstart/resync/väckning.
En redan startad fullöverföring kan avslutas i fullformat. **Fysisk återhämtning,
LCD-tid och en generell ensekundsgaranti är inte bevisade av hostproven.**

Endast två godkända privata snapshots lästes, hashverifierade före läsning:

- `bongo-album-startup-20261020-safe.json`:
  `BEE096125398F409CDA310F107E8FDB3FF61205735DA5979EB83E09DD404B05F`.
- `bongo-album-transfer-20261020-safe.json`:
  `7F1AFE0E724BDFD14589F776E3CBA5F72D6AB61131FCF3FD618A447AB5A06D5F`.

Separat godkänt granskningsbesked, också hashverifierat före läsning:
`bongo-partial-cap-root-package-review-20261020.json`,
`A9DFD4921C594BDE3B779DD54A6AA2E3211129E64965D5FA2635CCB78120D9AE`.

Inga privata länkar följdes. Ingen COM/runtime/API/installation från Code;
Spotify-bakgrundsfelsökning förblir pausad och seek avbruten.

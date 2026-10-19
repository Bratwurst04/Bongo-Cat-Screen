# Överlämning inför refinement-prov – 2026-10-19

## Ansvar och faktiskt läge

Endast arbetsytan `D:\DEV\Ai\Github\Bongo-Cat-Screen`. Lead sköter granskning,
UI-samordning och separat godkänt runtime-/flashsteg; Code äger kod/dokument.
Ingen ny chatt, release, commit, push eller Spotify-bakgrundsfelsökning.
Seek förblir borttaget. Den gamla nattnoten bevaras exakt.

| Roll | Chatt-ID |
| --- | --- |
| Lead | `01a14061-2445-7cc0-9178-79fb0625be18` |
| Code | `01a0ec49-da6f-7b00-be86-06822053344a` |
| UI Code | `01a11581-4a2c-7e80-9742-adcd989df5ca` |
| Idébollplank | `01a14fba-80ff-7eb1-b3a0-d75492f7bdc3` |

**Installerat fortsatt FD9D811B/C6EBAE4B vid 921600**, inga runtimeåtgärder
från Code. Apphash `FD9D811B0356818A56AA0787AD3041820DA8D45D6083D8E0E822D3B59426DB06`.
C6-app **936 704 byte**, hash `C6EBAE4B13DE934449E2F32738D2CBFAEEC2693C5ECF8EE8A3A71FDB6254D275`.
Tidigare drift gav första kompaktomslaget 1 164 ms och två låtbyten 374/351 ms;
bild/snabbhet godkändes snävt, fysisk C3-resendväg förblev oprovad.

Användaren vill nu ha skarpare bild cirka fem sekunder efter snabbilden.
Lead valde att vänta med 5556-flash och färdigställa ett komplett par.
**5556B647** är bevarad, endast byggd/granskad och inte installerad.

## Redo men inte distribuerat

- Companion **59FC2E33**, **19 662 092 byte**, SHA-256
  **59FC2E3323B1B0682069A29AD16460C2F9E960771506DA6BEE5F128721A83B3B**,
  `dist/companion-2026-10-19-artwork-refinement-dev/BongoDeskSpotify.exe`.
- Firmware **EBB334A9**, **937 184 byte**, SHA-256
  **EBB334A926709E047DA1D930684C76D02DFA162332C508E775F062AE492E2FF3**,
  `.pio/candidates/artwork-refinement-2026-10-19-EBB334A9.bin`.
- Profil `esp32-024r-spotify-compact80`, runtime **921600**; samma 5556-rörelser
  och två slotar. Nytt generation/id-bundet SHOWN skyddar kompakt-staging
  innan ett enda konservativt full112-jobb får börja.
- [Rapport](artwork-refinement-2026-10-19.md),
  [kandidatmanifest](../build/artwork-refinement-2026-10-19/candidate.json),
  SHA **024E827A2814918FAC1A1A336B6FB1EB48AA7D82CA29ABBCF04581E49E8CCC5F**.
  [Källa](../build/artwork-refinement-2026-10-19/source-frozen.json),
  [scope](../build/artwork-refinement-2026-10-19/scope-verification.json),
  [paket](../build/artwork-refinement-2026-10-19/package-verification.json),
  [firmwarebevis](../build/artwork-refinement-2026-10-19/firmware-verification.json).

Lead/UI godkände [r4-hostpreview](../visuals/artwork-refinement-2026-10-19/r4/index.html),
manifest **4100679C21BB4CE2E080BBA014E8521A5AE02EC3E1A8CE03AAAC789B9AE0C915**.
Atomisk skärpning behåller opakmask, geometri och rörelse; ingen extra fade.
23 nya PASS; relevant **158 upptäckta/156 PASS/två kända SDK-skip**. 189 frysta
källfiler, 75 Python, 8 584 bytebevarade äldre filer. Alla 12 inbäddade moduler
och fyra resurser matchar. Tidigare mellanbyggen/previews/källkopior bevaras.

**4720 ms är en tidsmodell**, baserad på äldre 4,68 s fullöverföring, inte
uppmätt ny TFT-latens. SHOWN betyder vald/pinnad slot, inte fysisk LCD-tid.
Missad signal/fel kan lämna low-res; tappad ACK kan gälla redan korrekt vald
fullbild. Refinement får ingen retryloop och ny normalbild har företräde.

## Nästa steg hos Lead

1. Inhämta nytt uttryckligt godkännande för exakt **59FC2E33/EBB334A9**.
   Inget sådant binärgodkännande eller någon installation/flash ingår här.
2. Stoppa companion säkert utan pågående omslag. Verifiera profil/auth/Run/
   genvägsbackuper och gammal appbackup. BOOT enligt behov; läs tillbaka och
   hashverifiera installerad C6-app **936 704 byte** före skrivning.
3. Skriv app-only vid **0x10000**, upload **115200**, bevara NVS. Verifiera
   skrivningen; installera/starta exakt matchad companion med oförändrad profil.
4. Mät första faktiskt synliga low-res→skärpning på stabil låt. Kontrollera
   mask/crop/storlek, tonarm/progress/rotation, ingen ny tass/default, snabba
   byten före/under/efter full-END och återanslutning. Prova Fokus/DJ/gester,
   åäö, sleep/resume, Exit och längre drift. Spara separat fysisk rapport.

Denna överlämning tillkom efter frysen utan att ändra frysta källor/bevis.

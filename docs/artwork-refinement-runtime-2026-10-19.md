# Progressivt omslag installerat och snävt skärmprovat – 2026-10-19

**Installerat: companion 59FC2E33 / firmware EBB334A9, 921600 baud.**
Tider nedan är svensk sommartid, UTC+02. Äldre
[byggrapport](artwork-refinement-2026-10-19.md), frysta kandidater/bevis och
[handoff](lead-handoff-2026-10-19-refinement.md) bevaras exakt som föreinstallunderlag.

## Godkänt och verifierat byte

Användaren godkände exakt paret: ”Ja, installera och flasha paret”. Lead
gjorde säker prepare med tre profilbackuper och verifierad gammal appbackup.
Installerad C6-app återlästes: **936 704 byte**, korrekt
`C6EBAE4B13DE934449E2F32738D2CBFAEEC2693C5ECF8EE8A3A71FDB6254D275`,
88,422 s, exit 0. Skrivning av nya appen vid **0x10000/115200** tog
43,157 s, exit 0; Lead bekräftade hashverifierad skrivning. NVS bevarades.

- Companion, **19 662 092 byte**:
  `59FC2E3323B1B0682069A29AD16460C2F9E960771506DA6BEE5F128721A83B3B`.
- Firmware, **937 184 byte**:
  `EBB334A926709E047DA1D930684C76D02DFA162332C508E775F062AE492E2FF3`.

Normalreset bekräftades. Appen startades på samma kanoniska plats genom
befintliga Explorer desktop med `--startup`. Samtliga fyra observationer
bekräftar rätt apphash och oförändrad config/auth/Run-post/genvägar. Senaste
status 17:32:22 visar ansluten ESP32, uptime 165 s, heap 154 236/min 151 508
av 261 032 byte. Windows Spotify är tillgänglig och aktuell källa.

## Uppstart och kvittenser

APP_START **17:29:19.024** följdes av misslyckat serieöppningsförsök ett
17:29:21.215 och lyckat försök två 17:29:25.368. Första omslaget gick legacy:
READY 17:29:28.695, SENT 17:29:37.962, ACK 17:29:37.971, **9 276 ms** totalt,
sändning 9 264 ms. Det var 37 632 byte före registrerad kapabilitet.

DEVICE_RESYNC loggades 17:29:29.172. **ART_CAPABILITY_RESEND 17:29:37.970**
följdes av färsk bas/compact/refine 17:29:38.002–.006. Den andra legacy-
kvittensen kom **17:29:47.158**, före **ART_SENT 17:29:47.182**
(9 203 ms sändtid). Automatisk measurements missar detta par; dessa
eventtider redovisas separat utan påhittad READY→ACK-parning.

Senare observerades följande ordning:

| Överföring | Faktiska byte | Mått | Tid |
| --- | --- | --- | --- |
| Kompakt, första försök | 12 800 | READY→ACK | 626 ms |
| Full efter vald slot | 37 632 | SLOT→full-ACK | 4 749 ms |
| Kompakt, andra försök | 12 800 | ursprunglig READY→slut-ACK | 9 553 ms |
| Full efter retry | 37 632 | SLOT→full-ACK | 4 797 ms |
| Kompakt, första försök | 12 800 | READY→ACK | 616 ms |
| Full efter vald slot | 37 632 | SLOT→full-ACK | 4 700 ms |

De snabba försöken använde åtta frames/0 ms. Mellanbilden fick slot-event
17:30:55.798 men saknade första ACK; timeout kom 17:30:58.938. Konservativ
retry med en frame/15 ms kvitterades 17:31:04.244. Samtliga tre fulljobb
kvitterades med två frames/15 ms. READY:s 37 632 anger cachebilden; SENT
visar faktisk kompaktpayload. SHOWN/SLOT betyder vald/pinnad slot och ACK
godkänd mottagning. **Dessa tider är inte LCD-visning eller mobilhandling→skärm.**

## Snäv fysisk acceptans och källbedömning

På frågan om snabb bild, senare skärpning utan ny flip/hopp och gammalt
omslag kvar till flipens mitt svarade användaren **”Japp det ser asbra ut nu.”**
Det godkänner den frågade sekvensen kvalitativt. Exakt LCD-tid, rapid-skip,
Fokus/DJ, sleep/resume och långdrift är inte allmänt verifierade här.

Read-only granskning visar att omsändningsvägen återanvänder samma challenge
efter giltig aktuell status, kontrollerar conn/epoch och konsumerar en chans.
Den hoppar över först med bas+compact+refine. Engångsvägen har nu körts i
drift; journalen fastställer inte vilken tidigare fråga som missades eller
vilken fråga som gav respektive caprad. Källans probe ignorerar CAPS och
sendern kan välja legacy före kapabilitet; raw håller seriallåset genom
överföringen. Detta är förenligt med uppstartsordningen. Orsaken till den
saknade kompakt-ACK:n är inte fastställd. **Alla omslag under en sekund är
inte visat**; uppstart och retry avvek trots godkänd skärmbild.

Enda privata filkälla, hashverifierad före läsning:
`%LOCALAPPDATA%/BongoDesk/deployment-artwork-refinement-20261019-172448-919001-accepted-visual-baseline.json`,
**AD8507E5A91069E02A9D9F03AE48D82B125721A392D50DE67B3051E80ED2CA06**.
Inga bakuplänkar eller andra privata filer lästes. Inga produktkod-/binär-
ändringar, nya tester, COM/live-API/runtime/installation/flash från Code.
Ingen release/commit/push/seek-ändring eller återupptagen Spotify-felsökning.

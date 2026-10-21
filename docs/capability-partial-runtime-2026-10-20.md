# B7019579 installerad via Startmenyn och snävt skärmprovad – 2026-10-20

**Installerat: companion B7019579 / firmware EBB334A9, 921600 baud.**
Tider är svensk sommartid, UTC+02. Tidigare [byggunderlag](capability-partial-2026-10-20.md),
frysta 205 källkopior, manifest och äldre rapporter bevaras som historiska bevis.

## Verifierat appbyte och vanlig Windows-start

Användaren godkände B7019579 och instruerade att framtida färdiga appuppdateringar
ska ersätta samma installerade app. Den stående rutinen finns i
[CHAT_ROLES](../CHAT_ROLES.md): verifierad backup/hash, kanonisk EXE och
kontrollerade Startmeny-/skrivbordsgenvägar inom den aktiva uppgiften.

Lead bytte enbart appen efter tre verifierade profilbackuper och verifierad
ZIP-backup av 94145746. Config/auth/budget bevarades vid bytet;
Run-post och genvägar var oförändrade. **Firmware skrevs inte.**

- Companion, 19 664 148 byte:
  `B7019579DD272A78DBBD59661447D35FB50A2C386A78B065F98288ABF0B2B6A6`.
- Oförändrad firmwarereferens, 937 184 byte:
  `EBB334A926709E047DA1D930684C76D02DFA162332C508E775F062AE492E2FF3`.

Root startade själva befintliga **Start Menu/Bongo Cat.lnk** genom Explorer
desktop. Den startade `%LOCALAPPDATA%\BongoDesk\BongoDeskSpotify.exe` med
rätt hash, två normala processer och Explorer som förälder. Observationer
12:26:31 och 12:28:25 bekräftar ansluten ESP32, Windows Spotify samt rätt
apphash och oförändrade config/authfält/Run/genvägar. Ingen bakgrundsuppdaterare
eller releasefunktion har införts.

## Transport och avgränsad fysisk acceptans

APP_START **12:26:09.524** följdes av lyckad första anslutning **12:26:11.687**.
Bas **12:26:14.966**, explicit COMPACT **.969** och REFINE **.976** kom före
READY **12:26:15.004**. Första kompakt-ACK kom **12:26:15.793**.

| Observation | Payload | Mått | Tid |
| --- | --- | --- | --- |
| Uppstart, kompakt | 12 800 byte | READY→ACK | 789 ms; sender 250 ms |
| Uppstart, detalj | 37 632 byte | SLOT→full-ACK | 4 749 ms |
| Sex senare kompakta kvittenser | 12 800 byte | READY→ACK | 450/441/475/456/431/440 ms |
| Fem senare detaljkvittenser | 37 632 byte | SLOT→full-ACK | 4 718/4 697/4 795/4 708/4 682 ms |

Observerade sändningar var första försök. Kvittenserna tillskrivs inga
titlar eller LCD-tid; SLOT betyder vald bildslot. READY:s 37 632 byte är
cachebilden, medan SENT anger faktisk kompaktpayload.

På frågan om två låtbyten med cirka tio sekunder emellan, snabb bild och
senare skarpare omslag utan extra flip/hopp svarade användaren
**”Ja, det fungerar”**. Detta är kvalitativ acceptans av den frågade sekvensen.

**Ingen ART_COMPACT_INFERRED observerades:** uppstarten fick alla explicita
kapabiliteter. Fysisk återhämtning från partiella svar, orsaken till tidigare
radbortfall, sleep/resume, långdrift och en universell ensekundsgaranti är
fortfarande obevisade. Hostbevis för inference redovisas separat i byggrapporten.

## Dokumentationskällor

Endast dessa två privata snapshots lästes, hashverifierade före läsning:

- `bongo-capability-partial-B7019579-startup-20261020-safe.json`:
  `EA7B2B4548994FA77458E6366D62447A8B8B33864348CF9CD195A89F012D7A35`.
- `bongo-capability-partial-B7019579-accepted-20261020-safe.json`:
  `3CEE6EA61E70EFE0B8835B11994F3F9A2DA122F134247377000C115632866735`.

Inga privata länkar/backuper/loggar följdes. Code ändrade endast dokument;
ingen produktkod/binär, ny testkörning/byggning, COM/runtime/API/credentials,
installation/flash, commit/push eller release ingick i dokumentationssteget.

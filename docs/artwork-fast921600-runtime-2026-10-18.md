# 921600-par: installation och underkänt fartprov – 2026-10-18

**Installerat är companion 445D72A0 / firmware 860896DB vid 921600 baud.
Ensekundsmålet är UNDERKÄNT.** Alla tider nedan är svensk sommartid, UTC+02.
Den oförändrade [byggrapporten](artwork-fast921600-2026-10-18.md) beskriver
föreflashläget; dess modeller och hostprov är inte det fysiska resultatet.

## Installation enligt fryst journal

Användaren godkände ”Ja, installera och flasha paret”, BOOT med ”klar” och
normal reset med ”japp”. Lead installerade på samma kanoniska appplats och
ändrade endast faktisk `connection.baudrate` från 230400 till 921600.
Explorer-start, Run-post och genvägar verifierades bevarade. Tre privata
profilbackuper och ZIP-backup av gamla 68721143-appen hashverifierades.

Gamla 627E6B93-appen lästes tillbaka: 936 240 byte, 88,781 s, korrekt hash.
App-only-skrivning av 936 384 byte vid `0x10000` tog 43,422 s, exit 0,
”Hash of data verified”; NVS-området skrevs inte.
Installerade binärers SHA-256 enligt journalen:

- Companion: `445D72A0FFE9CE907B9C75DE89566A3ABA1AEBD0951ACA52B24AE9A5F46E6EF4`.
- Firmware: `860896DBAA26C50F18D360946B8E88B39ED1ED1160036DE4B6E348820DE7BC65`.

APP_START via Explorer var 21:23:16.918. Första serialförsöket fick
UnicodeDecodeError; försök två lyckades 21:23:23.271. Resync 21:23:27.048,
ART2-kapabilitet 27.133 och FAST-kapabilitet 27.134 bekräftade åtta chunks
utan extra paus. Ingen felfri initialanslutning påstås.

Tokenfilen var bytebevarad under installationen. Efter lång mänsklig väntan
hade den gamla access-token löpt ut; normal förnyelse behöll samma
refreshtoken och uppdaterade access/expiry. Ingen credentialreset gjordes.

## Verkligt omslagsprov

| Spår | ART_READY | Första sändning | ACK/resultat |
| --- | --- | --- | --- |
| 1 | 21:24:51.919 | 703 ms; SENT 52.624 | art2_decode 53.815; retry avbrutet av nästa spår |
| 2 | 21:25:02.565 | 703 ms; SENT 03.272 | success 04.217: **1652 ms READY→ACK**, 945 ms efter SENT |
| 3 | 21:25:07.880 | 703 ms; SENT 08.581 | art2_line 08.574; retry 1/15 ms tog 9375 ms, success 20.224: **12344 ms READY→ACK** |

Användaren svarade exakt: **”Nope de tar lång tid för vissa, en tog 11 sekunder typ.”**
Kort sändtid räckte alltså inte för snabb, stabil mottagning. Detta är
transport-/mottagarresultat, inte Spotify-upptäcktsfördröjning. Visad commit
tidtogs inte separat. Backlog/paint och byteförlust är möjliga förklaringar;
orsaken är inte bevisad och ingen Waiting-fix påstås.

Status 21:25:53.939: ansluten, desktopstatusålder 1,002 s, ESP-statusålder
cirka 1,299 s, uptime 144 s, heap 154 064/min 151 540 av 261 056,
CPU-mätare av, aktiv API-takt 5 s och Windows Spotify false. Fullständiga
UI-/touch-, arm-, långdrifts- och sleep/resume-prov är inte godkända här.

## Underlag och dokumentgräns

Enda runtimekälla i detta dokumentsteg är den frysta innehållsfria journalen
`%LOCALAPPDATA%/BongoDesk/deployment-artwork-fast921600-20261018-201303-202709-speed-test-baseline.json`,
SHA-256 **EE3017E64E7D31AAC34309C2E155A3A9E78B5791B586E3C076BE88AF99B96CF2**.
Backup-/logg-/profilreferenser i journalen följdes inte. Code ändrade endast
denna rapport och aktuella toppstatusar i 00/01/02; inga tester, byggen,
produkt-, runtime-, profil-, API-, flash- eller installationsåtgärder utfördes.
Tidigare frysta C/B/627-underlag bevaras före nästa avgränsningsval.

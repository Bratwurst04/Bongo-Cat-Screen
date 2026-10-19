# Kattarm/tempo – flash och återstart 2026-10-18

Installerat par är nu **companion 68721143 / firmware 627E6B93**.
Användaren gav Lead ”Flasha”, bekräftade BOOT/RESET med ”klar” och normal
reset med ”japp”. Tider nedan är svensk sommartid, UTC+02.
Detta dokument kompletterar den oförändrade
[byggrapporten](turntable-arm-tempo-2026-10-18.md); dess föreflashstatus och
frysta manifest är historiska bevis och har inte skrivits om.

## Verifierad skrivning

Lead stoppade companion under befintligt byte-0-ledgerlås, med pending=0.
Tre privata profilbackuper hashverifierades. Companion ersattes inte och
inga nya lösa EXE skapades.

Gamla firmwareappen lästes på COM6/115200: **932 080 byte**, 85,2 s, exit 0.
Backup `.pio/device-backups/turntable-arm-tempo-20261018-1931-preflash-app-0x10000-55669C87.bin`
har exakt SHA-256 **55669C87CF8459996F173154691C6002B02D4DA193BAF13C3CBA801E18B40577**.

Esptool 5.3.1 skrev **936 240 byte** vid `0x10000`, endast appområdet
`0x10000–0xF4FFF`, på 39,0 s med exit 0 och ”Hash of data verified”.
Skrivningen avslutades 19:35:27.886. NVS-området skrevs inte; ingen fullbild
eller bootloader skrevs.
Appfil `.pio/candidates/turntable-arm-tempo-2026-10-18-627E6B93.bin`:
**627E6B93F3A4B2CC4E649C5EAF3D4FCA1164EB9989339B6A4AFFEB25B9E6D571**.
Code har skrivskyddat verifierat kandidatens, backupens och huvudappens hashar.

## Återstart och observation

Efter bekräftad normal reset startade Lead oförändrad kanonisk companion
via Explorer/ShellExecute `--startup` 19:36:44.907. Processparet var
34256/41888, med Explorer 12356 som förälder till huvudprocessen; appen kör
fristående från Codex. Huvudappen är **19 656 698 byte**, SHA-256
**687211432857B34424EDA3D203F645C7324C0639D2F2308367D185987BBB5A50**.

APP_START loggades 19:36:46.774. Första serieanslutningen misslyckades
19:36:48.957 med `UnicodeDecodeError` i `serial_open`; försök två lyckades
19:36:53.102. Orsaken fastställdes inte. Resync följde 19:36:56.848 och
art2-kapabilitet bekräftades 19:36:56.944. Initialstarten var alltså inte
felfri.

Observation 19:37:09.436: desktopstatusålder 0,009 s, ESP32 ansluten,
ESP-statusålder cirka 4,39 s, uptime 9 s, heap 154 408/min 153 604 av
261 120 byte, CPU-mätare av. Journalen bekräftar bevarad apphash,
konfiguration, credentialfält och autostart. API gav 204/empty; ingen aktiv
omslagsleverans var därför bekräftad i denna observation. Ingen Waiting-fix
påstås och Spotify-felsökningen förblir pausad.

Senare observation 19:39:14.752 visade aktiv API-takt 5 s, uptime 140 s,
heap 154 240/min 151 572 av 261 072, fortsatt kontakt och bevarad profil/app.
Två art2-överföringar lyckades: SENT 19:38:18.307, 5453 ms, ACK 18.357
(50 ms senare), samt SENT 19:39:00.249, 5358 ms, ACK 00.260 (11 ms).

## Fysiskt svar, provgränser och underlag

Efter Leads instruktion att starta/byta låt och pausa/återuppta svarade
användaren **”Ja. Armen kan bli lite tjockare”**. Det bekräftar kvalitativt
ansluten vit kattarm, lyft/nedläggning och tonarm play/pause. Önskemålet gäller
den vita underarmen, inte tonarmen, och hanteras som en separat revision.
Sällsynt komplett byte, Fokus, samtliga gester, uppmätt TFT-takt/stackmarginal,
långdrift och sleep/resync är fortfarande oprövade här.

Driftjournal: `%LOCALAPPDATA%/BongoDesk/flash-turntable-arm-tempo-20261018-193122-414828.json`.
Läs-/skrivloggar finns under `.pio/device-backups/` med prefix
`turntable-arm-tempo-20261018-1931-`.
Detta dokumentsteg ändrar endast rapporten och aktuella toppstatusar;
produktkälla, tester, kandidater och frysta bygg-/previewunderlag bevaras.
Inga nya kodtester, byggen, API- eller runtimeåtgärder utfördes av Code.

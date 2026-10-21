# Skivflip/ö – installerat par och grundläggande driftprov 2026-10-16

## Status och underlag

**Companion 0D397F89 och firmware C7E594B4 är installerade av Lead.
Användaren har kvalitativt bekräftat: ”Flip och ö fungerar”.**
Detta är grundacceptans av skivflip och tecknet ö vid låtbyte. Det är inte
ett genomgånget åäöÅÄÖ-ark, alla layouter/gester eller uppmätt prestanda.
**Seek finns nu i den installerade firmwaren men är fortfarande inte
skärmprovat eller fysiskt accepterat.**

Användaren godkände det specifikt föreslagna parets installation/flashning
med **”Yes kör”**. Lead genomförde bytet den 16 oktober. Alla tider nedan är
**2026-10-16, Europe/Stockholm**. Rapporten bygger på Leads verifierade
installations-/flashuppgifter, användarens svar och det tillåtna säkra
runtimeprotokollet. Inga medietitlar, artistuppgifter, omslags-URL:er,
konfigurationsvärden eller credentials återges.

Den [frysta r2-bygg-/källrapporten](record-flip-utf8-r2-2026-10-15.md)
behåller sitt läge före installationen. Denna separata rapport redovisar
senare driftbevis. Äldre kandidater, källkopior, bygg-/previewrapporter,
manifester och releasefiler har inte ändrats.

## Exakt installerat par och återställningsunderlag

| Del | Verifierat resultat |
| --- | --- |
| Installerad companion | `C:\Users\gusta\AppData\Local\BongoDesk\BongoDeskSpotify.exe`, **19657256 byte** |
| Companion SHA-256 | **`0D397F89DCBC5C6B648517268A08B1D4E9DBEF23B7BAFD9B51816EBE77850ADD`** |
| Installerad firmwareapp | **932720 byte**, endast app vid `0x10000` |
| Firmware SHA-256 | **`C7E594B462D0025B1BE00BFE70C535153326E18DCE4CA29017B4D84712AD7DFB`** |
| Deploymentprotokoll | `C:\Users\gusta\AppData\Local\BongoDesk\deployment-record-flip-20261016-104301-321558.json` |
| Companion-rollback | `C:\Users\gusta\AppData\Local\BongoDesk\BongoDeskSpotify.backup-20261016-104301-321558-pre-record-flip-17466EBF.exe`, hashverifierad av Lead |
| Rollback SHA-256 | `17466EBFC95B14FDFB93D717BB9700F5937087AC27933CCDF82DF98E8C77C1C0` |
| Före-flashbackup | `.pio/device-backups/record-flip-20261016-1044-preflash-app-0x10000-F406C485.bin`, **928960 byte** |
| Backup SHA-256 | **`F406C485C775E3D907A04BC82620CB305E4EC48FAC10F0CF52754DB508EA2984`** |
| Säker runtimejournal | `C:\Users\gusta\AppData\Local\BongoDesk\runtime-record-flip-20261016-104301-321558.json` |

Lead läste före flashning **928960 byte** från `0x10000` med `read_flash`,
**83,6 s**. Den sparade backupen matchade exakt tidigare F406. Kodskrivaren
har i detta dokumentationssteg verifierat backupfilens storlek och hela
SHA-256 skrivskyddat; ingen ny enhetsläsning eller flashning gjordes.

Lead skrev den godkända C7E594B4-appbilden via **COM6/115200**,
**esptool 4.9.0**, `no_reset/no_reset`, **38,3 s**. Verktyget rapporterade
**”Hash of data verified”**. Endast appområdet skrevs och **NVS bevarades**.
Normal drift använder fortsatt **230400 baud**.

## Säkert companionbyte och normal persistens efter start

Bytet gjordes cirka **10:43**, med deploymentstämpel
`20261016-104301-321558`. Lead höll samma **befintliga ledgerlås, byte 0/en
byte**, med **pending=0**, genom stopp/kopiering. Endast processer med exakt
installerad EXE-sökväg stoppades, child före parent. En verifierad
17466-EXE-rollback och separata config-/token-/ledgerbackuper skapades.
Profilbackuperna finns i Roaming/BongoCat med suffix
`.pre-record-flip-20261016-104301-321558.json`.

Config, token och ledger var **byteidentiska genom bytet och fram till
start** enligt Lead; autostart bevarades. Efter start är config oförändrad.
En normal access-tokenförnyelse gav längre expiry; refresh-token, scope
och typ bevarades enligt säkra jämförelseflaggor. Credentials och verkliga
config-/token-/ledgerinnehåll har inte lästs eller exponerats av
Kodskrivaren.

Runtimejournalens `budget_deadlines_preserved=false` betyder att alla råa
deadline-tal **inte** förblev identiska efter start. Lead bekräftade
skrivskyddat att `import_legacy_limits` golvade redan utgångna
`retry_until`/`quota_strong` till dåvarande logiska nu. Det gav ingen ny
väntetid; warm-/soft-/clock-gränser var lika. Aktuell RetryRemaining är
noll och ingen ny 429 observerades. Detta är vanlig återläsning/persistens
efter start, inte en radering eller nollställning av historiken vid bytet.
Ingen API-taktändring gjordes.

## Uppstart, återanslutning och omslag

| Lokal tid | Logg-/statusverifierad händelse |
| --- | --- |
| 10:46:43.417 +02:00 | Installerad EXE startad dolt med `--startup` |
| 10:46:48 | Första serialopen misslyckades |
| 10:46:52 | Serialanslutning lyckades på försök **2** |
| 10:46:55.960 | `DEVICE_RESYNC` |
| 10:46:56.055 | art2-kapabilitet bekräftad |
| 10:47:37.558 | API-låtbyte; **37632 byte** art2, **5203 ms** sändning, lyckad ACK **7 ms** senare |
| 10:47:48.008 | API-låtbyte; **37632 byte** art2, **5218 ms** sändning, lyckad ACK **12 ms** senare |

Normalt processpar var **27952/28776**. Detta är historiska PID:er och ska
aldrig användas som framtida stoppmål. Ny firmware hade färsk uptime och
heap. Ovanstående låtbytestider är appens observationer, inte tidsstämplar
för användarens handlingar eller uppmätt end-to-end-latens.

## Statusstickprov

| Mått | 10:48:10, enligt Lead | Senaste avlästa säkra journalobservation |
| --- | --- | --- |
| Observation / status uppdaterad | 10:48:10 | **10:49:19.169 / 10:49:18.230** |
| ESP32 | Connected | **Connected** |
| Friheap / minheap / total | 154884 / 151964 / 261456 byte | **154860 / 151248 / 261456 byte** |
| Uptime / statusålder | 79 s / 4,506 s | **149 s / 2,060 s** |
| Mediekälla / idle | API / aktiv | `spotify_api` / `idle=false` |
| Effektivt grundintervall / fast | 5 s / false | **5 s / false** |
| API-snapshotålder | Inte angiven här | **1,031 s** |
| Ledger totalt / auto | 842 / 811 | **855 / 824** |
| Aktuella 24 h-gränser totalt / auto | 4000 / 3600 | **4000 / 3600** |
| Reservation / Retry / clockguard | 0 / 0 / 0 | **0 / 0 / 0** |
| Registrerade 429 totalt | 2, oförändrat | **2**, noll senaste 15 min/timme/24 h |

Senaste stickprovet hade sex totala/automatiska anrop i 30 s-fönstret,
mot lokala tak 24/18. Profilen var day, `history_complete=false` och
`quota_recovery=true`. Normal återstående profilväntan var cirka **3,969 s**
(`wait_reason=profile`), ingen aktiv Retry-spärr. PSRAM var 0/0 och
CPU-mätaren av. Det är punktobservationer under kort drift, inte uppmätt
stationär anropsfrekvens, framekostnad, största fria block eller långtids-
stabilitet. Samma befintliga budgetskydd och 5 s daggrund används.

## Fysisk grundacceptans och kvarvarande prov

Lead bad användaren byta mellan ett par låtar och kontrollera snabb flip
till generisk vinyl, sedan nytt omslag, samt korrekt ö. Seek angavs
uttryckligen som ännu inte skärmprovat. Användaren svarade exakt:
**”Flip och ö fungerar”**.

| Område | Faktisk status |
| --- | --- |
| Godkänt byte och flash av exakt par | Utfört av Lead, enligt uppgifterna ovan |
| Serial/resync/art2/omslagskvittens | Loggverifierat, inklusive lyckat anslutningsförsök 2 |
| Skivflip och ö vid grundläggande låtbyte | **Kvalitativt fysiskt accepterat** av användaren |
| Komplett åäöÅÄÖ, långa namn och rullkanter | Ingen separat full fysisk genomgång |
| Normal/kompakt, paus, snabba byten och avbrutna flips | Utökad fysisk acceptans väntar |
| DJ, Fokus, meny/panel, övriga gester och progress | Utökad fysisk acceptans med detta par väntar |
| Seek | **Ingår i installerad C7E594B4 men ännu inte skärmprovat/fysiskt accepterat** |
| Sleep/resume, mörka timerväckningar och ljusblixt | Fysisk acceptans med detta par väntar |
| Exakt flip-/omslagslatens, FPS, soak och största heapblock | Inte uppmätt; korta heapstickprov ovan ersätter inte detta |
| Verklig OOM-fallback | Inte framtvingad eller fysiskt provad |

R2:s **186 PASS/två C++ SKIP** och UI:s simulationsgodkännande är tidigare
bygg-/granskningsbevis från 15 oktober. Inga nya kodtester kördes i detta
dokumentuppdrag och dessa äldre bevis utökas inte till fysisk acceptans.

## Dokumentationskontroll

Kodskrivaren har bara skapat denna rapport. Tillåtna runtimeuppgifter och
firmwarebackup har lästs skrivskyddat; inga credentials/configvärden,
processåtgärder, API-anrop, installationer eller flashningar ingick.
UTF-8/whitespace och `git diff --check` är **PASS**. Fingeravtryck för
**487 övriga befintliga projektfiler är oförändrade**. Befintliga lokala
käll-/test-/previewändringar bevaras. Lokal Git-bas och enligt Lead även
GitHub-grenen `codex/runtime-artwork-speed` är fortsatt **83cc460**;
ingen ny commit/push/release gjordes.

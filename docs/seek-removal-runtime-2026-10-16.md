# Installerat par utan seek – drift 2026-10-16

Alla tider är Europe/Stockholm. Underlag är de innehållsfria
[installationsuppgifterna](C:/Users/gusta/AppData/Local/BongoDesk/deployment-seek-removal-20261016-115421-353808.json)
och [driftjournalen](C:/Users/gusta/AppData/Local/BongoDesk/runtime-seek-removal-20261016-1159.json),
lästa skrivskyddat. Lead utförde versionsbytet efter användarens uttryckliga
”Ja, byt till paret utan seek”.

## Installerat och bevarat

| Del | Byte | SHA-256 |
| --- | ---: | --- |
| Companion **4D4A84E8** | 19655221 | `4D4A84E86F5439FF80F555AD10A7C8003EFBC950E3B24ABE51105D9E1D28DC82` |
| Firmware **55669C87** | 932080 | `55669C87CF8459996F173154691C6002B02D4DA193BAF13C3CBA801E18B40577` |

Detta är senare installationsstatus än den frysta
[bygg-/före-start-rapporten](seek-removal-2026-10-16.md).
Den breda kontextens uppgifter om installerat **26A0/C7** avser läget före
bytet. Kontextfilerna och det frysta 154-filsmanifestet är oförändrade;
denna separata rapport anger det nu installerade paret.

Companionen kopierades 11:54:24 med verifierad **26A0FAF0**-backup.
Samma befintliga ledgerlås hölls under stopp/kopiering, pending var noll,
profilfilerna var byteidentiska före start och autostart bevarades.
Ingen profilreset eller API-policyändring ingick.

Före flashning lästes tidigare C7-app tillbaka på 84,4 s till
[firmwarebackupen](../.pio/device-backups/seek-removal-20261016-1159-preflash-app-0x10000-C7E594B4.bin).
Code kontrollerade filens 932 720 byte och SHA-256
`C7E594B462D0025B1BE00BFE70C535153326E18DCE4CA29017B4D84712AD7DFB`.
Lead skrev sedan endast appen vid **0x10000**, COM6/115200, med
esptool 4.9.0: 38,3 s, exit 0 och ”Hash of data verified”. NVS bevarades.
Användaren bekräftade vanlig reset. Normal drift är 230400 baud.

## Uppstart och omslag

Start begärdes kring 12:01; APP_START loggades 12:01:03.317.
Första seriella försöket **misslyckades** 12:01:05.502 med
`UnicodeDecodeError`/serial_open. Försök två lyckades 12:01:09.664.
Orsaken till det första felet är inte fastställd här. Därefter följde
naturlig API 200 med track och DEVICE_RESYNC 12:01:13.440.

Uppstarten använde först legacy-omslag. Första överföringen tog 9 218 ms
och fick ACK 15 ms efter ART_SENT. Resync följdes av en andra på 9 203 ms:
ACK loggades 12:01:31.709, före ART_SENT 12:01:31.729. Någon kvittenslatens
beräknas inte ur den ordningen. Art2-kapacitet bekräftades 12:01:22.557.

Senare naturliga låtbyten gav lyckad art2 på första försöket, 37 632 byte:

| MEDIA_TRACK | ART_SENT | Sändtid | ACK efter ART_SENT |
| --- | --- | ---: | ---: |
| 12:02:32.274 | 12:02:37.632 | 5296 ms | 7 ms |
| 12:02:42.789 | 12:02:48.202 | 5359 ms | 9 ms |

Detta är sändnings-/kvittensevidens, inte uppmätt tid från mobilhandling
till färdig skärmbild.

## Nytt fysiskt besked och färsk status

Användaren svarade **”ja”** på: ”Byt låt en gång i mobilen. Visar skärmen
rätt låt och omslag, med skivflippen som tidigare?” Det bekräftar
kvalitativt låttext, omslag och flip på **4D4A/5566**. Journalens
registreringstid 12:03:26 är inte mobilhandlingens uppmätta tidpunkt.
Äldre ö-/gestacceptans på C7 räknas inte automatiskt som nytt prov.

Status 12:03:29 visade ansluten ESP32, Spotify ready/API aktivt 5 s,
uptime 139 s och statusålder 2,713 s. Heap var 154 888 byte, minimum
152 000 och total 261 464. Budget var 1 445 total/1 343 auto av
4 000/3 600; reserver, Retry-väntan och klockspärr var noll. Totalt 429
var fortsatt två, senaste timmen noll. Den normala processkombinationen
var parent 17116/child 8672. Config och access_token/refresh_token/expires_at
var oförändrade mot installationsbackupen enligt journalens jämförelse.
CPU-mätarflaggan var av efter reset; ingen configändring gjordes.

## Vänteläget återkom

Användaren rapporterade senare att Waiting återkom trots fortsatt musik
och tickande tid på mobilen. Automatisk 200/track 12:03:24.970 följdes
av **204/empty** 12:03:30.155 och 12:04:00.383. Det naturliga kontrolltrycket
12:04:13.133 gick genom accepted → started → urgent GET 204/empty
12:04:13.315 → completed/manual empty 12:04:13.336. Läskedjan fungerar,
men gav åter ingen låtdata.

Status 12:04:46 hade färsk ESP32-kontakt och API ready, nu idle/30 s.
Budget var 1 448/1 345, reserver/Retry/klockspärr noll och totalt 429
fortsatt två. Config och credentialfält var fortfarande oförändrade.
Det tidigare godkända enkla mobilbytet innebär därför inte stabil
uppspelningsföljning. Orsaken till de tomma svaren är okänd; ingen
permanent rättning påstås.

## Begränsningar och dokumentkontroll

Den olösta testvariabiliteten från byggsteget kvarstår: senaste hela
körningen gav 180 PASS/2 SKIP, men tidigare körningar hade varierande fel
utan fastställd orsak. Det korta driftprovet bevisar ingen fixturfix eller
långsiktig stabilitet. Full UI-/gestgenomgång, separat åäö-prov,
sleep/resume och långdrift med detta par är fortfarande oprövade.
Inga fler seekprov beställdes.

Endast denna nya driftrapport tillkommer. Produktkälla, tester, binärer,
154 aktuella och 154 frysta källhashar, byggmanifest, före-start-rapport
och äldre underlag är bevarade. `git diff --check`, separat UTF-8-/textkontroll
och jämförelse mot dokumentuppdragets filbaslinje är godkända.
Inga nya kodtester eller runtimeåtgärder utfördes av Code för rapporten.

# Devices-diagnos: installation och drift – 2026-10-17

Alla tider är Europe/Stockholm. Detta kompletterar den oförändrade
[bygg-/testrapporten](devices-diagnostics-2026-10-17.md) med faktiskt driftutfall;
det är ingen fix- eller stabilitetsacceptans.

## Par, installation och underlag

Efter användarens uttryckliga ”Ja, installera diagnosappen” installerade Lead:

- Companion: **19 656 698 byte**, SHA-256
  `687211432857B34424EDA3D203F645C7324C0639D2F2308367D185987BBB5A50`,
  på `C:\Users\gusta\AppData\Local\BongoDesk\BongoDeskSpotify.exe`.
- Firmware: `55669C87CF8459996F173154691C6002B02D4DA193BAF13C3CBA801E18B40577`,
  oförändrad och inte flashad i detta steg.

Det enda externa underlaget som Code läste är den
[frysta innehållsfria journalen](C:/Users/gusta/AppData/Local/BongoDesk/runtime-devices-diagnostics-20261017-1430-baseline.json),
med observationerna **14:29:21/14:30:32**. Verifierad SHA-256:
`5F5D436802E2536FB76F1AF2C47993B262544B0E56FE83EF7052E8827939AC8C`.
Installationsdetaljer nedan är Leads redovisning; ingen separat profil-/tokenläsning gjordes.

Befintligt ledgerlås vid byte 0 hölls öppet `r+b` under stopp/kopia,
pending=0. Config, tokens och ledger var byteidentiska under bytet, med
hashverifierade backuper. Run och båda nya genvägarna var byteidentiska.
Kvitto: `C:\Users\gusta\AppData\Local\BongoDesk\deployment-devices-diagnostics-20261017-142803-494082.json`.

Rollback finns som ZIP, utan extra lös EXE:
`C:\Users\gusta\AppData\Local\BongoDesk\archives\pre-devices-diagnostics-20261017-142803-494082-3EDD2187.zip`,
SHA-256 `A6C61AAFFC467EE9E7760ACEF21E1E82E6C01EB82BF6291F3039769CAD16B372`.
Entry `BongoDeskSpotify-3EDD2187.exe` har verifierad SHA-256
`3EDD2187F4DB3F550FF6C2D0342ED6E4BB38EB97BEE5EF6122B7988C738A0A4A` enligt Lead.

## Observerat A→devices→A

Start via befintligt Explorer-skal **14:28:25.133**, APP_START **14:28:27.773**,
SERIAL_CONNECT på första försöket **14:28:29.940**, art2-kapabilitet **14:28:33.218**.
Normalt processpar: 37336/39128; 39128 hade Explorer 12156 som förälder.
Detta är en punktobservation, inte ett ChatGPT-omstartsprov eller långdriftsbevis.

| Läsning | Tid | HTTP/utfall |
| --- | --- | --- |
| A, playback_state | 14:28:33.355 | 204 |
| Devices | 14:29:03.548 | 200 |
| Devices-body | 14:29:03.555 | valid; samtliga sex antal 0 |
| A | 14:29:33.800 | 204 |
| A | 14:30:04.198 | 204 |

Antalen var totalt, aktiva, smartphones, aktiva smartphones, private och
restricted. **Ett faktiskt devices-HTTP**, completed/attempt=1; ingen
401-retry, extra B eller metadatafallback observerades. Snapshotålder
46,609 s vid 14:29:21 är förenlig med att devices inte förnyade A-åldern;
efter senare A var den 24,953 s vid 14:30:32.

Källa API, WindowsSpotify=false, ready, idle 30 s och färsk ESP32-status
(1,960 s). Totalt 429 fortsatt två, senaste timmen noll; Retry,
klockspärr och reserver noll. Config och genvägar matchade installationen.
Enligt Lead föregicks bytet av fortsatta A204 kl. 14:25:37/14:26:07/14:26:38
med användarbekräftad bakgrundsmusik. Appomstarten återställde inte metadata.

**Avvikelse:** CPU-mätaren observerades AV före omstart, medan sparad config
redan hade true och var byteidentisk vid kopian. Efter start var telemetrin
PÅ genom befintlig startkods återsändning av sparat DIAG_CPU-värde.
Installationen ändrade inte config; detta är ingen ny diagnosfunktion.
Lead gjorde ingen flaggändring i samband med DNS-begäran.

## Tolkning och väntande prov

Tom giltig enhetslista stärker Connect-synlighets-/rapporteringsspåret,
men listans dokumenterade ofullständighet, kontoidentitet och iPhone kontra
tjänst/nät lämnar slutorsaken obevisad. Telefonläget är senast användarrapporterat;
ingen Spotify-foreground begärdes i detta steg. Ingen rättning fastställs.

Användaren klargjorde att 1.1.1.1 är **appen i DNS-only, WARP AV**.
Det tidigare Wi-Fi/mobildataprovet uteslöt därför inte DNS-profilen.
Lead har begärt tillfällig avstängning även av DNS i 60 s, med Spotify kvar
i bakgrunden. **Svar/resultat väntar i detta frysta underlag.** Inga senare
data ingår.

Endast denna rapport tillkommer. Kandidatrapport, frysta källor, binärer,
manifest, tester och tidigare rapporter bevaras. Code utförde ingen runtime-,
profil-, test-, bygg-, API-, process-, commit/push- eller releaseåtgärd.

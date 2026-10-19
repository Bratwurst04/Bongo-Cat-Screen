# Installerad endpointdiagnostik – drift 2026-10-16

Alla tider är Europe/Stockholm. Underlag är skrivskyddat lästa,
innehållsfria journaler för
[installation](C:/Users/gusta/AppData/Local/BongoDesk/deployment-playback-endpoint-diagnostics-20261016-153513-828690.json),
[drift till 15:40:14](C:/Users/gusta/AppData/Local/BongoDesk/runtime-playback-endpoint-diagnostics-20261016-1535.json)
och [omstart av samma version](C:/Users/gusta/AppData/Local/BongoDesk/restart-endpoint-rearm-20261016-153921-561190.json).
Lead utförde installation, start och omstart. Code dokumenterar enbart.

## Installerad version och skydd

Användaren godkände 15:34: **”Ja, installera diagnosappen”**.
Installerad companion är **3EDD2187**, 19 656 263 byte, SHA-256
`3EDD2187F4DB3F550FF6C2D0342ED6E4BB38EB97BEE5EF6122B7988C738A0A4A`.
Firmware är fortsatt **55669C87**, SHA-256
`55669C87CF8459996F173154691C6002B02D4DA193BAF13C3CBA801E18B40577`.
Ingen flashning gjordes; seek är fortsatt borttaget.

Lead verifierade rollback-EXE **4D4A84E8**, höll samma befintliga
byte-0-lås med pending=0 under stopp/kopiering och bevarade autostart.
Config, tokenfil och budgetfil säkerhetskopierades och var byteidentiska
genom installationen och inför start. Uppgifterna om backup och sökvägar
finns i installationsjournalen; inga hemliga värden lästes av Code.

Den frysta [bygg-/före-start-rapporten 0DC6](playback-endpoint-diagnostics-2026-10-16.md)
beskriver läget före detta versionsbyte. Dess källor, paketbevis och
versionsuppgifter är historiska byggbevis och skrivs inte om här.

## Första appsessionen: A–B–A under paus/stopp

APP_START loggades 15:36:15.321, seriell anslutning lyckades på första
försöket 15:36:17.493 och art2-kapacitet bekräftades 15:36:20.763.

| Automatiskt lästillfälle | Endpoint | Svar |
| --- | --- | --- |
| 15:36:20.887 | A: playback_state | 204/empty |
| 15:36:51.094 | B: currently_playing | 204/empty |
| 15:37:21.450 | A: playback_state | 204/empty |

B hade accepted, started 15:36:51.006 och completed 15:36:51.102,
**ett försök** och request_kind playback_poll. Detta visar den installerade
diagnosvägen över ordinarie cirka 30-sekundersplatser och återgång till A.

Användaren sade dock **”Nej, den är pausad eller stoppad”** under fasen.
Sekvensen är därför inte ett bekräftat Waiting-fel med pågående musik,
ingen skillnad mellan endpoints i ett sådant fel och ingen felfix.

Användaren startade sedan musik och svarade ”spelar”. A gav 200/track
15:37:51.814. Art2 överförde 37 632 byte på första försöket, 5 531 ms,
med ART_SENT 15:37:57.436 och lyckad ACK 40 ms senare. Fler A200 följde.
Mobilhandlingens exakta tid och ändringslatens mättes inte separat.

Status 15:38:32 visade API aktivt **7,5 s**, budget 2 356/2 243 av
4 000/3 600 och pressure 0,623. Det effektiva intervallet följer den
befintliga tryckpolicyn; grundtakten fem sekunder och config är bevarade.
Det är ingen ny frekvensändring i diagnoskoden.

## Säker omstart för ett nytt jämförelsetillfälle

Eftersom engångstillfället hade förbrukats under paus/stopp startade Lead
om **samma 3EDD-binär** efter att uppspelningen återkommit. Pending var
noll; profilerna var byteidentiska under stopp och inför start. Ingen
binär ersattes och ingen profil eller skyddshistorik återställdes.

Den nya appsessionen gav APP_START 15:39:23.927, anslutning på första
försöket 15:39:26.093 och art2-kapacitet 15:39:29.376. Befintlig
profilspärr väntade 20 s vid 15:39:29.410. Ingen extra GET eller bypass
gjordes. Därefter kom A200/track 15:39:49.642, 15:39:57.655 och
15:40:05.590. Art2 på första försöket tog 5 265 ms: ART_SENT
15:39:54.972, lyckad ACK 15:39:55.004, 32 ms senare.

**Inga nya SPOTIFY_ENDPOINT_DIAGNOSTIC-händelser** fanns i denna
appsession fram till 15:40:14. Ny jämförelse vid ett verkligt
uppspelningsavbrott är alltså fortfarande väntande.

## Slutstatus och begränsningar

Status 15:40:14 visade ansluten ESP32, Spotify ready/API aktivt 7,5 s,
heap 154 844 byte, minimum 151 272, total 261 464, uptime 13 147 s och statusålder
0,320 s. Budget var 2 366 total/2 253 auto av 4 000/3 600; kortgränserna
var 24/18. Reserver, Retry-väntan och klockspärr var noll; totalt 429
fortsatt två. Parent/child var 14588/4004 på den installerade sökvägen.
Config och access-/refresh-/expiry-fält var oförändrade mot färsk backup
enligt journalen. CPU-mätarflaggan var på enligt tidigare användarval;
ingen configändring ingick.

Ingen permanent rättning eller telefon-/endpointorsak är bevisad. Den
tidigare olösta testvariabiliteten kvarstår trots byggstegets senaste
196 PASS/2 kända SKIP. Detta korta driftprov löser inte den begränsningen.
Ny full UI-, ö-, flip-, gest-, sleep/resume- eller långdriftsacceptans
antas inte. ACK visar överföring, inte en ny visuell helhetsbedömning.

Endast denna nya rapport tillkommer. Alla 155 aktuella och 155 frysta
källhashar, binärer, manifest, före-start-rapport och äldre underlag är
bevarade. `git diff --check`, separat textkontroll och jämförelse mot
dokumentuppdragets filbaslinje är godkända. Inga nya tester, bygg-,
profil-/API-/runtimeåtgärder, commit, push eller release gjordes av Code.

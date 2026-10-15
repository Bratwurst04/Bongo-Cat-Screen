# Förebyggande Spotify API-budget – utvecklingsprojekt 2026-10-14

## Status och avgränsning

**Källa, simulering och separat EXE verifierade och frysta. Drift/hårdvara väntar.**
Lead har valt **5 s dagspelande med utglesning vid budgettryck** efter
jämförelse med 10 s. Kandidaten ska granskas separat före drift.
Arbetsyta: `D:\DEV\Ai\Github\Bongo-Cat-Screen`.
Nattprofilen är användarvald **00–08, Europe/Stockholm**, konfigurerbar.
Ingen layoutändring föreslås. Nya förklaringar kan först ligga i statusdata.

Aktuell källa inkluderar seek-integrationen från 2026-10-12. Dess frysta
57894EE0-firmware och A52946E5-companion ska behållas som separata artifacts,
med manifests/rapporter; seek-skärmprovet är uppskjutet. Installerat par är
fortsatt F406/68CC. Ingen firmwareändring, flashning, kandidatstart,
processkontroll, installation, commit, push eller release ingår här.
Utveckling och nätprov använder isolerade profiler/fejkad HTTP. Den riktiga
profilen och tokenfilen ska inte ändras av Kodskrivaren.

Separat före-baslinje: `build/api-budget-2026-10-14/baseline/`.
58 käll-/test-/dokumentfiler och 91 bevarade artifacts är inventerade med
SHA-256. Vid före-baslinjen matchade 52 källhashar det tidigare frysta seek-manifestet.

## Verifierad incident, återgiven från Lead

2026-10-14 **01:48:15.431 svensk lokal tid** på installerad companion
`68CC5BC1D90E0AB734D0997D03980653858C717F88AB4B97E42648E6DC93FE97`:

- `SPOTIFY_API_429`, `reason=quota_exceeded`, `request_kind=playback_poll`.
- Retry-After **49473 s**, tidigast återförsök **15:32:48 samma dag**.
- 59 anrop senaste 30 s, intervall 500 ms, nästa inlärda intervall 1000 ms.
- Totalräknare 217263; totalt två registrerade 429.
- Det 656 s långa användningsfönstret innehöll 1277 playback_poll och inga
  urgent/artwork_fallback/control/other.
- Från 00:07:08, total 206966, till incidenten tillkom **10297 anrop**.
- 27 API-låtuppdateringar registrerades 00:16:23–01:47:09.
- Idle före uppspelningen: 60 anrop/15 min; därefter ungefär 1747–1751.
- Omkring **29 000 lokala anrop under föregående 24 h** är jämförelsedata,
  inte en publicerad gräns. Efter 429 stod räknaren still; aktuell källa
  var senare lokal Windows-Spotify med noll API-anrop senaste 15 min.

Detta visar en kvotklassificerad incident efter många automatiska läsningar.
Det visar **inte en bestämd dagskvot** eller vilka andra appar som använde
developer-kontots bucket. Den sparade riktiga spärren ska behållas.

## Externa gränser och faktisk kod

Spotify beskriver rate limits som ett rullande 30-sekundersfönster med
varierande gränser samt separat development-kvot per developer account och
grupperade endpoint-buckets. Exakta grupper/gränser kan ändras.
Lokala budgetar nedan är därför försiktiga produktval, inga Spotify-garantier.
[Rate limits](https://developer.spotify.com/documentation/web-api/concepts/rate-limits),
[Quota modes](https://developer.spotify.com/documentation/web-api/concepts/quota-modes).

Baslinjens `spotify_api.py` hade en låst anropsstartgräns, 30 s/15 min
processräknare, sparad Retry-After, 24 h-historik över **429-händelser** och
ett 60 s automatgolv efter QUOTA. Den saknade persistent 24 h-historik
över alla API-anrop och förebyggande totalbudget. Ren drift började på
minimum 0,5 s; återhämtning minskar backoff 10 % efter rena 30 s-fönster
när kvotskyddet löpt ut. `api_max_interval_seconds` är backofftak, inte
ett tak som får hindra längre budget-/natt-/Retry-After-väntan.

Bridge använder Windows-Spotify först och låter inte andra Windows-spelare
dölja Connect. Vanlig Windows-session kräver inga playback-API-polls;
befintlig thumbnail-fallback kan behöva en budgeterad API-läsning.
Seek har färsk API-läsning → PUT → vanlig bekräftelse, kontext-/källskydd,
fyra bounded requests och fem sekunders livslängd. Alla dessa vägar ska
behållas. Tokenförnyelse/OAuth och CDN-bildhämtning är separata från Web API
och ska redovisas som sådana, utan nya playback-prober.

## Signaler som finns lokalt

| Signal | Underlag / begränsning |
| --- | --- |
| Faktisk tangentaktivitet | `engine.on_key_press` räknar fysisk utskrivbar tangent/space en gång; modifiers/repeat ignoreras. Billig aktivitetssignal efter befintligt datalås; inga tecken lagras i nya policyn. |
| Explicit skärmkommando | Validerad MEDIA_CMD, inklusive seek; befintlig serial-reader. Panel-/Fokus-touch skickar inga sådana kommandon och är därför ingen tillgänglig aktivitetssignal. |
| Spelande/pausad/ingen uppspelning | Befintlig Windows-timeline eller redan budgeterad API-snapshot. |
| Källa och låtbyte | Befintlig bridge-state; ett automatiskt API-låtbyte är inte bevis för mänsklig interaktion. |
| Anropskostnad/fel | Varje verkligt `/v1`-HTTP-försök i delad guard, inklusive misslyckande/401-retry. |
| Lokal tid | Konfigurerad Europe/Stockholm; natt är profil, inte antagande om sömn. |

Musaktivitet finns inte i nuvarande lyssnare; ingen ny global input-hook
föreslås. En mobilhandling är osynlig tills nästa vanliga poll upptäcker den.
Startupens initialiserade `last_keystroke_time` får inte räknas som faktisk
interaktion. Aktivitetshooken får inte vänta på HTTP-/API-låset.

## Vald modell och standardvärden

### Godkända preciseringar 2026-10-14

- Börja med 5 s dagspelande och jämför med 10 s på identiska 24–72 h-trace;
  rapportera anrop, median/p95/max discovery och tid i budgettryck/full budget.
- Reserven är skyddat ledigt utrymme: auto högst 18/30 s och 7200/24 h;
  explicit får använda ledig **totalbudget** 24/30 s och 8000/24 h, utan
  separata hårda tak på 6 eller 800. Giltiga grants och faktiskt debiterade
  försök krävs även på publika API-metoder; en urgentflagga räcker inte.
- Grants ska rymma verklig 401-retry, tidsbegränsade operationer och
  bekräftelser; unused reservations återlämnas. Kötömning ska även återlämna
  seek-slots. Frysta tidigare seek-artifacts ändras inte.
- Historik ska fördebiteras hållbart och atomiskt, vara bounded och skilja
  faktiskt spent från temporära grants. Corrupt/I/O får inte skapa tom
  budget; klockkontinuitet, minute-kanter och omstart ska testas konservativt.
- Status ska skilja lokal paus från verklig 429. Inga firmware-/layout- eller
  driftändringar. Skrivskyddad granskning visar att CLI:s separat skapade
  SpotifyApiBridge används för OAuth-länkning; den gör inga playback-polls.
  Alla publika Web API-entrypoints ska ändå få samma vakter och ledger.

Tabellen beskriver slutlig källa. Äldre explicita konfigurationsvärden
bevaras, inklusive idle och adaptivt minimum/backoff; högre skydd vinner.

| Skydd / profil | Vald källa |
| --- | --- |
| Absolut minsta startavstånd | 0,5 s; befintligt högre sparat minimum/backoff vinner |
| Rullande kortbudget | Högst **24 verkliga API-försök/30 s**, automatik högst **18**; explicit arbete får använda ledig totalbudget |
| Rullande långtidsbudget | Högst **8000/24 h**, automatik högst **7200**; explicit arbete får använda ledig totalbudget |
| Dag, spelande | Grundintervall **5 s** |
| Natt 00–08, spelande | Grundintervall **30 s** |
| Dag, pausad/ingen | **max(15 s, sparat idle-värde)** |
| Natt, pausad/ingen | **max(60 s, sparat idle-värde)** |
| Kort snabbperiod | **5 s**, högst 10 automatiska polls, minsta avstånd 0,5 s; högre befintligt minimum/backoff gäller |
| Återarmning | Tidigast efter **5 min**, högst **120 snabbpolls/rullande timme**; ytterligare aktivitet förlänger inte pågående period |
| Långbudgettryck | Vid 50/80 % nyttjande sträcks profilgolven till **1,5× / 3×**; snabbperiod nekas från 50 %. Från 80 % sprids kvarvarande utrymme till nästa konservativa minutexpiry med 1 % buffert |
| Full automatbudget | Skjut upp automatpoll/fallback lokalt till äldsta relevanta kostnad kan åldras ut; reservera explicit budget |
| Ofullständig ny 24 h-historik | Första 24 h efter okänd/migrerad historik: halverad **24 h-budget**, automatgolv minst **30 s**, ingen snabbperiod. Status markerar att äldre användning är okänd. |

Kortbudgetens exakta tidsstämplar och långtidsbudgetens räknare ska båda
kontrolleras innan HTTP startar. De är gemensamma för alla endpoint-vägar
och persisteras bounded; ett nytt schema/midnatt får inte nollställa dem.
Fördelningen är en skyddad reserv: automatik kan inte förbruka kommando-
delen. Prioritering tillåter heller inte att totaltak/Retry-After kringgås.

En snabbperiod kan ges av verklig tangentaktivitet eller explicit kommando
bara om budget/backoff tillåter. Den får **inte återarmas eller förlängas
av automatisk ny låt, varje tangent eller upprepad vanlig poll**. Därmed kan
incidentens 27 automatiska låtbyten inte hålla 2 Hz igång hela natten.

## Explicit reserv, livslängd och klassificering

Vanliga kommandon behöver normalt en control och en bekräftelse (två
kostnader); seek behöver förberedande read, PUT och bekräftelse (tre).
Prioritetskostnader måste kopplas till explicit arbete/bounded bekräftelse,
så `urgent=True` inte blir en allmän budgetgenväg för automatpollning.
Förberedande reservering ska rymma operationens kostnad; oanvänd del
frisläpps när operationen misslyckas, avbryts eller går ut. Reserveringen
är tre försök för control och fyra för seek, inklusive en möjlig 401-retry.

Behåll seek-köns fyra slots/fem sekunder och dess källa/låtnyckel. Vanliga
API-kontroller har också en bounded kö och kort utgångstid
(åtta väntande, fem sekunder) så budgetstopp inte skapar försenad replay.
Bekräftelser har en separat bounded deadline (tio sekunder)
och återanvända vanlig snapshot. Windows-kontroller går via lokal session
och förbrukar ingen API-reserv. Kvot-/källbyte tömmer/frisläpper arbetet,
inklusive seek-slots; inget nytt command skickas efter en lång spärr.

## Långsam kvotåterhämtning och tidsintegritet

Retry-After är alltid den överordnade spärren för **alla** API-anrop, även
urgent/seek, natt/dag, aktivitet, omstart, settingsändring och manuellt reset.
Budgethistorik får inte nollställas av "reset safety".

Implementerad återhämtning efter QUOTA, räknad från Retry-After-slut:

1. Första 24 h: automatgolv minst 60 s, halverad lokal 24 h-budget, ingen
   snabbperiod. Befintlig längre spärr/golv vinner.
2. Följande 48 h: automatgolv minst 30 s, 75 % av 24 h-budgeten, ingen snabbperiod.
   Försiktig inlärning tidigast efter sex rena, faktiskt observerade timmar
   per steg; minska högst 10 %. En ny QUOTA startar om skyddet.
3. Kort vanlig rate limit: rent återhämtningsfönster tio minuter
   per 10 %-steg. Den långa kvotincidenten får inte glömmas efter 30 s.

Kortbudgetens totaltak 24/18 behålls även i guarded återhämtning;
snabbpoll är avstängd och automatgolven är minst 30/60 s.

Anropshistorik lagras separat från credentials, som bounded UTC-minut-
aggregat (högst 1441 tidsbucketar för 24 h) med räknare/kategorier,
klockcheckpoint och skyddsdeadline. Kortfönstrets högst 24 starter och
snabbperiodskostnader sparas också. Kostnad/reservation måste hållbart
registreras före HTTP; avbruten process kan överskatta men inte återanvända
en redan förbrukad budget. Ingen metadata/token/URL/klient-id ska lagras.

Profilen beräknas från lokal tid; budget/Retry-After är UTC plus monoton
förfluten tid. Midnight/DST/schemabyte påverkar bara nästa profilgolv.
Monotont startavstånd hindrar burst efter sleep/resume. Vid bakåtklocka
eller stor avvikelse mellan UTC och monotont checkpoint behålls historik
och kända återstående spärrar konservativt, snabbperiod nekas och status
förklarar klockskyddet. Osäker kontinuitet efter omstart får inte ge tom
budget eller radera en framtida spärr. Exakt konservativ rebasering ska
bevisas i klock-/restarttester; det kan ge extra lokal väntan vid fel klocka.
Timezone-data för Europe/Stockholm måste finnas i båda paketerade körvägar.

## Latens och förväntad kostnad – beräkningar, inte körresultat

Utan budget/backoff/HTTP-fördröjning kan ett mobilbyte upptäckas senast
nästa poll: dag spelande cirka 5 s, natt spelande cirka 30 s, dag idle
minst vald 15 s, natt idle 60 s. Snabbperiodens 0,5 s gäller bara dess
budgeterade fem sekunder. Verklig discovery inkluderar HTTP-tid; omslag
har dessutom befintlig download/art2-tid. Tangentaktivitet kan väcka en
lokal väntan, men kan inte skapa fler tillåtna anrop.

Utan interaktion ger nattens 101 min 7 s ungefär **203 läsningar** med
30 s-grundprofil, mot incidentens 10297 observerade anrop. Detta är en
ramberäkning, inte reproducerad incidenttrafik eller bevis för undviken 429.
Äldre loggutdrag saknar ett fullständigt input-/playback-/HTTP-latenstrace;
simulatorn måste märka antagna segment. Ingen omedelbar mobilupptäckt kan
lovas medan automatpollning är uppskjuten eller serverns spärr är aktiv.

Andra appar/användare under samma developer account förbrukar osynlig
bucket-kvot. Lokal budget kan reducera denna apps kostnad, men kan inte
garantera att externa rate-/kvotstopp undviks.

## Verifierad källimplementation

- `companion/api_budget.py`: central policy, strikta numeriska standarder,
  bounded historik, delade profiltransaktioner och operation-grants.
- `spotify_api.py`: alla `/v1`-vägar delar slutguard och kostnader. OAuth
  förbereds först. Under profilens lås sparas pending hållbart, därefter
  kontrolleras tid/grant/Retry/seek-kontext igen innan HTTP faktiskt startar.
  Transaktionen hålls till HTTP-retur. Slutkostnadens tid är **HTTP-slut**, så
  den åldras konservativt senare än den verkliga starten. Nästa start får
  därför även HTTP-tiden utöver profil-/minimiavståndet.
- `media_bridge.py`/`media_seek.py`: samma media-worker, begränsade köer,
  operation kopplad till förberedelse/control/bekräftelse, faktisk snapshot-
  ålder, fortsatt Windows-upptäckt under lokala budgetpauser. Kötömning
  återlämnar seek-slots och unused grants; gammalt explicit arbete spelas
  inte upp senare. Fyra täta seek godtas i kön; i det provade 401-fria flödet
  hinner tre avslutas, det fjärde förfaller efter fem sekunder.
- `engine.py`: en billig aktivitetssignal efter befintligt datalås, endast
  för verklig godkänd utskrivbar tangent/space. Den väntar inte på fil/HTTP.
- `config.py`/`default_config.json`: nya validerade JSON-fält, bevarade äldre
  explicita fält. `diagnostics.py`: fasta tillåtna värden och numerisk status.
- Spec/requirements: tidszonsdata `tzdata==2026.3` inkluderas i kandidaten.
  Windows-inställningslayouten och serial/art2 är bevarade.

## Felvägar, pending och säker bytespunkt

HTTPError och URLError är OSError-underklasser. Fil-låsens acquisition och
unlock har därför egna smala felvägar; callbackens serverfel omklassificeras
inte till history_io. 401 når tokenförnyelse och budgeterad retry. Verklig
429 ger en klassificerad händelse och totalräknare en gång. 500/URLError går
till befintlig media-fallback. Unlockfel skyddar nästa arbete utan att
maskera ett redan känt serverfel.

Om slutlig ledger-save misslyckas efter ett känt 429 finns den numeriska
spärren kvar i delat profilminne. Den måste flushas innan nästa transaktion
kan arbeta. Token-state försöker också spara sin kända Retry-After; ett
token-skrivfel raderar inte minnesspärren eller svarets klassificering.
Riktiga profiler/tokenfiler har inte använts i dessa prov.

En abrupt processförlust efter pending-skrivning, innan resultatet lagrats,
kan lämna ett **oavgjort pending**. Nästa försök återdebiterar kostnaden och
lägger **24 timmar lokal quarantine på alla `/v1`-vägar**, samt försiktigt
historikläge. Det är skilt från serverns **Retry-After** och det vanliga
**10-minutersskyddet för osäker klockkontinuitet**. En förlorad serverrespons
kan ha haft en längre deadline; sådan okänd kontinuitet kan inte garanteras.
Ett vanligt avbrott mitt i HTTP kan alltså ge ett konservativt lokalt dygns-
uppehåll även utan att Spotify begränsat appen.

Lead ska inför senare byte/rollback stoppa trafik vid en säker punkt och
kontrollera under samma profil-lås att inget HTTP-försök är pågående och
`pending` är tomt. Radera inte ledger, grants eller serverdeadline för att
få en snyggare status. Ingen ny shutdownfunktion eller driftåtgärd ingår här.

## Prov och avgränsning av bevis

Full Python-svit: **135 upptäckta, 133 körda PASS, två befintliga SKIP**.
Logg: `build/api-budget-2026-10-14/python-regression-final.log`.
De överhoppade är host-C++-runtime i `test_focus_countdown`:
`test_cpp_state_cache_and_ui_calls` och
`test_cpp_actual_touch_handler_and_media_dispatch` (ofullständig MSVC-
installation/headers). Firmwarekälla är oförändrad mot före-baslinjen;
ingen firmwarebyggnad eller verktygskedjereparation gjordes.

- 18 policyprov: 30 s/24 h, minutexpiry, burst/rearm/timtak, reserv,
  klocka/restart/sleep/DST, schema/config/reset, corrupt/I/O och parallellitet.
- 22 integrationsprov med **riktig FileBudgetStore**, isolerade profiler
  och mocked HTTP: faktisk OAuth/401-refresh/tokenbyte/retrykostnad;
  verklig QUOTA/kort 429-kropp/Retry/event/total/backoff och nästa klient;
  slutcommit + token-skrivfel efter 429; unlockfel; 500/URLError-fallback;
  diskfördröjning/startspacing, faktisk short/long-cap, grant/seek-expiry,
  source/queue/replay och fortsatt Windows-upptäckt under lokal väntan.
- Tre budget-konfigprov, övriga regressionsprov för controls/seek, serial
  resume/resync/art2, diagnostik, config och båda companion-livscyklerna.
- Äldre transport-/backoff-komponentprov använder en deklarerad budgetstub;
  de provar transportregression. Hårda budgetar bevisas av riktiga policy-/
  FileStore-prov och simulatorn, inte av denna stub.
- Compileall PASS; befintlig Settings-diagnostik PASS och **538 isolerade
  native UI-kontroller PASS**. Ingen riktig profil, motor, COM-port eller
  Spotify-anslutning användes av UI-provet.

Ingen verklig 429 framkallades. Verklig drift, fysisk seek, skärm-/omslags-
latens, lång budgetdrift och Windows sleep/resume med denna nya kandidat
återstår. Användarens väntestatus/UI-observation gäller installerat F406/68CC,
inte API-budget- eller seek-kandidaten. Inga nya förhandsbilder behövs eftersom
geometri/resurser är bevarade. Publicerade releaser och äldre frysta artifacts
ska fortfarande verifieras byte/hash-identiska vid handoff.

## Slutliga simuleringar
Fil: `build/api-budget-2026-10-14/simulation-final.json`. **Virtuell UTC/monoton tid och mocked HTTP**, inte driftbevis. Alla 21 jämförelser använder verklig SpotifyApiBridge: före-baslinjens kod, slutlig 5 s-källa och samma källa med enbart daggolvet 10 s. Långtrace är 72 timmar, incidentnatten 6067 sekunder. HTTP tar 120 ms; ledger är MemoryBudgetStore för långa trace, med separat verklig fil-/fsync-verifiering ovan. Mobilbyten är deterministiska (seed 421, 151–229 s mellan byten); de utlöser ingen lokal aktivitet. Typing-tracet ger en faktisk numerisk tangentaktivitet per sekund. Ingen verklig Spotify, token eller personlig media användes.
Blandat dygn är 4 h Connect-spelande, 4 h idle och 16 h Windows-källa. Det ger gamla kodens cirka 29 762/24 h och är ett **antaget jämförelsescenario**, inte rekonstruktion av hela incidentdygnet. Incidentnatten har 555 s idle följt av spelande och 27 byten; verkliga incidentens 10 297 anrop är loggdata, simulatorns 11 032 är ett annat syntetiskt trace.
| Trace | Äldre HTTP | 5 s HTTP | 10 s HTTP | Max faktisk 24 h, 5/10 s | Tryck ≥50 %, timmar 5/10 s |
| --- | ---: | ---: | ---: | --- | --- |
| incident_night | 11032 | 192 | 192 | 192/192 | 0.0/0.0 |
| incident_like_daily | 89285 | 5661 | 3576 | 1888/1193 | 0.0/0.0 |
| long_mobile | 518400 | 18997 | 14532 | 7124/5639 | 59.7223/56.2017 |
| long_typing | 518400 | 19210 | 14890 | 7125/6069 | 61.046/59.2813 |
| paused | 17280 | 11257 | 11257 | 4059/4059 | 32.1769/32.1769 |
| idle_resume | 474842 | 18900 | 14283 | 7124/5514 | 59.1978/55.1628 |
| warm_start | 518400 | 15410 | 12444 | 6781/5129 | 47.3058/45.5741 |

Alla 14 budget-trace: minsta faktiskt HTTP-startavstånd ≥0,5 s, ≤24 starter/rullande 30 s och ≤7200/rullande 24 h (här finns bara automatläsningar). **0 timmar full-budgetstopp** i samtliga. Riktig totalbudget med explicit trafik provas separat i FileStore-integrationen. Tail-utglesningen infördes eftersom den första 5 s-modellen utan den gav cirka 109 min lokalt budgetstopp i kontinuerlig belastning; den gamla siffran ska inte tillskrivas slutkandidaten. Hårda gränser och serverns Retry-After kvarstår.

### Upptäcktstid per profil inklusive HTTP
Mått: tiden från schemalagt mobilbyte till retur av första läsningen vars **HTTP-start är efter bytet**. Det inkluderar 120 ms HTTP men inte bildhämtning/art2/skärmens rendering. Median/p95/max nedan är sekunder. Kompletta råmått, superseded/pending och källhashar finns i JSON-filen.
| Trace/profil | 5 s median/p95/max | 10 s median/p95/max |
| --- | --- | --- |
| incident_like_daily/day_playing | 2.422/5.036/5.234 | 5.324/9.694/10.060 |
| incident_like_daily/night_playing | 16.102/28.082/29.902 | 16.102/28.082/29.902 |
| long_mobile/day_playing | 5.192/14.815/20.058 | 6.990/14.138/15.200 |
| long_mobile/night_playing | 27.244/84.396/89.966 | 20.053/42.490/45.020 |

Båda dagsvalen såg 225/225 aktuella byten i blandat trace och 1368/1368 i kontinuerligt mobiltrace. Incidentnatten såg 27/27: 17,785/29,985/46,320 s, där max inkluderar initial idle-till-spelande. Idle-resume-bytet tog 28,120 s i båda slutprofilerna, mot 13,120 s i baslinjen; natt-idlegolvet är 60 s, så den enstaka fasen är ingen generell maxgaranti.
Vid kontinuerlig mobiluppspelning blev största gap mellan spelande läsningar **90,12 s med 5 s** och **45,12 s med 10 s**. Detta är tydlig UX-kostnad under tryck. Valda 5 s är ett friskt daggolv, inte ett löfte om upptäckt inom fem sekunder under all belastning. Lead valde 5 s efter jämförelsen eftersom det blandade scenariot fick snabbare dagsupptäckt med stor kvarvarande budgetmarginal. Andra appar och okänd äldre trafik i samma developer-konto förblir osynliga: mindre lokal kostnad bevisar inte frånvaro av framtida 429.

## Fryst kandidat och handoff
- EXE: `D:\DEV\Ai\Github\Bongo-Cat-Screen\dist\companion-2026-10-14-api-budget-dev\BongoDeskSpotify.exe`. **19654754 byte**.
- SHA-256: `B8C7BB2859F86737686899C86C2FA48CDE3702BD5CCBF28A86B13D45C7CC417E`.
- Byggd med PyInstaller 6.22.3; logg `build/api-budget-2026-10-14/pyinstaller.log`. Arkivgranskning: 11 kompilerade moduler matchar källan (normaliserade filnamn, full kodobjektsjämförelse), fyra resurser byteidentiska, tzdata/Europe/Stockholm samt paketmoduler inkluderade; vinter/sommar +3600/+7200 s.
- Paketkontroll: `build/api-budget-2026-10-14/package-verification.json`; reproducerbar kontroll `tools/verify_api_budget_candidate.py` startar aldrig EXE:n.
- Källmanifest: `build/api-budget-2026-10-14/source-frozen.json`; separata frysta källkopior under `source-frozen/`. Kandidat/filhashar: `build/api-budget-2026-10-14/candidate.json`; tests/sim/paketmanifest länkas där.
- 91 äldre artifacts byte/SHA-identiska; alla firmwarefiler, releasefiler, tidigare seek-manifests/rapporter och UI-geometri bevarade. 58 före-baslinjefiler jämförda; ändringarna ligger enbart i de redovisade companion-/testfilerna. Nya policy-/test-/verktygs-/rapportfiler är separata.
- EXE:n har inte startats eller installerats. Ingen riktig profil/token, autostartpost, companionprocess, firmware, flash eller release har ändrats. F406:s befintliga media/serial/art2 bevaras; fysisk seek kräver den separat frysta seek-firmwaren och är uppskjuten.

### Ändrade filer i detta steg
- Befintliga: `companion/BongoDeskSpotify.spec`, `README.md`, `config.py`, `default_config.json`, `diagnostics.py`, `engine.py`, `media_bridge.py`, `media_seek.py`, `requirements_app.txt`, `spotify_api.py`; `tests/test_adaptive_connect.py`, `test_media_seek.py`, `test_spotify_cooldown.py`.
- Nya: `companion/api_budget.py`; `tests/test_api_budget.py`, `test_api_budget_config.py`, `test_api_budget_integration.py`, `transport_budget.py`; `tools/simulate_api_budget.py`, `verify_api_budget_candidate.py`; denna rapport. Prefixen gäller alla namn inom samma listgrupp.

### Senare driftprov, utförs av Lead efter separat beslut
1. Läs/verifiera EXE- och källhashar samt bevara installerat F406/68CC, config, token-state, ledger och rollback. Kända Retry-After ska respekteras; starta inte extra playbackklient eller framtvinga 429. Stoppa/byt endast utan in-flight HTTP/pending enligt säker punkt ovan.
2. Kontrollera båda normala companion-vägarna, UI/tray-Exit, aktuell tid/statistik, meny/gester/DJ och omslag med samma låt efter resync. Stoppursmät mobilbyten/omslag separat från 120 ms-simuleringen; ange warm/kvot/tryck/profil vid varje mätning.
3. Låt normal användning passera dag/natt och initialt historikdygn. Läs fasta räknare/snapshotålder, kontrollera lokal Windows-prioritet, ingen lång köreplay och inga extra workertrådar. Gör vanligt Windows sleep/resume och bekräfta serialåteranslutning/återsynkning. Framkalla inga Spotifybegränsningar.
4. Seek-skärmprovet väntar separat på användarens beslut; denna companionbuild gör ingen flashning eller fysisk acceptans av den funktionen.

Slutlig whitespace-kontroll: **git diff --check PASS**, även separat
kontroll av de åtta nya käll-/test-/verktygs-/rapportfilerna PASS.

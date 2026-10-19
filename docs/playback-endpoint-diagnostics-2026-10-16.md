# Tidsbegränsad endpointdiagnos A–B–A – 2026-10-16

## Status och bakgrund

Kandidaten är **byggd och verifierad i isolering, inte installerad eller
driftprovad**. Den samlar innehållsfria jämförelseuppgifter; den är ingen
automatisk fallback eller utlovad rättning. Installerat par är fortfarande
companion **4D4A84E8 / firmware 55669C87**. Ingen firmwareändring behövs.

Den bekräftade incidenten 12:03 hade fortsatt musik på mobilen men tomma
primärsvar och Waiting på skärmen. Senare foreground på iPhone 13 Pro
sammanföll med återkomst utan omstart. Det korta låstprovet 12:10:11–12:12:28
gav fortsatt 200/track. WiFi, Strömsparläge av och AppStore ”Öppna” är
användaruppgifter enligt Lead; någon telefon-/batteriorsak är inte bevisad.

En senare loggad 200→204-övergång 12:29:22 var **inte** en bekräftad ny
Waiting-incident: användaren sade att skärmen fortfarande visade låten.
Telefonens foregroundläge var osäkert. Återkomst till 200 vid senare
observation kan därför inte beskrivas som bevisat spontan återhämtning.
Den frysta [driftrapporten BAD061](seek-removal-runtime-2026-10-16.md) och
[borttagningsrapporten 4CDC](seek-removal-2026-10-16.md) är bevarade.

Lead har endast läst booleskt scope-medlemskap: playback-state,
currently-playing och modify-playback-state finns. Code har inte läst
verkliga tokens eller gjort återinloggning, scopemigrering eller API-prov.

## Den avgränsade sekvensen

| Steg | Befintligt lästillfälle | Effekt |
| --- | --- | --- |
| A | Ordinarie `/me/player` ger tomt resultat | Vanlig Waiting/idle-policy, en diagnostikmöjlighet armeras. |
| B | Nästa redan förfallna automatiska A ersätts av `/me/player/currently-playing` | Endast status/shape/item/type loggas. Inga B-metadata publiceras. |
| A | Nästa ordinarie läsning | Primärvägen fortsätter; ingen ny B-sekvens armeras. |

Ingen omedelbar följd-GET, separat klient, timertråd, urgentflagga eller
explicitgrant läggs till. Samma klient/worker, automatiska request_kind,
budgetdebitering, next_due och 5/30 s-profiler används. **B200 ändrar inte
`_last_is_playing`, idle/active, låt-/omslagscache eller ordinarie
snapshotålder. Skärmen kan därför fortfarande visa Waiting efter B200.**

Möjligheten förbrukas vid första armeringen i appsessionen, även om den
avbryts före HTTP. Den har **90 s monotonic TTL** och kan inte skjutas
över source-/Windows-växling. Giltigt A före B avbryter den, även om A
kommer från en äldre bakgrundstråd för Windows-omslag. En innehållsfri
A-revision uppdateras under det befintliga klientlåset för detta skydd.

Manuell refresh, kontrollbekräftelser och Windows-omslagsfallback använder
fortsatt A och armerar inte B. Slutvillkoret kontrolleras igen efter OAuth
och durable I/O. Mellanliggande manuellt arbete bevaras om B då nekas.

En logisk B tillåter högst två HTTP-starter endast för den befintliga
401-retryn; automatisk pacing/budget och TTL gäller även vid workeråterinträde.
403, transport-/parsefel eller 429 avslutar B via befintlig felpolicy,
inklusive ordinarie 60 s API-felväntan eller Retry. Den felvägen kan
nollställa ordinarie snapshotstatus/ålder. Ingen andra B skapas efter felet.
Misslyckad durable claim behåller den befintliga konservativa pendingkostnaden.

Loggfältet `endpoint` tillåter endast `playback_state`/`currently_playing`.
Inga titlar, ID:n, URL:er, headers, tokens, kroppar eller råa felmeddelanden
tillförs. B-fel saneras före befintlig felvisning. Inget tekniskt
diagnostikval läggs i normalt UI.

## Kod och verifiering

Endast `companion/diagnostics.py`, `media_bridge.py`, `spotify_api.py`
och nya `tests/test_playback_endpoint_diagnostics.py` ändras, utöver denna
rapport. Övriga filer i basens 154 källor, breda kontext-/statusfiler och firmware
bevaras. Scope-/AST-bevis visar oförändrad budgetmodul och oförändrade
delade request-/retryguards efter borttagning av de nya loggfälten och
revisionsräknaren för jämförelsen. Normala kontroll- och pollningshjälpmetoder är oförändrade.

- **16 nya riktade prov PASS.** A200 utan B; A204→B200→A204 ger exakt tre
  tillfällen/tre HTTP, waiting/30 s och noll nya grants; Btomt, 403 vid
  idle15, transport-/parsefel, 401/429, noll HTTP vid start-/profil-/spacing-/
  Retry-/clock-/I/O-spärr, TTL/sourcecancel och primär A-revision täcks.
- Bdata ändrar inte publiceringsantal, cache, flaggor eller snapshotålder.
  Manuell/confirmation/windowsartwork stannar A. Slutguarden bevarar
  manuell begäran som anländer under tokenförberedelse. Fast privacyenum provas.
- **En full regression: 198 upptäckta, 196 PASS, 2 kända C++ SKIP**,
  21,800 s, noll fel och noll externa nätförsök. Separata testprofiler och
  ny native-utdatamapp användes. Ingen blind serie fulla omkörningar gjordes.
- Den tidigare olösta testvariabiliteten från 4D-bygget kvarstår som
  begränsning. Denna lyckade körning är inte bevis på att dess orsak är löst.
- PyInstaller, 48 Pythonkällor i minnet, elva paketmoduler, fyra resurser
  och Stockholm-tzdata: PASS. `media_seek` är inte packad.
- **155 aktuella + 155 frysta källor**, **1 811 äldre artefakter/rapporter**
  och äldre 6A2B-snapshot matchar byte/hash. Lead har oberoende verifierat
  paket och bevarande. `git diff --check` och textkontroller: PASS.

## Fryst kandidat och bevis

- EXE: `dist/companion-2026-10-16-playback-endpoint-diagnostics-dev/BongoDeskSpotify.exe`.
- **19 656 263 byte**, SHA-256
  `3EDD2187F4DB3F550FF6C2D0342ED6E4BB38EB97BEE5EF6122B7988C738A0A4A`.
- Underlag: `build/playback-endpoint-diagnostics-2026-10-16/`.
- `source-frozen.json`:
  `E05E043A07CAA06C0F733F7558C298F3266FDE7D9E90198C83545B38B5314E0D`.
- `package-verification.json`:
  `04377F47B206C20118CD3FB8C6D5ECE4078B6168907D77242F980AE8CC408D68`.
- `candidate.json`:
  `F4527857397B490EC78E66F372C3A7934BD3D540F2C9657B769F458E189E4A34`.
- `scope-verification.json`:
  `3C5D075CBE5FACF76DE668664E8E9B98947B3C68628E357C11A8B30E579ED32E`.

## Väntande driftbedömning

Lead hanterar versionsgodkännande, eventuell installation och separat
runtimejournal. Ingen installation/start, verklig profil-/API-åtgärd,
flashning, commit, push eller release gjordes av Code.

Vid framtida driftprov jämförs endpoint-enum, HTTP/shape och lifecycle.
A204/B200/A204 kan stödja olika svarsvyer men jämförelsen är tidsförskjuten
och bevisar inte orsaken. Btomt/403 bevisar ingen batteri-/backendorsak.
Faktisk endpointsekvens, stabilitet och eventuell uppspelningsrättning
är fortfarande oprövade. [Spotifys primärreferens](https://developer.spotify.com/documentation/web-api/reference/get-information-about-the-users-current-playback)
och [alternativreferens](https://developer.spotify.com/documentation/web-api/reference/get-the-users-currently-playing-track)
beskriver endpoints/scopes; de garanterar inte beteendet i denna incident.

# Manuell API-status från Spelarens vänteläge – 2026-10-15

## Status

**1370651D är byggd, paketverifierad och källfryst för Projektledarens
granskning och säkra driftbyte. Fysiskt väntetryck är ännu inte accepterat.**
Kodskrivaren har inte startat/installerat EXE:n eller ändrat riktig profil,
ledger, token, process, Run-post, firmware eller release. Alla nätprov är
mockade med isolerade filer under `D:\DEV\Ai\Github\Bongo-Cat-Screen`.

Den fungerande **CB313174/F406**-installationens kontrollomprov är
kvalitativt godkänt av användaren. Det är separat från denna nya funktion;
se [driftrapporten](api-budget-runtime-2026-10-15.md). CB-EXE, 68 frysta
källkopior/manifests och den [tidigare fixrapporten](api-control-fix-2026-10-15.md)
är bevarade som rollback/historik. B8-artefakterna är också orörda.

Denna rapport och driftrapporten ligger **utanför det nya 71-filersmanifestet**.
De kan kompletteras med senare fakta utan att ändra fryst kod eller kandidat.

## F406 kan redan signalera väntetrycket

Kontrollen gjordes före implementation i
`build/media-seek-2026-10-12/baseline/src/bongo_cat_featured.inc`.
Dess SHA-256 är
`29CA89C1DC07BC40DA5858BCBD7D2CF2D5D9166AC575EF95279EAE6F4F40DC58`,
exakt F406-kandidatmanifestets källhash.

`handleTouchFeature()` skickar Spelarens vanliga korttryck till
`queueMediaTap()` även utan låt. `serviceMediaTaps()` grupperar i **320 ms**
och sänder `MEDIA_CMD:PLAY_PAUSE` för enkeltryck, NEXT/PREVIOUS för dubbel/
trippeltryck. Det finns ingen `media_has_track`-spärr runt utskicket.
Menyn och Fokus-touch fångas separat. `MEDIA_STATE:NONE` tar bort omslaget
men titel-/artistraderna fortsätter visa befintliga metadatafält.

Funktionen är därför **companion-only**: ingen ny firmware, hitbox,
touchgest, serialkommando eller flashning behövs.

## Beteende och gränser

- När Windows-källan försvunnit och ingen giltig API-låt har lästs i den
  aktuella källperioden visar Spelaren **Waiting for Spotify** /
  **Tap to check status** när reserv är möjlig. Snapshoten är fortsatt
  `available=false`, `playing=false`, utan påhittad musikväxling.
- Ett PLAY_PAUSE i detta vänteläge begär **en GET**. Det skickar ingen
  PUT/POST och pausar, spelar eller byter inte låt. En tom API-snapshot
  är fortfarande vänteläge och kan läsas igen på samma sätt.
- Vid giltig aktuell API-låt behålls vanliga musiktryck. Det gäller även
  play av en giltig pausad snapshot. Windows-kontroller, Bongo/Fokus,
  DJ, meny och seek utanför vänteläget behåller sina roller.
- Läsningen har en enda koalescerad slot, **3 s TTL före HTTP-start**, och
  **5 s lokal anti-spam** för nya läsningar. Dubbletter och andra
  musikgestvarianter under pending läsning samlas utan extra arbete.
  NEXT/PREVIOUS/seek i väntan utan läsning ignoreras. Efter avslut/avbrott
  skyddar en **0,5 s gestsvans** mot sena 320 ms-grupper från samma tryckserie.
  Därefter gäller vanlig control för en giltig låt; ingen femsekundersspärr
  läggs på vanliga musiktryck.
- Inget väntetryck anropar aktivitetshooken eller armerar snabbpollning.
  Efter läsningen väntar automatiken minst sitt ordinarie profilintervall
  från den nya snapshoten. Ingen extra bekräftelse-GET behövs: läsningen
  är själv den auktoritativa snapshoten.

**Checking status...** används efter reservering när startgränsen tillåter.
Hårda Retry-vyn **Spotify API paused / Retry &lt;tid&gt;** bevaras. Vid känd
clock/I/O-/budgetspärr visas inget missvisande busy-/tap-löfte. Befintlig
artistlabel får i stället **Waiting for next check**. Käll-/captionändringar
publiceras genom den befintliga ändringskontrollen, inte som extra seriell
pollning. UI-granskningen var skrivskyddad: de tre texterna ryms inom
befintlig 204 px-yta; ingen layout eller Windows-inställningsvy ändrades.

## Säkerhet i käll-, budget- och felvägar

Källperioden räknas med en **epoch** vid Windows/API/generic-byte. Gamla
API-snapshots och gamla Windows-bilder kan inte göra ett nytt väntetryck
till play/pause. Normala köade API-kontroller får periodskydd; seek behåller
källa/låt/context/TTL. Första upptäckta Windows-ägaren får fortfarande ett
native NEXT som köats före första workerpasset; verkliga senare ägarbyten
invaliderar gammalt arbete.

Manuell läsning kontrollerar TTL/epoch och återkommen Windows-källa efter
OAuth/fsync, precis före HTTP-start, samt källa igen efter svaret. En
giltig pausad snapshot i samma aktuella API-period blir vanlig play,
medan en gammal API-cache från före Windows blir väntetryck.

Det befintliga **control-grantet** återanvänds konservativt: tre kostnader
reserveras, en GET används, eller två vid verklig 401-retry; oanvänd reserv
återlämnas. En räknare på den manuella sloten och en retry-guard begränsar
hela operationen över worker-återinträden till **högst två GET och en
401-tokenförnyelse**. Pacing mellan försöken kan inte återställa denna gräns.
Ingen fri `urgent=True`-genväg eller nytt ledgerformat infördes.

**`api_budget.py` är byteidentisk med den verifierade CB/B8-policyn.**
Hard total, 0,5 s-spacing/högre inlärt minimum, grants, clockguard,
I/O/corrupt, verklig Retry-After och warm/QUOTA vinner alltid. Endast lokal
automatprofil, exempelvis 60 s-golvet, kan preempteras av legitim reserv.
Ingen riktig spärr, profil eller ledger har raderats för provet.

Pacing-väntan för manuell slot använder faktisk bounded `await sleep`, så
Windows-upptäckt och TTL får framsteg. Hårda avslagsorsaker släpper slot.
Strikt GET-parsning behålls; JSON-/UTF-/shape-fel och OSError efter read
släpper slot/grant och återgår till normal automatväntan utan replay.

Den nya NONE-vyn rensar motorns gamla omslag. Vid återinträde i Windows
återställs därför just track-/cover-complete-vakterna så **samma låt** får
sin thumbnail igen utan extra `/v1`. Gamla asynkrona API-/fallbackbilder
får inte färdigmarkera eller publicera i en ny källperiod.

## Verifiering

Ny fil `tests/test_manual_api_refresh.py`: **17 prov PASS**, varav **15
hela-worker-/FileStore-prov** och två riktade omslagsprov med verklig
`_read_session`/motorns bildcache respektive asynkron epoch-kontroll.

Proven täcker första Windows → API-väntan med föregående fallbackkostnad,
en snabb GET utan musikkommando, redan tom aktuell snapshot, gammal API-
cache och upprepad övergång, giltig pausad play, pending-burst/gestsvans,
TTL under tokenförberedelse, källa tillbaka före start/efter svar,
Retry/clock/short/long-cap/I/O, faktisk minspacing med yield/Windows-
takeover, riktig mockad 401 samt ihållande 401 med max två försök.
Malformed JSON/UTF/shape och post-read metadata-OSError ger en enda
manuell läsning, ingen återanvändning av granten för extra GET.
Samma Windows-thumbnail återställs i riktig engine-cache utan API-anrop.

Full regression: **162 upptäckta, 160 körda PASS, två befintliga C++ SKIP**:
`test_cpp_state_cache_and_ui_calls` och
`test_cpp_actual_touch_handler_and_media_dispatch` i `test_focus_countdown`
(ofullständig lokal MSVC/headers). Compileall och `git diff --check` PASS.
Logg: `build/manual-api-refresh-2026-10-15/python-regression.log`.

Tre äldre testfixturer anger nu sin riktiga förutsättning: redan giltig
API-period respektive stopp först på auktoritativ Windows-snapshot,
med tidigare dispatch-/seek-/budgetassertions kvar. Native-NEXT före
första Windows-pass bevarades genom produktionsfix, inte ändrat testkrav.
Ett äldre fsync-spacingprov fick tillfälligt `admission did not settle`;
numerisk feldiagnostik lades till utan ändrade assertions eller policy.
Den isolerade 22-testkörningen och slutliga hela sviten passerar; orsaken
till den tidigare testfluktuationen är inte fastställd.

### Full worker, virtuell tid och 120 ms mocked HTTP

| Scenario | Första GET efter väntetext | Manuella GET-försök | Nästa normala auto | Kostnad totalt/auto/reserv |
| --- | --- | ---: | --- | --- |
| Utan tryck | 59,40 s | 0 | Normal profil | 3/3/0 |
| Ett väntetryck | 0,05 s | 1 | 60,42 s efter manuell snapshot | 3/2/0 |
| Ihållande 401 | 0,05 s | 2, en OAuth-refresh | Vanlig väntan efter avslutande fel | 4/2/0 |

I samtliga är aktivitetssignal **0** och snabbperiod **false**. Tabellen
inkluderar en verkligt mockad initial fallbackkostnad. Tiden 0,05 s börjar
vid väntetext i fejkad worker, inte fysisk touch; F406:s 320 ms-gruppering,
seriell transport, skärmrendering och CDN/art2 ingår inte som mätt fysisk
latens. Råmått: `build/manual-api-refresh-2026-10-15/worker-metrics.json`.
Ingen ny bred 72 h-simulering gjordes eftersom policy-/clockmodulen är
byteoförändrad. Äldre simuleringar och deras artifacts bevaras.

## Fryst kandidat och bevarande

- EXE: `D:\DEV\Ai\Github\Bongo-Cat-Screen\dist\companion-2026-10-15-manual-api-refresh-dev\BongoDeskSpotify.exe`
- Storlek: **19655597 byte**.
- SHA-256: `1370651DF6FCC28D70FE4736B39818AA71F8BCEE13EF0992C90EC92EA97F7762`.
- Källmanifest: `build/manual-api-refresh-2026-10-15/source-frozen.json`,
  **71 filer**, separata kopior under `source-frozen/`.
  SHA: `1D1F5B6069574F29FC7DDD6B307A99480C571DB8CCD9415C658DE5DFE3ADCD60`.
- Kandidatmanifest: `build/manual-api-refresh-2026-10-15/candidate.json`,
  SHA: `A289767D3AC1C4E1B21F530756F7A5A1A10D482C9FB3C491EAEA13EDF4F1249D`.
- Paketmanifest: `build/manual-api-refresh-2026-10-15/package-verification.json`,
  SHA: `631C78443BC4408A48535FAEC92531EC24973F0837AE737ED8ED09FA98DF464C`.
- Worker-mått SHA: `7AB2911925FE79A89E9DAC4018F12A5BC38781F162B9F0552BCEB49548F0CF06`.

Paketkontrollen bekräftar elva kompilerade moduler, fyra byteidentiska
resurser och Stockholm-tzdata. Projektledaren har även själv granskat
paketet skrivskyddat. Före-baslinjen har **70 filer** och **419 skyddade
tidigare artifacts**. De senare är oförändrade i storlek/SHA, inklusive
CB/B8-EXE:er, frysta källor/manifests, tidigare rapporter och firmware.

Ändrade produktionsfiler: `companion/media_bridge.py`, `media_seek.py`,
`spotify_api.py`. Äldre testfixturer: `tests/test_api_budget_integration.py`,
`test_media_seek.py`, `test_spotify_cooldown.py`. Nya filer: denna rapport,
`tests/test_manual_api_refresh.py` och `tools/verify_manual_api_refresh_candidate.py`.
Separata driftrapporten har kompletterats. Ingen settingslayout, källa
under `src/`, config, policy, serial/art2, release eller Git-commit ändrades.

## Senare fysiskt prov hos Projektledaren

1. Byt säkert under gemensamt ledgerlås utan pending/in-flight HTTP och
   bevara verklig ledger/profil/token/kvot. CB är fungerande rollback.
2. Avsluta Windows-Spotify, spela från mobilen och kontrollera väntetexten.
   Ett kort tryck ska ge en aktuell status/omslag utan att ändra musiken.
   Bekräfta även tom snapshot och flera snabba tryck utan oavsiktligt NEXT/play.
3. Kontrollera vanlig paus → play efter giltig API-snapshot, samt återkomst
   till samma Windows-låt med rätt omslag. Prova sedan vanlig meny/DJ/seek
   enligt installerad firmware; separat seek-firmware är fortsatt uppskjuten.
4. Läs händelser/räknare: högst en GET plus verklig 401-retry, ingen fortsatt
   snabbpollning. Kända Retry-spärrar ska visas och respekteras; framkalla
   inte nya 429 eller extra API-prober för att testa dem.

Installation och fysisk acceptans av denna nya funktion redovisas först
när Projektledaren lämnat verifierat utfall i separata driftrapporten.

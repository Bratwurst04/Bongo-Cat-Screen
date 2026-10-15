# Explicit API-control – separat korrigeringskandidat 2026-10-15

## Status och avgränsning

**CB313174 är byggd, paketverifierad och källfryst. Klartecken för
Projektledarens säkra byte och verkliga knappomprov är lämnat.**
Kodskrivaren har inte startat eller installerat EXE:n, ändrat riktig profil/
ledger/token/process/Run-post, anropat Spotify eller byggt/flashat firmware.
Alla nedanstående nätprov använder isolerade filer under projektet,
fejkad HTTP och virtuell tid.

Rapporten och den löpande [driftrapporten](api-budget-runtime-2026-10-15.md)
ligger **utanför den nya källfrysningen**, så dokumentationen kan färdigställas
utan att försena omprovet eller ändra frysta källhashar. Den tidigare
[B8-utvecklingsrapporten](api-budget-2026-10-14.md), B8-EXE:n, dess 66 frysta
källkopior och manifests är bevarade.

## Verklig regression – orsak ännu inte fångad

På installerad **B8C7BB28/F406** rapporterade användaren att NÄSTA och paus
nådde Spotify men att play inte fungerade som väntat, och att skärmen
uppdaterades först efter uppskattningsvis **1 min 20 s**. Projektledarens
logg visar tre `MEDIA_CONTROL skipped/api_error` efter ett NÄSTA och två
PLAY_PAUSE. Nästa automatiska `MEDIA_TRACK` kom cirka **84,6 s efter
NEXT-mottagningen**. Sju budgetkostnader, varav fyra auto/tre explicita,
inga kvarvarande reservationer, ingen aktiv Retry/clockguard och ingen ny
429 observerades. Exakta tider finns i driftrapporten.

Scopes och framtida tokenutgång var verifierade av Projektledaren; vanliga
GET/omslag fortsatte fungera. **Det verkliga controlfelets exceptionklass,
HTTP-status och responsform saknas i den äldre diagnostiken.** Därför
påstås inte att den lokala reproduktionen nedan är den fångade serverorsaken.

## Bevisad lokal felväg

En fryst B8-API-klient kördes med riktig `FileBudgetStore` och hela
`WindowsMediaBridge._run()` under importerad 60 s-kvotåterhämtning och
okänd historik. Ett control verkställs i den fejkade servern och får ett
lyckat **200/202-svar med icke-JSON-innehåll**. B8 anropar därefter
`json.loads()` på svaret och kastar `JSONDecodeError`.

Media-workern behandlar då det redan verkställda kommandot som ett fel,
släpper dess grant och inväntar nästa automatiska snapshot. Det ger
**61,37 s från köläggning till uppdaterad snapshot** i detta trace.
Play-state-flippen efter lyckad PUT nås inte heller vid parserfelet; två
snabba toggles kan därför välja samma endpoint från gammal cache.

En syntetisk 204 med icke-tom body demonstrerar samma parserkod. Den ska
inte beskrivas som en fångad verklig 204-respons: stdlib kan behandla 204
som längd noll. Helt tomt svar fungerade även i baslinjeprovet.

## Avgränsad ändring

- `companion/spotify_api.py`: lyckade control/seek-anrop med `empty_ok`
  kräver ingen JSON och läser inte en body som inte behövs. HTTP-fel
  hanteras fortfarande av befintliga error-/429-/401-vägar. GET-metadata
  behåller strikt JSON-tolkning. Senaste control-HTTP-status sparas endast
  som ett numeriskt värde för diagnostik och nollställs inför nytt anrop.
- Ett OSError när ren-driftsmetadata sparas i `_record_success()` kan
  inte upphäva ett redan accepterat control. Numeriskt fel loggas och
  bekräftelsen får fortsätta med sitt befintliga grant. Själva
  `_record_success`-metoden och dess intervallvillkor är oförändrade.
- `companion/media_bridge.py`: `MEDIA_CONTROL api_error` får felklass och
  HTTP-status, även för seek. Inga exceptiontexter, responsebodies, URL:er,
  tokens eller låtmetadata läggs till. Control-/bekräftelseflödet och
  köernas befintliga gränser behålls.
- `companion/diagnostics.py`: numeriskt `http_status` och tillåtna
  klassnamn `JSONDecodeError`/`UnicodeDecodeError` stöds.

**`api_budget.py` är byteidentisk med B8.** Budgettak, grants, clockguard,
pending/Retry, warm/QUOTA, burst och profilegenskaper har inte ändrats.
Inga tätare automatpolls eller extra kompenserande API-prober införs.
Input-/serialvägen, F406, art2, touch, Fokus, UI-layout och seek-skydd
är oförändrade i detta steg.

## Prov och resultat

Ny testfil: `tests/test_api_control_confirmation.py`, **10 prov PASS**.
Hela verkliga media-workerloopen används; kontrollen går inte endast via
en helper som pumpar kommandon och manuellt anropar confirm.

- NEXT → confirm → PAUSE → confirm → PLAY → confirm under 60 s-recovery,
  `history_complete=false`, vid både **0,5 och 1 s** grundgräns.
- 200/202/204, tomt/whitespace/non-JSON/ogiltigt UTF-8/JSON-innehåll och
  Content-Length/Content-Type-varianter; lyckad bodylös ack blir inte JSON.
- Seek → färsk förberedelse → PUT → reserverad bekräftelse med samma
  guard, fungerande position, släppta slots och oförändrade kostnader.
- Riktig mockad 401 → OAuth-tokenförnyelse → budgeterad retry → confirm;
  inga riktiga token- eller nätanrop.
- 403, 500 och URLError förblir fel, ingen control-replay, ingen ny 429
  påhittas; felklass/status registreras utan innehåll.
- 429 bevarar Retry-After och tömmer explicit arbete. GET med ogiltig
  JSON fortsätter kasta parserfel. Loggprov bevisar att råfält filtreras.
- OSError vid success-metadata och fel vid budgetens slutcommit skiljs
  åt. Verkligt ledger-commitfel förblir **fail closed**, behåller kostnaden
  och spelar inte om kommandot. Vid sådant lagringsfel garanteras ingen
  snabb bekräftelse; detta fel var inte ett `api_error` i reproprovet.

### Tidsmått, full worker och 120 ms fejkad HTTP

| Klient/gate | Kö → snapshot | Control-ACK → confirm-retur | HTTP / auto / kvarvarande reserv |
| --- | --- | --- | --- |
| Fryst B8, 1 s, 200/non-JSON NEXT | 61,37 s | 60,42 s | 3 / 2 / 0 |
| Korrigerad, 0,5 s, NEXT/PAUSE/PLAY | 1,49 s per kommando | 0,92 s per kommando | 7 / 1 / 0 totalt |
| Korrigerad, 1 s, NEXT/PAUSE/PLAY | 1,95 s per kommando | 1,00 s per kommando | 7 / 1 / 0 totalt |

Måtten inkluderar fejkad HTTP och workerflöde, inte fysisk touch-/serialtid,
CDN/art2 eller skärmens bildvisning. De är **lokala prov, inte driftacceptans**.
Råmått: `build/api-control-fix-2026-10-15/worker-metrics.json`.

Full regression: **145 upptäckta, 143 körda PASS, två befintliga C++ SKIP**
i `test_focus_countdown`: `test_cpp_state_cache_and_ui_calls` och
`test_cpp_actual_touch_handler_and_media_dispatch` (ofullständig MSVC/
headers). Logg: `build/api-control-fix-2026-10-15/python-regression.log`.
Compileall och `git diff --check` PASS. Ingen ny bred 72 h-simulering
gjordes: budget-/clockmodulen är byteidentisk, dess verifierade policyprov
ingår i regressionen och äldre simulationsfiler bevaras.

## Ny fryst kandidat

- EXE: `D:\DEV\Ai\Github\Bongo-Cat-Screen\dist\companion-2026-10-15-api-control-fix-dev\BongoDeskSpotify.exe`
- Storlek: **19653708 byte**.
- SHA-256: `CB31317492880698421BB0DEF7EEBCEAABEF7F8D13FA2C82318B2DB810C4A130`.
- Källmanifest: `build/api-control-fix-2026-10-15/source-frozen.json`,
  **68 filer** och separata kopior under `source-frozen/`.
  SHA: `AB5557568EAB5B83C4B4B6546646777336A9A6712E6BBE79DC493E00E7891D18`.
- Kandidatmanifest: `build/api-control-fix-2026-10-15/candidate.json`,
  SHA: `ECC34B11E7C20F08BDCFEA402D3A7D68C0E32E69D43D794409B0DF379E66F943`.
- Paketmanifest: `build/api-control-fix-2026-10-15/package-verification.json`,
  SHA: `3AE39AFAE42AE99DAE18C9A2D31A9438D18056E88C26282AB0FD5ED216F5125A`.
- Worker-måttens SHA: `5EA7247DFB3816545A1FDC46E750EC078E85D3521BE75663823E20088C3B3097`.

Arkivkontrollen `tools/verify_api_control_candidate.py` bekräftar elva
kompilerade moduler mot källan, fyra byteidentiska resurser, Stockholm-
tidszonsdata och **254 tidigare artifacts** med oförändrad storlek/SHA.
Projektledaren har även oberoende granskat elva arkivmoduler och fyra
resurser skrivskyddat utan att starta EXE:n.

Före-baslinjen finns under `build/api-control-fix-2026-10-15/baseline/`:
67 aktuella filer samt skydd för B8-EXE:n, dess frysta källkopior/manifests/
rapporter/byggdata och tidigare 91 artifacts. Den löpande driftrapporten
är avsiktligt separat från nya frysta källmanifestet.

Endast tre produktionsfiler ändrades. Nya test-/verktygsfiler är de två
namngivna ovan; dokumentändringarna är denna rapport och driftrapporten.
Ingen commit, release, firmwarebyggnad eller flashning ingår.

## Verkligt omprov återstår

Projektledaren hanterar säkert byte under profilens gemensamma fil-lås,
utan pending/in-flight HTTP, med bibehållen riktig ledger, config, token
och befintliga kvot-/Retry-spärrar. Efter byte behövs ett NÄSTA och
paus → play med fungerande snabb auktoritativ skärmuppdatering. Om felet
återkommer ger den nya diagnostiken faktisk felklass och HTTP-status.
Ingen ny verklig 429 eller extra playback-prober ska framkallas.

Det friska 5 s-automatgolvet, långdrift/dag-natt, sleep/resume och separat
seek-skärmprov har inte accepterats genom dessa lokala kontrollprov.

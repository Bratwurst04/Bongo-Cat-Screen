# Aktiv mobilföljning under lokal API-återhämtning – 2026-10-15

## Status och beslut

**17466EBF är byggd, paketverifierad och källfryst. Klartecken för
Projektledarens säkra byte är lämnat; fysisk mobilföljning återstår.**
Kodskrivaren har inte startat EXE:n, anropat Spotify eller ändrat riktig
profil, ledger, token, process, Run-post, firmware eller release.

Den manuella vänteläsningen i 137 fungerade: användaren godkände rätt snabb
låt, oförändrad musik och rätt omslag. Däremot kom nästa automatiska läsning
cirka 60,571 s senare och mobilens senare låtbyten låg efter på skärmen.
Status visade lokal 60 s-återhämtning, ingen aktiv Retry/clock-spärr och
fortsatt två historiska 429. Det är en separat policyfråga; se
[driftrapporten](api-budget-runtime-2026-10-15.md).

Efter ett konkret förslag och jämförbara 72 h-trace godkände Projektledaren
att **dag + känd faktisk uppspelning** följer valt **5 s-grundgolv**, även
under lokal warm/strong/soft recovery, före budgettryck och högre backoff.
Ingen kort boost efter väntetryck används som ersättning för fortgående
mobilföljning. Natt **00–08 Europe/Stockholm** och paus/idle förblir glesare.

**5 s är inte ett löfte under tung kontinuerlig användning.** Den nya sena
tailen är sämre i det kontinuerliga stresstracet: högst **120 s daggap** och
**84,720 s p95-upptäckt**, mot tidigare **60,12/29,162 s**. Projektledaren
granskade och accepterade denna avvägning; skydden lättades inte för att
förbättra extrema latensmått.

Rapporten och driftrapporten ligger **utanför de 75 frysta källfilerna**.
137/CB/B8, deras frysta källkopior/manifests/EXE:er och tidigare rapporter
behålls orörda. 137 är den närmast föregående fungerande rollbacken.

## Minsta produktionsändring

- `companion/api_budget.py`: endast de lokala warm-/quota-golven i
  `_profile` begränsas till natt eller idle. Känd spelande musik dagtid
  använder fortsatt det konfigurerade dagvärdet (standard 5 s), med
  oförändrad 1,5×/3×-pressure och tail-utglesning.
- `companion/spotify_api.py`: klientens separata `_quota_poll_floor`
  undantar känd daguppspelning. Poll-delay och intervall förmedlar idle
  uttryckligt, så ett paus-/idleanrop fortfarande får recoverygolvet.
  Högre adaptivt intervall/minimum behålls.

Båda golven måste ändras: att endast ändra budgetmodulen lämnar klientens
separata 60 s-golv kvar. Ingen musikstate gissas från tangentaktivitet:
klienten måste ha läst `is_playing=true`. Före första aktuella uppgift,
vid paus/idle och på natten kan upptäckten fortfarande ta längre tid;
befintligt manuellt väntetryck finns kvar.

### Skydd som är kvar

Riktig **Retry-After är alltid absolut**. Automatiken får högst 18/30 s och
7200/24 h, totaltak 24/30 s och 8000/24 h; warm/strong behåller halverad
24 h-budget (4000 totalt/3600 auto), soft behåller 75 % (6000/5400).
Ingen ledger/token/deadline/historik återställs. Clock/I/O/corrupt,
0,5 s-spacing/högre sparad pacing, explicitreserv och pending gäller som
tidigare. Ingen 0,5 s-burst öppnas under warm/QUOTA och automatiska låtbyten
armerar ingen boost.

Manuell one-shot med högst en verklig 401-retry, anti-spam, source-epoch,
vanlig control, pausad play, Windows-prioritet, omslag, Fokus, touch,
serial/art2 och seek ändrades inte i produktionen i detta steg.

AST-kontroll jämför hela budgetmodulen utom de två avsedda golvblocken och
hela klienten utom quota-floor/poll-delay/poll-intervall: **övrig kodstruktur,
schema, caps, grants, burst, clock och Retry är identiska** med baslinjen.
Detta påstår inte att hela `api_budget.py` är byteidentisk efter policyändringen.

## Jämförbara 72 h-trace

Före implementation kördes en isolerad prototyp. Slutprovet jämför sedan
**riktig fryst 137-klient/policy mot riktig ny produktionskod**, inte bara
en ersättningsfunktion. Alla HTTP-svar och klockor är fejkade; ingen riktig
profil lästes. Varje steg verifierar aktuella total-/auto-/korttak, inklusive
halva/75 %-budgetarna medan respektive fas gäller.

Start och seed enligt Projektledarens verifierade läge:

- Start **2026-10-15 12:46:36 Europe/Stockholm**, **74 totalt/61 auto**.
- Warm till **2026-10-16 11:39:30**.
- Strong till **2026-10-15 15:32:48**, soft till **2026-10-17 15:32:48**.
- Seedkostnaderna läggs i en föregående minut. Full realledger/tidsfördelning
  är okänd; detta är ett **live-liknande scenario, inte exakt driftreplay**.
- Mixed: lokal 06–08/12–14 spelar, 02–06 idle, övriga 16 timmar Windows.
  Continuous: spelar oavbrutet i 72 h. HTTP tar 120 ms; inga nya manuella
  kommandon, extra thumbnail-fallbacks eller externa appar ingår.
- Mobilbyten schemaläggs deterministiskt (seed 421, 151–229 s mellan byten).

| Scenario/policy | HTTP under 72 h | Max rullande 24 h total/auto | Längsta spelande dag-/nattgap | Tryck ≥50 % / full budget, timmar |
| --- | ---: | --- | --- | --- |
| Mixed, 137 | 2538 | 1174/1174 | 60,12/30,12 s | 0/0 |
| Mixed, ny | 5659 | 1954/1941 | **5,12/30,12 s** | 0/0 |
| Continuous, 137 | 11554 | 6284/6284 | 60,12/90,12 s | 47,276/0 |
| Continuous, ny | 15472 | 6407/6407 | **120/101,293 s** | 69,070/0 |

Max rullande kortförbrukning var sex i samtliga trace. Inget full-budgetstopp
uppstod, men en lång tail är fortfarande gles polling och har märkbar
upptäcktslatens. Äldre seed-explicitkostnader kan ingå i totalmax medan
nya trace-anrop här bara är automatiska. Maxen inträffar i olika recovery-
faser; aktuella fasers lägre tak kontrolleras separat vid varje steg.

### Upptäcktstid dagtid, sekunder inklusive 120 ms HTTP

| Scenario/policy | Median | p95 | Max observerad |
| --- | ---: | ---: | ---: |
| Mixed, 137 | 15,172 | 42,228 | 51,249 |
| Mixed, ny | **2,769** | **4,832** | **5,196** |
| Continuous, 137 | 10,409 | 29,162 | 56,757 |
| Continuous, ny | 6,129 | **84,720** | **115,688** |

I mixed är nattens median/p95/max oförändrat 15,619/27,768/29,774 s.
I continuous blir nya nattmåtten 38,523/91,290/100,564 s mot tidigare
20,948/45,152/89,884 s. Att spendera mer tidigt på dagen lämnar mindre
utrymme senare; tidig 5 s-takt beskrivs därför inte som 5 s hela dygnet.

Resultat: `build/active-api-recovery-2026-10-15/final-comparison.json`.
Reproducerbar jämförelse: `tools/simulate_active_api_recovery.py`.
Detta är valda stresstrace, **inte universella maxlatensgarantier**.
Mer explicit trafik, saknade thumbnails, lång HTTP eller nya Spotifyspärrar
kan ge andra utfall. Andra appar delar osynlig kvot; 429-frihet garanteras inte.

## Regression

**168 upptäckta, 166 körda PASS, två befintliga C++ SKIP** i
`test_focus_countdown`: `test_cpp_state_cache_and_ui_calls` och
`test_cpp_actual_touch_handler_and_media_dispatch` (ofullständig MSVC/headers).
Logg: `build/active-api-recovery-2026-10-15/python-regression.log`.
Compileall och `git diff --check` PASS.

Sex nya prov i `tests/test_active_api_recovery.py` använder riktig
FileBudgetStore/mock HTTP och täcker day-playing i warm/strong/soft,
bevarat natt/idle, högre adaptiv 20 s-gate, verklig Retry-After,
halva total-/auto-tak och fortsatt pressure/tail. Hela workerflödet visar
fortsatt en manuell GET följd av vanlig ungefär femsekundersautomatik,
utan aktivitetsboost eller kvarvarande reserv.

De 17 manuella och tio control-/confirm-regressionerna finns kvar, inklusive
ihållande 401/max två GET, källbyte, omslag/engine-cache och paus → play.
Den manuella stresstestfixturen anger uttryckligt 60 s-dagvärde för att
fortsatt prova preemption av en giltig lång lokal profil; en separat ny
workerassertion provar den nya faktiska 5 s-standarden.

Äldre transportfixturer har uttryckliga nya aktiva dagsförväntningar,
med tidigare verkliga Retry-assertions och 60 s-idleprov bevarade.
FileStore-stressen hanterar en utgången syntetisk operation genom att
bevisa **noll fortsatta HTTP och släppt reserv** innan nästa separata
testoperation. Produktions-TTL/grants höjdes inte och gammalt användararbete
spelas inte om. De faktiska spacing-/rolling-assertions är oförändrade och
provet kräver fler än 24 verkligt mockade HTTP för att inte bli vakuöst.

## Fryst kandidat och bevarande

- EXE: `D:\DEV\Ai\Github\Bongo-Cat-Screen\dist\companion-2026-10-15-active-api-recovery-dev\BongoDeskSpotify.exe`
- Storlek: **19656937 byte**.
- SHA-256: `17466EBFC95B14FDFB93D717BB9700F5937087AC27933CCDF82DF98E8C77C1C0`.
- Källmanifest: `build/active-api-recovery-2026-10-15/source-frozen.json`,
  **75 filer** och separata kopior under `source-frozen/`.
  SHA: `0311312B2631F2E0F59CB66F80C6BF6DB0F9F01F60EA46C93D52E7384632DA86`.
- Kandidatmanifest: `build/active-api-recovery-2026-10-15/candidate.json`,
  SHA: `72D5437D1171731205039A23DC2D32F40EC5BD519D0015E9E6918071226CCEF3`.
- Paketmanifest: `build/active-api-recovery-2026-10-15/package-verification.json`,
  SHA: `5FC4B4EC8D020D03F01B431690918F9F3CCB21F0BEB520BF30E75445C4ED55C7`.
- Slutsimulering SHA: `1AC8AC7F529AA17A1C1D0AC25E798BB02BE85C61A3CE9FB761BD0723AFDCE69A`.

Elva kompilerade moduler och fyra resurser matchar källan; Stockholm-tzdata
ingår. Projektledaren har även oberoende paketgranskat samma EXE skrivskyddat.
Före-baslinjen har **73 filer**, och **592 tidigare artifacts** är oförändrade
i storlek/SHA. 137:s 71 kopior/manifests, dess funktionsrapport och äldre
CB/B8-/firmware-/releasefiler är bevarade. Ingen firmwarebyggnad/flash gjordes.

Ändrade produktionsfiler är endast `companion/api_budget.py` och
`companion/spotify_api.py`. Äldre tester med avsiktliga ändrade förutsättningar:
`tests/test_api_budget.py`, `test_adaptive_connect.py`, `test_spotify_cooldown.py`,
`test_api_control_confirmation.py`, `test_manual_api_refresh.py`,
`test_api_budget_integration.py`. Nya filer är denna rapport,
`tests/test_active_api_recovery.py`, `tools/simulate_active_api_recovery.py`
och `tools/verify_active_api_recovery_candidate.py`. Separata driftrapporten
har kompletterats. Ingen config, settingslayout, media-/engine-/firmwarekälla,
Git-commit eller release ändrades.

## Kvar för verklig drift

Projektledaren hanterar byte med profil-/ledgerbackup, samma gemensamma
fil-lås och ingen pending/in-flight HTTP; 137 är rollback. Kontrollera
dagspelande API-status med 5 s-grundintervall och flera mobilbyten,
med separat observation av låttext och omslag. Bekräfta manuellt väntetryck,
vanlig NÄSTA/paus → play och Windows-återkomst med samma omslag.

Faktisk mobil-/skärmlatens, senare budgettryck, natt/idle och sleep/resume
har inte accepterats för denna nya EXE. Kända Retry-spärrar respekteras;
ingen verklig 429 ska provoceras för provet. Verifierade driftsfakta läggs
endast till i den separata driftrapporten.

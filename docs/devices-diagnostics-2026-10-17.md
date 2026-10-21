# Tillfällig devices-diagnos – 2026-10-17

## Status och incidentgräns

**Byggd och isolerat verifierad; inte installerad, startad eller driftprovad.
Ingen rättning påstås.** Installerat par är enligt Lead fortsatt
**3EDD2187/55669C87**; firmware, profiler, Run och release lämnas orörda.

Dagens verkliga Waiting-fel hade fortsatt musik på upplåst iPhone 13 Pro,
Spotify i bakgrunden och ingen datorSpotify. A200 senast **13:23:49.347**,
första A204 **13:23:54.568**, fortsatt A204 **14:01:52.117**. Dagens gamla
B-möjlighet avbröts **13:13:47.537**, attempt=0: **inget B-HTTP idag**.
Frisk ESP32-kontakt och inga aktuella budget-/Retry-/klockspärrar förklarade
inte tomheten. Lokalt nätverk var PÅ; användaren angav iOS 26.6.2 och Spotify 9.1.90.

Detta skiljer sig från gårdagens verkliga A204/B204/A204 i
[frysta incidentrapporten 0D56194C](spotify-background-incident-2026-10-16.md).
[Återfallsrapporten 0CD43BDF](spotify-connect-recurrence-2026-10-16.md)
redovisar även datorappens frysta pausade metadata. Gårdagens avslutade
45-minutersprov med A200, 16:34–17:20, omfattar inga senare data.
Ingen permanent tiominutersorsak eller telefon-/tjänstorsak är fastställd.

## Avgränsad funktion

Devices ersätter B i **denna kandidat**. Första automatiska tomma A armerar
sessionens enda möjlighet, med 90 s monotonic TTL. Nästa redan förfallna
automatiska A ersätts av `/me/player/devices`; därefter fortsätter A.
Samma klient, worker, lås, automatisk ledgerdebitering och pacing används.
Högst **ett transportförsök**, utan HTTP-retry även vid 401.

A-återkomst, source-/epochbyte, TTL och väntande manuellt/kontrollarbete
avbryter före nätstart; slutguarden kontrolleras efter OAuth och durable I/O.
Möjligheten förbrukas redan vid armering: avbrott kan ge noll devices-GET.
`phase=guarded, attempt=1` är ett konservativt guardförsök, inte bevis på
HTTP-start. Ett efterföljande I/O-stopp kan fortfarande innebära noll GET.

Devices publicerar ingen metadata och ändrar inte A:s snapshotålder,
idle/playing eller omslag. Även nekad diagnos har en egen väntväg utan
publicering: minst ordinarie intervall och gällande spärr, med manuell prioritet.
401/403/transport-/parsefel avslutar provet; 429 behåller gemensam Retry-spärr.

`SPOTIFY_DEVICES_HTTP` loggar faktisk svarsstatus med `endpoint=available_devices`.
`SPOTIFY_DEVICES_BODY` skiljer valid/invalid och loggar endast antal totalt,
aktiva, smartphones, aktiva smartphones, private och restricted. Smartphone
räknas oavsett skiftläge efter strikt typkontroll. Tom korrekt lista ger
giltiga nollor; fel form ger inga antal. Formatteraren avvisar främmande
fält och str-/int-subklasser. Inga namn, ID:n, token, URL:er, headers,
råa kroppar eller fria feltexter tillförs.

## Verifiering och reproduktion

Ändrat: `companion/spotify_api.py`, `media_bridge.py`, `diagnostics.py`;
nya `tests/test_devices_diagnostics.py`, `tools/devices_diagnostics_candidate.py`
och denna rapport. Det historiska B-testets import/undantag pekar nu på
oförändrad fryst 3EDD-källa; dess gamla beteende räknas inte som aktuell funktion.

Från projektroten, Python 3.10:

```powershell
python -X utf8 -B tools/devices_diagnostics_candidate.py focused
python -X utf8 -B tools/devices_diagnostics_candidate.py regression
python -X utf8 -B tools/devices_diagnostics_candidate.py freeze
```

**20 riktade PASS.** Senaste fullkörningen: **218 upptäckta, 216 PASS,
2 kända C++ SKIP**, 21,991 s, noll fel/externa nätförsök. Två fullkörningar
gjordes: den första fann ett undantagstypsfel i det historiska testets nya
modulalias; den andra verifierade rättningen. Ursprungliga loggar bevaras.
Äldre olöst testvariabilitet är inte förklarad av denna lyckade körning.

Exakt byggkommando från `build/devices-diagnostics-2026-10-17/source-frozen/companion`
(PyInstaller 6.22.3; utdata i `pyinstaller-build.log`):

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYINSTALLER_CONFIG_DIR = 'D:\DEV\Ai\Github\Bongo-Cat-Screen\build\devices-diagnostics-2026-10-17\pyinstaller-cache'
python -X utf8 -B -m PyInstaller --noconfirm --clean --workpath 'D:\DEV\Ai\Github\Bongo-Cat-Screen\build\devices-diagnostics-2026-10-17\pyinstaller-work' --distpath 'D:\DEV\Ai\Github\Bongo-Cat-Screen\dist\companion-2026-10-17-devices-diagnostics-dev' BongoDeskSpotify.spec
```

Paketkontroll från projektroten:

```powershell
python -X utf8 -B tools/devices_diagnostics_candidate.py verify
git diff --check
```

Paketkontroll: 50 Pythonkällor kompilerade i minnet, elva moduler,
fyra resurser och Stockholm-tzdata matchar fryst källa; seek saknas.
**157 aktuella +157 frysta källor**, 8 603 äldre skyddade filer bevarade.
AST-kontroll bevarar gemensam HTTP/auth/retry/guard och övriga klient-/bridgehjälpare.
Äldre arkiverade EXE-kopior återställdes inte. Slutdiff och textkontroll godkända.
Lead har oberoende verifierat EXE, manifest, källor, paketerade kodobjekt,
resurser, tzdata, seek-frånvaro och samtliga skyddade filer: PASS.

## Fryst kandidat

EXE: `dist/companion-2026-10-17-devices-diagnostics-dev/BongoDeskSpotify.exe`.
**19 656 698 byte**, SHA-256
`687211432857B34424EDA3D203F645C7324C0639D2F2308367D185987BBB5A50`.

Manifest i `build/devices-diagnostics-2026-10-17/`:

| Fil | SHA-256 |
| --- | --- |
| source-frozen.json | `96FD7DE27C7EA77799CCC54E65E1A5780823AA5E5BAD9ACA974A9D66D94D285E` |
| package-verification.json | `9800F06692E2348790E02C839130B6998B35D71D7FE545AB7E8F6522375B313F` |
| scope-verification.json | `DCA6B2E8206A5DAB6B6F11DBC610D245D53661084AEC952F0789DE0879552B41` |
| candidate.json | `AD88C54D8AE09620580F33579CEB039CF0373078CDA01C4BD47487632F77E275` |

## Driftgräns

Ett giltigt 200 ger en annan autentiserad läsvy; tom/inaktiv lista kan stärka
Connect-synlighetsspåret, aktiv smartphone samtidigt med A204 kan stärka
skillnad mellan tjänstens vyer. [Spotify](https://developer.spotify.com/documentation/web-api/reference/get-a-users-available-devices)
anger befintlig `user-read-playback-state` men garanterar inte komplett lista.
Provet identifierar därför inte säkert iPhonen eller slutorsaken och är ingen
återhämtning. Liveutfall och stabilitet väntar. Lead granskar kandidaten före
användarens separata, hashbundna installationsgodkännande. Ingen produktstart,
installation, live-API, verklig tokenläsning, flash, commit, push eller release.

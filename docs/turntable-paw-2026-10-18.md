# Tonarm och Bongo-tass – 2026-10-18

## Status och kandidat

**Byggd/hostverifierad, inte flashad eller skärmprovad.** Spotify-felsökningen
är pausad. Installerat par är fortsatt **companion 68721143 / firmware 55669C87**;
kanonisk app, autostart, genvägar och runtime är orörda.

Kandidat: `.pio/candidates/turntable-paw-2026-10-18-3606F2E0.bin`,
**936 032 byte**, SHA-256
`3606F2E02C32736E5049F4044A51CC92017B7E890CCCEF9D9C0EEA8F95CD8103`.
Profil `esp32-024r-spotify-fastserial`, 230400 baud, app vid `0x10000`,
inte fullbild vid `0x0`. Ingen companionbuild, installation eller release.

## Beteende och skydd

- Fast pivot (214,60), konstant armlängd cirka 106 px. Play svänger in/sänker,
  pause lyfter/parkerar. Nålen följer faktisk position/duration med Q16-utjämning.
  Okänd duration håller föregående mål; ny okänd låt får stabil mellanposition.
- DEFAULT förbereder; TRACK_CONTEXT identifierar ett byte även vid samma
  metadata/omslag. NONE→samma identitet och resync ger ingen ny fysisk rutin.
  Titel/progress uppdateras direkt genom oförändrad parser.
- Normal skivsekvens 1 080 ms, armen klar omkring 1 130 ms i simuleringen.
  Var femte avslutade stabila byte tar ut skivan åt vänster: 1 450 ms,
  arm klar omkring 1 480 ms. Räknaren kräver 400 ms utan ny identitet.
  Snabba skips ersätter målet i pågående rutin utan kö; senaste play/pause gäller.
- Försenat omslag använder generic under bytet och därefter endast 180 ms
  ytreveal, inget nytt lyft/tassbyte. Meny/DJ/panel/Fokus-resize landar aktuell
  scen utan återspelad kö. Skiva/arm/tass är separata inerta screen-lager,
  utanför rundklippningen; omedelbar linjeritning behåller inga punktpekare.
- Oförändrad 172/144 px viewport och albumzoom: synlig diameter cirka 168/140 px.
  Generic får samma 56/112-radie. State 84 B, befintlig 25 088 B projektion återanvänds.
  Inga gamla bildpekare lagras; endast committed-art läses, alias avvisas,
  RX/committed-art skrivs aldrig av animationen. Art2-ACK föregår tung rendering.
- Ingen ny API/serialtrafik, blockerande sleep eller stor återkommande allokering.
  Vid projektion-OOM uteblir effekten; reduced generic använder endast dold
  DJ-scratch. DJ-canvas/touch och övrig fallback bevaras. Seek återinförs inte.

## Filer och prov

Ändrat: `src/bongo_cat_featured.inc`, `tests/test_record_flip.py`,
`tests/test_focus_countdown.py`, `00_PROJECT_CONTEXT.md`, `01_CURRENT_STATE.md`,
`02_DECISIONS.md`. Nytt: `src/media_turntable.h`, `tests/turntable_paw_host.cpp/.py`,
`tests/test_turntable_paw.py`, `tools/turntable_paw_visuals.py`,
`tools/turntable_paw_candidate.py`, denna rapport och daterade utdata.
Äldre 280 ms-helpern bevaras och testas separat från aktuell scen.

**19 native-prov PASS:** arm/progress/okänd duration, 1 ms-konvergens,
vanligt/fullt byte, sent omslag, snabba/sena skips, identitet/resync,
livscykel/Fokus, wraparound, geometri, kapacitet/alias, OOM och faktiska
firmware-commit/ACK/BEGIN-kroppar.

Slutlig suite: **237 upptäckta/235 PASS/2 kända C++ SKIP**, 24,857 s,
noll fel/externa nätförsök. Två äldre Fokusprov saknar fullständiga MSVC
SDK-headerfiler; nya native-prov kördes. Tre fullkörningar redovisas i loggarna:
gamla UI-strukturassertioner anpassades, därefter tillkom stabilitetskantfallet.
Övrig Fokus-layout, touch, art2 och åäö-regressioner kvarstår.

En delad temporär Fokusfixture skrevs före SDK-skip; ursprungsbytes återställdes
från fryst baskälla med exakt före-hash. Ny utdata/bevis sparades under
`build/turntable-paw-2026-10-18/focus-fixture-preservation.json`.
**5 154 äldre skyddade filer, 163 aktuella +163 frysta källor** verifierade.

## Förhandsvisning och granskning

[HTML/åtta GIF-förlopp](../visuals/turntable-paw-2026-10-18/r5/index.html):
normal/Fokus, play/pause/progress, tassflip, pausat/fullt byte, sent omslag,
snabba skips. **SIMULERAT, EJ TFT-PROVAT:** faktisk native C++-state,
projektion/primitiver, tidigare källstyrd UI/glyphbakgrund. Position/rotation
är scripted inputs; PIL-rasterisering och hosttempo bevisar inte TFT-takt.

UI godkände **r4 för V1**, inga blockerande fynd. r4:s 18 outputfiler är
byteidentiska med r3. Slutlig r5 korrigerar endast negativ kompositoravrundning
till C++ (upp till 1 px), utan ändrade poser/tider. Code såg r5:s
play-pause-progress.png; Lead såg r5:s complete-change.png och tidigare
r3-overview/paw-flip/play-pause-progress. Inget påstående om granskning av
samtliga GIF-bildrutor. Lead verifierade oberoende 163 källpar och alla 18
r5-outputhashar/källpins: PASS. UI:s avgränsade godkännande gäller r4.

## Byggbevis och återstående fysisk kontroll

RAM **112 408 B / 34,3 %**, program/flash **935 293 B / 47,6 %**; ESP-imagechecksum valid.
Separat `PLATFORMIO_BUILD_DIR`; befintligt paketlås krävde byggbehörighet.
Inga nya beroenden, authscope-/budget-/protokolländringar.

Körda kommandon från projektroten:

```powershell
python -X utf8 -B tools/turntable_paw_candidate.py focused
python -X utf8 -B tools/turntable_paw_candidate.py regression
python -X utf8 -B tools/turntable_paw_visuals.py --revision r5
$env:PLATFORMIO_BUILD_DIR='D:\DEV\Ai\Github\Bongo-Cat-Screen\build\turntable-paw-2026-10-18\pio-build'
pio run -e esp32-024r-spotify-fastserial
python -X utf8 -B tools/turntable_paw_candidate.py freeze
python -X utf8 -B tools/turntable_paw_candidate.py verify --preview r5
git diff --check
```

Bevara frysta utdata vid reproduktion; välj nytt bygg-/previewområde.
Manifest i `build/turntable-paw-2026-10-18/`:

| Manifest | SHA-256 |
| --- | --- |
| source-frozen.json | `9BDB9EBB8D6EAF1E796CB7691C0C4C17DC5D46BCD7B63C9A3D808460E811ADE3` |
| scope-verification.json | `0E99FC007BBA9EDA1D7412EE875152332673BA04EE0C9451155F79F4D7A74D5E` |
| firmware-verification.json | `3B413895B1E8D90946740EB0AA654F80E3FA91DBCE2E0030BBB255D4B0E4BB6A` |
| candidate.json | `29E155ED9A1E0975819D13CBF65640939F2BB4FB5DAD88EDB9D0874A55CFF723` |

r5 previewmanifest: `EA41CEB8CFB2A3C1D0EDC1E129ABD90F59718F3EC95B7ED9FA67856ECDBCFB22`.
UI-granskat r4: `CD817958DFD850CFD61D49D0369EB964F465056C9F65B08CCABC7E82B2723F83`.

Efter separat hashbundet flashgodkännande återstår faktisk jämnhet,
heap/minheap/stackmarginal och touch under art2, play/pause/extern korrigering,
fem lugna byten/samma omslag/sent omslag/snabba skips samt meny/DJ/Fokus och
sleep/väckning. Två LVGL-objekt och ritprimitivernas stackarrayer har ännu
omätt dynamisk kostnad på enheten. Ingen flash, runtimeåtgärd, live-API,
commit/push/tag/release gjordes.

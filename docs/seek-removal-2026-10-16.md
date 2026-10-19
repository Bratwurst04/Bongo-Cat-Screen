# Seek borttaget – 2026-10-16

## Beslut och status

Användaren avbröt seek efter det underkända börjanprovet och beställde
borttagning. Seekutredningen avslutades; ingen ytterligare seekrättning
eller orsaksdiagnostikkandidat gjordes. Historiken finns i den separata
[driftrapporten](playback-diagnostics-runtime-2026-10-16.md).

**Borttagningen är byggd och granskningsbar, inte installerad eller
fysiskt accepterad.** Installerat par är fortfarande **26A0FAF0 / C7E594B4**
enligt Lead. Ingen flashning, verklig API-/profilåtgärd, commit, push eller
release har gjorts av Code i detta steg.

## Omfattning

- Firmware saknar seekyta, gesttillstånd, kontextrevision för seek och
  utgående SEEK-kommandon. Nedre tidsytan använder vanliga medietryck,
  NEXT/PREVIOUS-svep och DJ-svep. Fokus, panelmeny och långtryck bevaras.
- `media_commands.py` ersätter `media_seek.py` med endast PLAY_PAUSE,
  NEXT, PREVIOUS samt de generella kontroll-/refreshtyperna.
  Seekparser, köplatser, Windows-positionändring, Spotify-förberedelse,
  seek-PUT och de två överblivna device/track-fälten är borttagna.
- **`MEDIA_TRACK_CONTEXT`** ersätter seeknamnet för skivans identitet.
  Firmware läser prefixets 20 tecken med strikt heltalskontroll.
  Ny identitet med samma synliga text ger rätt flip och avbryter gammal
  art2-mottagning; samma identitet/resync gör inte det. Korrigerad längd
  räknas fortsatt inte som ny skiva. Det nya paret använder detta fält ihop.
- Vanliga explicitgrants har oförändrad kostnad tre och tagg ett.
  Nya seekgrants nekas. Äldre tagg-två-grants kan fortfarande läsas utan
  ledgerreset eller migrering. Budgetgränser, tids-/I/O-skydd, pacing,
  Retry, tokenflöde, dagintervall fem sekunder och manuell vänteläsning
  bevaras. 26A0:s innehållsfria playbackdiagnostik finns kvar.

Berörda produktfiler är `src/bongo_cat_featured.inc`, ny
`src/media_track_context.h`, `companion/{engine,media_bridge,spotify_api,
api_budget,diagnostics}.py` och nya `media_commands.py`.
`src/media_seek_touch.h`, `companion/media_seek.py`, rena seektester och
den aktuella seekpreviewgeneratorn är borttagna. Generella tester och
native-fixturer är uppdaterade. Kontext-/status-/README-filer har daterade
pekare; äldre releasebeskrivningar är bevarade.

## Verifiering och öppen begränsning

- Full körning r3: **182 upptäckta, 180 PASS, 2 SKIP**, inga fel eller
  externa nätförsök. De två kända Fokus/touch-proven kräver ofullständigt
  tillgängliga MSVC-runtime/headers och är inte hävdade godkända.
- Beteendeprov visar att gamla wire-/direktkommandon ignoreras utan nya
  Spotify-anrop/reservationer. Separat publikt API-prov gav samma resultat.
  Native-prov kör faktisk firmwarekod för vanliga mediegester, 1/2/3-tryck,
  spärr vid meny eller nedhållet finger, neutral kontext, art2-avbrott och skivflip.
  UTF-8, Fokus, omslag, återanslutning, manual refresh och budget ingår.
- AST-jämförelse visar oförändrat helt budgetmodulträd utom den borttagna
  grantgrenen samt oförändrad Spotify-modul utom seekmetoder/import/fält.
  Produktskällan och EXE saknar seekmodulen/API-vägen; firmwarebinären
  saknar gamla seekkommandon. Låsfilernas `handle.seek(0)` är kvar.
- **Testvariabilitetens orsak är fortfarande olöst.** R1 hade tre fel,
  r2 två, r3 noll med samma produkt-/testkälla. Endast runnerns extra
  felrapportering ändrades; inga guards, asserter eller skip lättades.
  Riktade fem fall × tre gav 15 PASS med kopierad fryst 26A0-källa och
  14 PASS/ett fel med aktuell kopia. Därefter gav ett instrumenterat
  enskilt fall × tio per version inga fel. Ingen exakt budgetorsak/errno
  fångades. Detta bevisar varken en rättad fixtur eller stabil drift.
  Alla loggar är bevarade; r3 väljs inte som bevis att tidigare fel försvunnit.
- Båda byggen: PASS. EXE:s elva moduler, fyra resurser och Stockholm-tzdata
  matchar fryst källa; `media_seek` ingår inte. 47 Pythonkällor kompilerades
  i minnet. **154 aktuella + 154 frysta källor** och **1 586 äldre
  artefakter/rapporter** matchar byte/hash. Lead har oberoende verifierat detta.
- `git diff --check` och separata textkontroller: PASS.

## Fryst nytt par

| Artefakt | Fil | Byte | SHA-256 |
| --- | --- | ---: | --- |
| Companion | `dist/companion-2026-10-16-seek-removal-dev/BongoDeskSpotify.exe` | 19655221 | `4D4A84E86F5439FF80F555AD10A7C8003EFBC950E3B24ABE51105D9E1D28DC82` |
| Firmware, app vid **0x10000**, drift **230400** | `.pio/candidates/seek-removal-55669C87.bin` | 932080 | `55669C87CF8459996F173154691C6002B02D4DA193BAF13C3CBA801E18B40577` |

Underlag: `build/seek-removal-2026-10-16/`.

- `source-frozen.json`: `6A2B249DA6ACAC201C9B27B3B8A07697227C681734F140F9B168BE0D160E1A07`.
- `package-verification.json`: `71D982A07FFCCF4E7C02F22A3EE0AC4783D297E58377426421E1E4F95CBEF1C2`.
- `candidate.json`: `D2ABFA57278244ECE6752900C8C551344E2150A0E023EA9F6AF86B955EC2B40A`.
- `scope-verification.json`, `python-regression*.log`, test-/probe-
  sammanställningar och båda byggloggarna redovisar verifieringen.

Tidigare 26A0-, C7-, 0D397-, seek-, preview- och releaseartefakter samt
deras frysta källor/manifester/rapporter är oförändrade. Äldre
verifieringsverktyg och previewreferenser avser historiska versioner.

## Fysisk kontroll återstår

Lead hanterar versionsgodkännande och eventuell installation av paret.
Kontrollera därefter vanlig bild, åäö/skivflip, omslag efter resync,
tryckgruppering och NEXT/PREVIOUS/DJ även från tidsytan, långtrycksmeny,
Fokus och återanslutning. Sleep/resume och långdrift med det nya paret
är fortfarande väntande. Testvariabiliteten ovan ska redovisas före beslutet.

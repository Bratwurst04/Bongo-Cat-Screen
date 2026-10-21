# Kattarm och lugnare lyft – 2026-10-18

## Beslut och gräns

Användaren avböjde flash av 3606F2E0: tassen skulle sitta fast i en kattarm
och lyft/nedläggning ta längre tid. Ny kandidat **627E6B93 är endast byggd
och verifierad i host/simulering, inte flashad eller fysiskt accepterad**.
Installerat par är fortsatt companion **68721143 / firmware 55669C87**.
Code har inte ändrat runtime, profil, autostart, companion, serialprotokoll,
API-budget eller releasefiler. Spotify-felsökningen är fortsatt pausad.

Föregående 3606F2E0, dess frysta källa, manifests, loggar, förhandsbilder
och [rapport](turntable-paw-2026-10-18.md) är byteidentiska.

## Ändring

- Vit, lätt stegformad underarm med svart pixelkontur fortsätter ut genom
  vänsterkanten. Tassens gamla svarta handledssöm är öppnad så den vita
  fyllningen sitter ihop. Arm och tass följer skivan i normal och Fokus.
  När hela handen lämnat bilden ritas inget kvarvarande armfragment.
  Ogiltiga rektanglar vid negativa koordinater utelämnas.
- Tonarmen går undan före greppet. Greppaus **120 ms**, eget mjukt lyft
  **260 ms**, flip eller komplett ut/in, sänkning **320 ms**, en diskret
  enpixels sättning och utdragning ger **1880 ms normalt / 2380 ms komplett**.
  Lyftets fem native pixlar håller skivan under Fokus-kortet. Tonarmen
  återgår bara om senaste uppspelningsstatus spelar.
- Senaste identitet/state, sammanslagna snabba byten, femte stabila byte,
  180 ms sen omslagsreveal, NONE/resync/duration och bufferägande bevaras.
  State är fortsatt **84 byte** och projektion återanvänder **25 088 byte**.
  Ingen ändring behövdes i `bongo_cat_featured.inc` eller touch/DJ/Fokus.

Ändrade befintliga filer jämfört med frysta 3606-källan:
`src/media_turntable.h`, `tests/turntable_paw_host.cpp`,
`tests/turntable_paw_host.py`, `tests/test_turntable_paw.py`,
`tests/test_focus_countdown.py`, `00_PROJECT_CONTEXT.md`,
`01_CURRENT_STATE.md`, `02_DECISIONS.md`.
Nya källfiler: `tests/test_turntable_arm_tempo.py`,
`tools/turntable_arm_tempo_visuals.py`, `tools/turntable_arm_tempo_candidate.py`.
Därtill denna rapport och separata build-/previewunderlag.

## Verifiering

- **23/23 riktade tester PASS**: fyra nya native-/rasterprov och 19 befintliga
  beteendeprov med uppdaterade tider. Sammanhängande vit komponent till
  vänsterkanten kontrolleras genom normal/full rörelse i båda layouterna;
  komplett uttag, giltiga rektanglar, kapacitet, fria textytor och separata
  gradvisa lyft-/sänkningsfaser täcks. Tidigare identitets-, paus-, omslags-,
  ACK/RX-, OOM-, progress- och wrap-prov passerar.
- Regression: **241 upptäckta, 239 PASS, två befintliga SDK-skip**, inga
  fel eller externa nätverksförsök. De två äldre Fokus C++-runtimeproven
  saknar komplett MSVC/headers; ingen verktygskedjereparation gjordes.
  Fokusfixtures och äldre native-hjälpare isolerades före testupptäckt.
- Fastserialbygge **PASS**, 71,765 s. RAM **112 408 byte (34,3 %)**,
  programflash **935 505 byte (47,6 %)**. Image checksum och validation hash
  är giltiga. **166/166 aktuella/frysta källor** matchar och 57 Pythonkällor
  kompilerar. **5961/5961 skyddade äldre filer** är byteidentiska.
- `git diff --check` passerar; endast befintlig LF/CRLF-varning för
  `tests/test_focus_countdown.py`. UTF-8-underlagen är läsbara.

## Kandidat och spårbarhet

Appfil: `.pio/candidates/turntable-arm-tempo-2026-10-18-627E6B93.bin`,
**936 240 byte**, profil `esp32-024r-spotify-fastserial`, drift 230400,
appadress `0x10000`. Inget flashgodkännande har lämnats för denna hash.

**SHA-256:** `627E6B93F3A4B2CC4E649C5EAF3D4FCA1164EB9989339B6A4AFFEB25B9E6D571`

Separat område: `build/turntable-arm-tempo-2026-10-18/`.

| Manifest | SHA-256 |
| --- | --- |
| source-frozen.json | `9F5F06B270BC559D77FE610BC085BACE6484AA25E55E7604D19E9AEDD294E7D5` |
| scope-verification.json | `6B5699781F7BD1F41A4BD8D7025EA700C68339F8CAA245FF8C651633C1736B56` |
| firmware-verification.json | `675A4DC1B34EF046E1DB8433DAA3A4CC267E3A7E0652C805271D82479E3D90E4` |
| candidate.json | `88C220A0EE48EF7A952DF5D764EBA1D06141776C1FA14A7686BBDA8EEA3830F1` |

## Visuell granskning och kvarvarande prov

[R1-förhandsvisning](../visuals/turntable-arm-tempo-2026-10-18/r1/index.html)
innehåller nio källstyrda scenarier med tidslinjer från C++-konstanterna.
Previewmanifest: `F2873C36AE7EEF17C0F185F604F8A526174FCE1F50AA5BE1C7E846B864A7FD5C`.
UI godkände via Lead just sammanhängande arm/hand och lugnare tempo utan
blockerande fynd, utifrån stillsekvenser/GIF-mellanrutor. Lead granskade
`paw-flip.png` och `focus-complete-change.png`. Det är ingen uppmätt TFT-takt
eller fysisk acceptans; PIL/LVGL kan också skilja i kantpixlar.

Efter ett separat hashbundet flashgodkännande återstår kort fysisk kontroll:
normal/full rörelse i båda layouterna utan glapp/stump eller skymd text;
lyft/landning och faktisk jämnhet; paus under byte samt snabba byten/sent
omslag; meny/panel/Fokus/DJ och vanliga mediegester under animation;
heap/stack och sleep/resync på enheten. Ingen flashning görs i denna uppgift.

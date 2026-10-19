# Kompakt omslag C2: 80×80 RGB565 – 2026-10-18

**Byggt/isolerat verifierat, inte installerat eller flashat. Ensekundsmålet är
oprövat för detta par.** Installerat är fortfarande **445D72A0/860896DB vid
921600**, med det [underkända fartprovet](artwork-fast921600-runtime-2026-10-18.md).
Den rapporten sparades före produktändring: SHA-256
`1627C43E2CA2046DD055D035151C4D8CA8B0C869D857A6EE0D3D87C2D550258C`.
Ingen runtime-/profil-/COM-/API-/installations-/flashåtgärd görs här.

## Val och avgränsning

En lyckad äldre sändning på 703 ms behövde ändå 1652 ms till ACK; decode/line-fel
gav en annan leverans på 12344 ms. Backlog/paint och byteförlust är hypoteser,
inte fastställda orsaker. Ett extra drainpass kan hjälpa men undanröjer inte
294 raders buffertryck under en lång paint. Ingen mindre bevisad orsaksfix
hittades. Lead valde därför den mindre bild som användaren ursprungligen
föreslog, utan större kö eller nytt serial-IO-lager.

| Format | Payload | Chunks | Ungefärlig ASCII-wire / ren tid vid 921600 |
| --- | ---: | ---: | ---: |
| Äldre 112 RGB888 | 37 632 byte | 294 | 59 366 byte / 644 ms |
| Hypotetisk full 112 RGB565 | 25 088 byte | 196 | 39 573 byte / 429 ms |
| Vald 80 RGB565_BE | **12 800 byte** | **100** | **20 179 byte / 219 ms** |

Siffrorna använder största transfer-id och inkluderar header/END. Bara det
sista RGB565-formatet implementeras. En kompakt helbild plus header/END
ryms i den befintliga 96-events-kön och återstoden i 8192-byte UART vid ett
enstaka renderstopp med i övrigt ledig kö; obegränsad köbelastning garanteras inte.

- Ren `artwork_codec.py` kodar befintligt 112 RGB888-input med centre-nearest
  och RGB565_BE. Ingen LANCZOS av färdig grön-key-bild och ingen ny färgblandning.
  Cache, `media_bridge`, API, auth och polling/budget är bytebevarade.
- Egen profil `esp32-024r-spotify-compact80`, 921600 runtime/115200 upload,
  annonserar färsk `RGB56580`-kapabilitet endast med core-0-RX. Den annonserar
  **inte** gamla FAST. Gammal FAST-cap räcker aldrig för kompakt payload.
  Default 230400 och tidigare profiler bevaras.
- En uttrycklig BEGIN565-variant återanvänder ART2-chunks, CRC, id/epoch,
  ACK/reason/abort och tidsgränser. Kompakt retry behåller formatet med en
  chunk/15 ms. Äldre ART2/raw behålls. En sista ERROR-kontroll före END
  undviker att redan avvisad sista batch felaktigt loggas som ART_SENT.
- Mottagning sker i första 6400 orden i inaktiv 112-slot. Efter CRC expanderas
  samma slot baklänges till 12544 ord: sourceIndex≤destinationIndex skyddar
  oläst input. Först därefter aktiveras bilden/ACK skickas. Deskriptorn är
  fortsatt 112×112/25088 byte. RGB565_BE:s råa byte matchar LV_COLOR_16_SWAP=1
  och befintlig `pushColors(..., false)`; ingen dubbel byteswap görs.
- Arm/tass/tonarm, 1880/2380 ms, identitet/coalescing/late-art, touch, DJ,
  Fokus och borttagen seek bevaras. Ingen ny stor bildbuffer eller kö införs.

## Verifiering och bildgranskning

**64/64 riktade PASS**; en relevant regression gav **266 upptäckta,
264 PASS/två kända Fokus SDK-skip**, noll fel/externa nätverksförsök.
Faktiska firmwarefunktioner för parser/CRC/slotaktivering/uppskalning och
LVGL-färgmakrot körs nativt med avgränsade String/base64/IO/UI-hoststubbar.
Tester täcker oberoende PIL-referens för expansion, kapacitetsvakter,
gammal aktiv slot, descriptor/pointer, chroma/byteordning, 100 chunks,
legacy-avvisning, färsk cap, kompakt retry, CRC/order/length, rapid abort,
partialwrite och sista-batch-fel. Den första hostlänkningen fick ett artificiellt
stackprobe-behov från stora String-stubbar; stubben ersattes med små vyer,
utan SDK-/verktygskedjereparation eller produktändring.

[R1 normal/Fokus](../visuals/artwork-compact80-2026-10-18/r1/comparison.png)
och [detaljbild](../visuals/artwork-compact80-2026-10-18/r1/detail.png) går genom
faktisk packning→firmwareparser/CRC/staging/expansion→C++-skivrendering.
UI och Lead godkänner stillbildsjämförelsen: väntat grövre småtexter/linjer,
begripligt motiv, samma färger/storlek/centrum och ingen synlig ny grön halo.
Det bevisar inte komplett animation, fysisk TFT-kvalitet eller transporttid.
Previewmanifest: `0C010BC7DB308D04B795BAE84A76BE13E65A64187E269953349B0C1D55D078AC`.

## Modellgränser och exakt par

Modellen antar **500 µs per rad**, jämfört med tidigare 80 µs; inte ett
CPU-benchmark. Faktiska parser-/framer-/budgetregler används med angivna
virtuella paint-/flush-pauser. Transfer-id 1 ger cirka 215 ms wire.

| Antagande | ACK/commit | Max kö / UART | Tappade byte |
| --- | ---: | ---: | ---: |
| 50 ms paint per loop | 623 ms | 72 / 10 | 0 |
| 80 ms paint per loop | 953 ms | 82 / 10 | 0 |
| 300 ms initialt stopp + 50 ms paint | 871 ms | 96 / 1007 | 0 |
| 150 ms paint per loop | **1723 ms** | 92 / 10 | 0 |
| Varje flush 50 ms poll + 50 ms paint | 727 ms | 11 / 10 | 0 |

Alla gav korrekt bild, men långsam återkommande paint kan fortfarande missa
en sekund. Windows/USB, faktisk TFT/CPU, CH340-stabilitet och visad commit
behöver mätas på hårdvaran. Den tidigare verkliga CRC/framingproblematiken
påstås inte vara bevisat löst.

- Firmware `.pio/candidates/artwork-compact80-2026-10-18-C6EBAE4B.bin`,
  **936 704 byte**, SHA-256 **C6EBAE4B13DE934449E2F32738D2CBFAEEC2693C5ECF8EE8A3A71FDB6254D275**.
  Bygge PASS 116,220 s; RAM **112 416 byte (34,3 %)**, åtta byte mer än C;
  program **935 969 byte (47,6 %)**. Appadress `0x10000`, bildchecksum giltig.
- Companion `dist/companion-2026-10-18-artwork-compact80-dev/BongoDeskSpotify.exe`,
  **19 657 988 byte**, SHA-256 **356A5EC0BC224EB92C7A9748E68F7445BAE9C01149C5E739B7B9C146063B1813**.
  Standard-spec, inte körd/installerad. Tolv inbäddade produktmoduler och fyra
  direkta resurser matchar slutkällan.

Separata snapshots/manifests/loggar/modeller: `build/artwork-compact80-2026-10-18/`.
Produktändringar: `companion/engine.py`, `src/media_art_v2.h`,
`src/bongo_cat_featured.inc`, `platformio.ini`; nya codec-hjälpare
`companion/artwork_codec.py`, `src/media_art_compact.h`.
Därtill nya host-/test-/preview-/verifieringshjälpare, README-filer och
aktuella toppstatusar. Tidigare C/B/627-binärer, snapshots, rapporter och
previews bevaras, inklusive det underkända C-driftresultatet.

Slutverifiering: **178/178 aktuella/frysta källor**, 66 kompilerbara
Pythonkällor och **7269/7269 skyddade tidigare filer** matchar. A:s sparade
toppstatusar finns separat under `baseline-status/`. UTF-8 och
`git diff --check` passerar; Git ger LF/CRLF-varningar för `media_art_v2.h`
och den tidigare Fokus-testfilen, utan whitespacefel.

| Slutmanifest | SHA-256 |
| --- | --- |
| source-frozen.json | `0CCFC48F72C91D659EE4B58D76DB844B9FC85AA69931828B291263FDB218756F` |
| package-verification.json | `89FEE433CBA34B2FF896D79F90113255ADF5A13E2AA04D41D130FFE3D606438C` |
| scope-verification.json | `48FE506E5BC7884EC3B1917EBF2A5BCDDFC5D121AB829B0661D5A88C166D487D` |
| candidate.json | `B1DE1097EBF35D62F3AC67C7273D75A3E6A4D62C465DA60E169128ECE0BB7BCA` |

Efter ett separat hashgodkännande återstår fysiska ART_READY→ACK/visad-commit-
mätningar över flera och snabba byten, färg/key/utseende, retry/CRC/framing,
heap/touch/Fokus/DJ samt sleep/resync. Ingen flashfråga eller runtimeåtgärd från Code.

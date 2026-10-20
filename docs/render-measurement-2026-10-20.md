# Separata firmwaremätkandidater – 2026-10-20

**Endast byggda och statiskt granskade, inte flashade.** Installerat är fortsatt
**C42112AD/EBB334A9 vid 921600**. Användaren accepterade rättad PLAY/PAUSE-status
men rullningen rycker under uppspelning, även efter färdigt omslag, och är jämn
vid paus. Rotation/renderbelastning är en hypotes att mäta, ingen bevisad rotorsak.

| Kandidat | Profil | Appbinär vid 0x10000 | SHA-256 |
| --- | --- | --- | --- |
| Färre redundanta label-/färgskrivningar | `esp32-024r-spotify-compact80` | 937 360 byte | `B846FF5240E401B4800F3D075BE006EB97BD3448414DEE4AD66CF0842DA174FC` |
| Samma ändring och separat RAM-tidsmätning | `esp32-024r-spotify-renderdiag` | 938 192 byte | `D7DA9953E85449685912005B4062F9F15A8BCA720A9861781EFB946CCDE66B82` |

Lokalt: `dist/firmware-2026-10-20-render-measurement-dev/normal-compact80.bin`,
`render-diagnostics.bin` och `candidates.json`. Ingen ny companion-EXE eller release.

## Avgränsning

Medialabels jämför aktuell UTF-8-text före `lv_label_set_text`; art-boxens faktiska
bakgrund/border jämförs före färgskrivning. Äkta titel-/artist-/status-/tidsändring
uppdateras fortfarande. Companionens tresekunderssynk bevaras. Detta undviker
redundanta setteranrop; ingen jämnare scrollning, total heapbesparing eller
bevarad verklig LVGL-fas påstås. LVGL 8.3.11 bevarar normalt marquee-`act_time`
vid omladdning; ”samma text återställer alltid fasen” används inte som förklaring.

Vinylens 60 ms-steg, 172×172-skivytan, befintlig parent till `media_screen`
och full invalidiering, bildcache/refine/CRC,
core-0-RX/drainbudget, befintliga serialkommandon, touch, fonter och paneler
bevaras. Ingen ändring av SPI-/LVGL-period, inget nytt RX-kommando.

## Diagnosprofil och format

Endast diagnosprofilen sätter `BONGO_RENDER_DIAGNOSTICS=1`. Andra profiler har
mätningen av: hooks/statistik preprocessas bort. Normal binär saknar både
`DIAG_RENDER` och `RenderDiagnostics`-symboler; diagnosbinären har dem.
Program-RAM är **112 448/112 848 byte**, programflash **936 617/937 449 byte**
för normal/diagnos. Mätningen har egen kostnad i diagnosprofilen.

RAM-räknare/max/histogram mäter **G**: gap mellan handleranrop, **H**: tid inne
i `lv_timer_handler`, **F**: synkron `my_disp_flush` inklusive TFT-sändning.
Första okända entrygapet utelämnas. **M=0/1** betyder ej spelande/spelande;
**T=0/1** betyder ingen/aktiv bildmottagning vid provtillfället. T är parserns
aktuella flagga, inte en garanti att allt bildarbete är avslutat. Panel och
metadata lagras inte. Flushantal kan överstiga handlerantal.

Högst var 15:e sekund skickas en numerisk rad per aktiv M/T-grupp. Varje G/H/F
innehåller `count,max_us,b0,b1,b2,b3,b4,b5`. Bins är **≤1, ≤4, ≤16, ≤33, ≤66,
>66 ms**. Ingen per-frame-utskrift, text, URL eller credential ingår.

```text
DIAG_RENDER:M:1,T:0,G:count,max_us,b0,b1,b2,b3,b4,b5,H:count,max_us,b0,b1,b2,b3,b4,b5,F:count,max_us,b0,b1,b2,b3,b4,b5
```

Firmware persisterar eller laddar inte upp statistiken. Mottagande PC-verktyg
kan spara den. Nästa gap kan inkludera den glesa utskriftens kostnad; jämför
stabila faser/histogram, inte enstaka maxvärden. Se [Privacy](../PRIVACY.md).

## Verifiering

- Båda byggen PASS med befintlig Espressif32 6.12.0/Arduino 2.0.17,
  TFT_eSPI 2.5.43/LVGL 8.3.11, cirka 70/64 s. Ny lokal core/cache/build/libdeps;
  ingen SDK-installation eller ändring av gamla EBB-byggfiler.
- **38 publika projektpins** matchar fryst källa och arbetsyta; **3042** kopierade
  bibliotekspins verifierade och ursprungliga TFT/LVGL-filer bevarade.
- **Fem native labelprov PASS**: kompilerad aktuell helper/refresh/metadata,
  lång svensk titel/artist, tio tresekundersrepeats, äkta titel-/paus-/tidsbyte
  och DJ-färger. Repeats gav noll label-/färgsetteranrop. LVGL-räknaradaptrar
  användes, ingen verklig LVGL-animation/allocator/raster- eller TFT-mätning.
- **Sex native ackumulatorprov PASS**: histogramgränser, uint32-timeromslag,
  M/T-isolering, nested-anrop, 15 s-gräns och window-reset med bevarat entrygap.
- Ren slutkontroll: **368 funna/359 PASS/nio klassade SKIP/noll fel och noll
  blockerade operationer**; relevanta befintliga artwork/slot/touch/fontprov ingår.
- Root granskade källpins, image-huvud/DIO/storlek och DIAG-separering oberoende.
  Offline `image_info` godkände båda checksummorna/valideringshasharna.
  Ingen COM-port eller hårdvara användes; fysisk jämnhet är fortfarande oprövad.

Källmanifest-SHA:
`CC7A6035A793889DB02741EED4D5F079FFD8173FB980528CEB7CCD7440A97EB4`.
Byggkvitto-SHA:
`BAA69FCDA1E4A1F98E3FD974384E1A1B513641C5A3567D733E9A67D73C59FB21`.
Rootkvitto-SHA:
`535376189F78FD55FB81C5351E53A3AD81037494F88020ED3F958863322EABD7`.
Slutsvitens summary-/källmanifest-SHA:
`2E98A1CAC539D94971CA3B075578964E19DE766078FDF465E901BA9DC1D77B55` /
`1026F39D60DD51D6CFDC438AD6A5031FB9ADE0DA12A61B9EBD27D92EC5372105`.
Lokala bevis: `build/product-committee-2026-10-20/render-measurement-r2/` och
`quality-delivery/fw/check-kaoix9r2/`. R1 var en ofullständig förberedelse utan
byggning. Äldre källfrysningar/manifest är bevarade.

## Nästa steg – separat exakt flashgodkännande krävs

Efter Root-granskning och användarens godkännande för konkret diagnoshash kan
Lead stoppa C421 tillfälligt och använda en fristående COM-harness med syntetiskt
offentligt omslag/lång svensk titel och befintlig STATS-/metadatakadens. Håll
Spelaren öppen; låt start/överföring klinga av. Jämför flera 15-sekundersfönster
med stabil PLAYING respektive PAUSED, med/utan överföring och vid behov DJ,
samt synliga ryck/stale pixels. Återställ sedan exakt EBB/C421 enligt godkänd
plan. Inget flash-/mät-/återställningssteg är utfört av detta byggarbete.

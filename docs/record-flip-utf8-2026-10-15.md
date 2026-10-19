# Skivflip och svenska medietecken – 2026-10-15

## Status och exakt par

**Implementerat, byggverifierat, källfryst och visuellt godkänt i simulering.**
Ingen ny companion har startats/installerats och ingen firmware har flashats.
Ingen verklig profil, Spotify-trafik, API-takt, commit, push eller release
ändrades i detta uppdrag. Git-bas: **83cc460b6e3a651f862db9aff1577f40b683bac0**.
Arbetsytan är enbart `D:\DEV\Ai\Github\Bongo-Cat-Screen`.

**Installerat är fortfarande 17466/F406 med 5 s dagaktivt grundintervall.**
Det nya paret nedan behövs för den kompletta åäö-rättningen. F406 ska inte
beskrivas som UTF-8-/glyphprovat med den nya companionen. Den nya firmwaren
innehåller också det tidigare byggda seek-stödet, som **fortfarande inte är
flashat, skärmprovat eller fysiskt accepterat**. Befintlig seek-kandidat
57894EE0, installerade F406/17466 och äldre artifacts är bevarade.

| Ny kandidat, endast byggd | Sökväg relativt arbetsytan / bytes / SHA-256 |
| --- | --- |
| Firmwareapp | `.pio/candidates/record-flip-utf8-09305A29.bin`, **932736 byte** |
| Firmware SHA-256 | **`09305A29F96E689A4746FCE2464BD886DDF3ECF9B4739BB6083088C4C903E06A`** |
| Companion | `dist/companion-2026-10-15-record-flip-utf8-dev/BongoDeskSpotify.exe`, **19657256 byte** |
| Companion SHA-256 | **`0D397F89DCBC5C6B648517268A08B1D4E9DBEF23B7BAFD9B51816EBE77850ADD`** |
| Källa | `build/record-flip-2026-10-15/source-frozen/`, **153 bytekopierade filer** |
| Källmanifest | `build/record-flip-2026-10-15/source-frozen.json`, SHA **`890A4750FF16BC543B50A6778C0A06BA608A3554407899EBE9E4ABC2A9296A9A`** |
| Kandidatmanifest | `build/record-flip-2026-10-15/candidate.json`, SHA **`50993572BF14864D65888D157CA2B5260FA06B820DB3A36309966D2883C52CBC`** |
| Visuellt godkänt manifest | `visuals/record-flip-2026-10-15/manifest.json`, SHA **`F0AA9837CC2FA55F798E4D81FAD66FE39ABC8F64E41AAD6FCCB96EE3CA4E1BA3`** |

Drift använder fortsatt 230400 baud. Kandidaten är en appbild för kompatibel
layout vid `0x10000`; inga fullbilder, nya flashinstruktioner eller
flashgodkännanden har skapats i detta steg.

## Vad skivvändningen gör

Vid verkligt låtbyte vänds gammalt omslag till den befintliga generiska
vinylens utseende. Vid nytt komplett giltigt omslag vänds generisk vinyl
till omslaget. En normal full vändning är **280 ms**, med en tidsstyrd
höjdprofil i **20 ms-steg**: cirkel → tunn horisontell ellips/kant → rättvänd
ny sida. Ingen studs, extra planrotation eller kvarhängande väntanimation.

| Normal vändning | Bild |
| --- | --- |
| 0–120 ms | Utgående sida komprimeras lodrätt runt samma centrum |
| 140 ms | Två källpixlars kant, högst den generiska skivans 92 px bredd |
| 160–280 ms | Mottagande sida öppnas till full höjd |

Ordinarie rotationsvinkel fryses under vändningen. Den fortsätter sedan
naturligt med befintlig rotation endast när musik spelar; ett bildbyte
nollställer inte vinkeln. Både 172 px normal viewport och 144 px kompakt
Fokus-layout används med sina befintliga zoomvärden.

Snabba signaler coalescas i ett enda tillstånd, utan kö. Kommer komplett
omslag under utgående rörelse öppnas den senaste aktiva bilden från kanten.
Kommer ett nytt låtbyte under en inkommande rörelse avbryts den till
generisk vinyl. **Varje snabb signal får därför inte en egen full 280 ms-
animation.** Ett gammalt omslag kan inte återupplivas ur en animationskö.

Samma låts fullsynk/reconnect/cacheretry ger ingen ny vändning. Revisioner
för ändrade metadata och den befintliga `MEDIA_SEEK_CONTEXT`-slutmarkören
skiljer verkligt byte från upprepad synk; markören fångar även ändrad
låtnyckel med identisk titel/artist. Ingen companion-/protokolländring
behövdes för själva flippen. Textbuggen kräver companionändringen nedan.

DJ/menu/annan panel och faktisk ändring av kompakt Fokus-layout avslutar
en pågående vändning till senast beslutade slutläge. DJ visar sin egen
omritade canvas, och återkomst till Spelare visar rätt hel bild. Vid uteblivet
eller felaktigt omslag slutar skivan som vanlig generisk vinyl; ingen
animation väntar på nätet.

## Renderings- och buffertval

LVGL **8.3.11** har planrotation och gemensam zoom, men inte separat
vertikal bildzoom för denna rörelse. Lösningen använder därför en liten,
heltalsbaserad projektion i `media_record_flip.h` och vanlig `lv_img`-
visning. Den är lokal och tidsstyrd, utan animationsvänteslinga, ny tråd
eller nya beroenden. Högst en begränsad 112×112-pixelberäkning görs per nytt
steg. Missade steg hoppas över; de köas inte. Verklig ESP32-framebudget
och jämnhet är ännu inte uppmätta.

Alla tolkningar, LVGL-anrop och bildtillstånd ligger kvar på **core 1**.
Core 0:s UART-framing, art2-format, CRC, chunkordning och ACK-väg bevaras.
Komplett giltig bild byter omedelbart aktiv slot; ACK skickas innan någon
projektionsframe ritas. Det sker inget väntande på en animation i RX-vägen.

Projektionsytan är separat från de två transportbuffertarna. Generisk vinyl
skriver inte längre i inaktiv/mottagande art-slot. Animatören sparar ingen
pekare till ett gammalt omslag mellan frames: den läser endast aktuell
committad slot. Vid ny bild mitt i en flip släpps den gamla sidan innan
nästa BEGIN kan återanvända den gamla aktiva slotten. Ny DEFAULT eller
ändrad kontext avbryter en gammal ofärdig överföring. Felaktig legacy-RGB
ersätter inte heller en redan committad bild med ett trasigt mellanläge.

Källkontrollen gjordes mot den installerade LVGL-koden och
[LVGL:s bildfunktioner](https://docs.lvgl.io/8.3/widgets/core/img.html) samt
[canvas-/buffertkontrakt](https://docs.lvgl.io/8.3/widgets/core/canvas.html).

### Minne och OOM

Den första statiska 25088-byteytan kompilerade men fick **12720 byte
DRAM-segmentöverskridning vid länkning**. Den används inte i slutbygget.
Slutlösningen gör **ett enda försök** att allokera **25088 byte** intern
8-bitarsheap vid skärmens skapande. Ingen frame, metadata, panelväxling
eller resize gör nytt malloc-försök. Den rena tillståndshjälparen är 20 byte.

Vid misslyckad allokering sker direkta bildbyten utan flip eller vänteläge.
Generisk vinyl ritas då i **56×56** i den redan befintliga **64×64** DJ-
scratchytan, bara när DJ är dold. 3136 pixlar ryms i 4096; övriga pixlar
lämnas orörda. Dubbel zoom bevarar storleken med grövre raster. Innan DJ
visas fylls/ritas hela dess canvas om. LVGL läser och uppdaterar bilderna
seriellt på samma UI-core; dess displayflush använder separat drawbuffer.
Transportbuffertarna berörs inte heller i OOM-fallet.

| Slutbygge | Resultat |
| --- | --- |
| Firmwaremiljö | `esp32-024r-spotify-fastserial`, **PASS 80,680 s** |
| Separat byggmapp | `build/record-flip-2026-10-15/firmware/` |
| Statisk RAM | **112216/327680 byte**, +120 mot 83cc460/seek-källans 112096 |
| Bygg-flash | **931997/1966080 byte**, +2744 mot samma bas |
| Engångsheap för projektion | **25088 byte**, utöver ovanstående statiska tal |
| Byggvarningar | Befintliga TFT_WIDTH/TFT_HEIGHT-omdefinitioner kvar; inga slutbyggfel |

Äldre cirka 180 kB friheap är historik, inte ett löfte om sammanhängande
block eller ny minheap. Fysisk heapfragmentering, största block, minheap
och belastning under flip/art2/touch återstår att mäta.

## Åäö/ÅÄÖ genom verkliga kedjan

Buggen hade två orsaker: `_clean_media_text()` translittererade allt genom
NFKD→ASCII, och payloaden kodades som ASCII med ersättning. Firmwarefonterna
Montserrat 14/16 saknade samtidigt de sex svenska glyferna.

1. Snapshotens titel/artist normaliseras nu till **NFC**. Åäö/ÅÄÖ bevaras;
   dekomponerade svenska tecken sätts ihop korrekt. Övriga ännu ostödda
   tecken behåller tidigare ASCII-fallback.
2. Radbrytningar blir mellanslag, kontrolltecken tas bort, `|` blir `/`.
   Titel/artist begränsas fortsatt till 72 tecken. Med högst två UTF-8-byte
   per tillåtet tecken ryms metadata enkelt inom **256-byteframer**; längsta
   artist-/titelrad är högst 157 byte före LF. Numerik och kommandon bevaras.
3. Endast medietextpayloaden sänds som UTF-8. Art2/base64, numeriska fält,
   kommandon och trafiktakt ändras inte. Den riktiga C++-framer bevarar
   fragmenterade UTF-8-byte fram till komplett rad.
4. LVGL:s befintliga UTF-8-stöd används. Två små tillägg har sex 4bpp-glyfer
   vardera, härledda från befintliga Montserrat-bokstäver med ring/prickar.
   Samma baseline, storlek och advance behålls. ASCII/symboler faller tillbaka
   till originalfonten; ingen tung ny fontkedja införs.
5. De riktiga rullande titel-/artistetiketterna använder tilläggen, även i
   DJ/kompakt vy. Övriga panelers fonter och geometri ändras inte.

`tools/generate_media_swedish_font.py` reproducerar den nya headern utan
fontkonverterarinstallation. Visuella prov använder endast tillåtna **Dö
ung / Hov1**, åäöÅÄÖ och syntetiska omslag/texter.

## Körda prov och begränsningar

**186 upptäckta: 184 PASS, två befintliga C++ SKIP**, 27,388 s, noll fel och
noll externa anslutningsförsök. Profil/temp är isolerade under den nya
byggmappen. Python-nätspärren tillåter bara intern loopback för asyncio.

- **14 nya flipprov**: riktig C++-tillståndsmodell/projektion exekverad via
  befintlig fristående MSVC-DLL, utan CRT/SDK-reparation. Normal 280 ms,
  byte mitt i flip, senaste mål/slot, snabb avbrytning, inga dubblettflips,
  lika titel/ny kontext, DJ/panel/resize, millis-wrap, pixeldimensioner och
  kantbredd. Faktiska `activateMediaArtwork()`/`loadGenericVinyl()` körs med
  minimala LVGL/TX-adaptrar: ACK före frame, gammal slot får skrivas medan
  ny bild förblir korrekt. Faktisk engångsallokering körs mot tvingad OOM;
  reducerytans gränser, orörda canarypixlar och ingen retry kontrolleras.
- **Fyra nya textprov**: faktisk enginepayload→verklig C++-byteframer,
  NFC/NFD, åäöÅÄÖ, tidigare fallback, kontroller/radbrytningar, bytegräns,
  overflow/recovery, genererad glyphdata och riktiga fontkopplingar.
- Nytt prov kräver att slutpreviewmanifestets käll- och bildhashar matchar.
  Historiska previewprov är uttryckligt historiska och läser 83cc460-blobbar
  med LF/CRLF-hantering samt oförändrade pinnade fontfiler. Gamla frysta
  bilder/manifester är inte omskrivna. Övriga presentationsassertions kvar.
- Befintliga regressioner för API-budget, Retry, manuell read, kontroll/
  confirm, källbyte, omslag, seek, serialåteranslutning och Fokus passerar.
- `test_cpp_state_cache_and_ui_calls` och
  `test_cpp_actual_touch_handler_and_media_dispatch` är fortfarande **SKIP**
  p.g.a. ofullständig lokal MSVC/headers. De nya fristående provens framgång
  betyder inte att dessa två fulla adapters/touchkörprov har exekverats.
- Hela firmwaren inklusive riktiga LVGL-fonttyper/callbackkopplingar är
  kompilerad/länkad. Faktisk LVGL/TFT-rendering, fysisk UTF-8-mottagning och
  full touchdispatch har inte körts på ESP32 i detta steg.
- Ny companion byggd **30,886 s**. Skrivskyddad paketkontroll: **11 moduler,
  fyra resurser och Stockholm-tzdata** matchar källan. API-budget, bridge,
  Spotify-klient och standardkonfiguration är bytebevarade. Ingen EXE-start.
- **960 historiska filer** bevarade i bytes/SHA-256, inklusive äldre
  kandidatrapporter, kopior/manifester, previews, firmware och releases.
  Alla 153 nya snapshotkopior matchar aktuell fryst källa. `git diff --check`
  och UTF-8/whitespace kontrolleras vid slutöverlämningen.

## Granskningsbilder

[Nya underlag](../visuals/record-flip-2026-10-15/) innehåller normal/kompakt
flip, snabb följd, riktig musikpaus, DJ-, Fokus- och panelavbrott, OOM-
reserv, slutbilder, kontaktark, glyphark och lång rullande titel/artist.
Projektionsframes/tillstånd kommer från den verkliga C++-hjälparen och
glyphbilder från firmwarens verkliga bitmaps. Infokortet ritas rent med
aktuell geometri/färger. Cirkulär text använder verkligt 204 px-klipp och
tre mellanslagsglyfers kopieavstånd.

**UI har visuellt godkänt exakt F0AA9837…-manifestet ovan**, efter verifierade
8/8 källhashar och 20 outputhashar samt avkodade GIF-rutor/tidsstämplar.
Inga blockerande visuella avvikelser kvar. Rapid/OOM är avsiktligt avbrutna/
direkta förlopp enligt ovan. Simuleringen visar fryst nollgradig planvinkel
för läsbarhet; normal rotation styrs av den riktiga firmwarevägen.
20 ms i en GIF är inte uppmätt ESP32-fps eller garanti om skärmens jämnhet.

## Kort senare skärmprov – fortfarande väntande

Efter separat uttryckligt godkännande för det nya paret:

1. Kontrollera Dö ung/Hov1 och åäöÅÄÖ i kort/lång titel och artist, vid båda
   rullkanterna och omslag, i normal och kompakt vy.
2. Spelande och pausat: gammal→generisk→ny skiva, ingen extra planrotation,
   återupptagen rotation bara vid spelande. Saknat/felaktigt omslag lämnar
   generisk skiva utan väntanimation.
3. Snabba byten och omslag mitt i första flippen: endast senaste bild,
   korrekt ACK/art2, jämn touch och inga halvbilder eller tappad seriell data.
4. DJ in/ut, meny, Bongo, Fokus och ändrad kompakt layout mitt i flip;
   korrekt helt slutläge, intakta gester/tidslinje/Fokus-touch/progress.
5. Samma låts reconnect/reset/cache, sleep/resume/återsynkning och mörka
   timerväckningar: inga onödiga flips, kvarhängande bild eller ljusblixt.
6. Följ heap/minheap/största block och framekostnad under belastning. OOM-
   logik är hostprovad; ingen verklig lågminnessituation har framtvingats.

Seek behåller sin separata uppskjutna fysiska provstatus även om det nya
paret senare skulle installeras. Inga av ovanstående hårdvaruprov är gjorda.

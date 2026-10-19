# Snabb bild först, sedan mer detalj – 2026-10-19

**Nytt par 59FC2E33/EBB334A9 är endast byggt.** Installerat är fortfarande
**FD9D811B/C6EBAE4B vid 921600**. Den redan frysta, granskade **5556B647** är
bevarad exakt och är inte flashad. Lead valde att invänta denna kompletta
kandidat inför kombinerat runtimeprov. Code gör ingen installation/flashning.

## Källbedömning och vald lösning

Befintlig cache är 112×112 RGB888. Samma fulla ART2-format tog cirka 4,68 s
i det äldre C2-provet med två frames/write och 15 ms paus. Det är en rimlig
startpunkt för ungefär fem sekunder efter snabbilden, inte bevis för detta par.

5556:s ACK gäller mottagen staging. En omedelbar full-BEGIN kan därför
skriva över kompaktbilden före 870/1 070 ms eller nästa väntande rörelse.
En fast PC-väntan löser inte retarget/frame-gap säkert med två slotar.
Lead godkände därför en liten ny färsk kapabilitet och slotbekräftelse:

- `CAPS:MEDIA_ART2_REFINE:<challenge>:921600` annonseras bara med den befintliga
  kompakta profilen och live core-0-RX. Äldre format/defaultbaud bevaras.
- `MEDIA_ART2_SHOWN:<compact-id>:<challenge>` skickas en gång när frame-steget
  valt/pinnat kompakt-slot för aktuell kontext. Det betyder säker slotägare,
  **inte uppmätt synlighet på LCD**; även osynlig panel kan välja senaste slot.
- Companion registrerar jobbet före END/ACK/SHOWN. Båda svar krävs, oavsett
  ordning. Conn/epoch/färsk nonce, compact-id och originalcacheobjekt binds.
  Gammal signal med återanvänt id kan inte släppa en ny generation. Ny nonce
  pensionerar endast RX/notice; samma nonce bevarar staging och animation.
- Den befintliga enda statusutlösta omfrågan kräver nu bas+compact+refine för
  att hoppas över. Äldre kompaktpeer får högst en extra ofarlig fråga.

Samma sendertråd tar därefter ett enda valfritt full112-jobb från befintlig
cache. Det får uttryckligen fullformat och konservativ **2 frames/15 ms**,
även om FAST finns. Ingen extra API-/nätverkshämtning, tråd, timertråd,
växande bildkö eller stor MCU-buffer. Bildens befintliga två RGB565-slotar
används. Inaktiva mottagarsloten måste vara komplett och CRC-godkänd före byte.

Trackbyte eller nytt cacheobjekt på samma track avbryter refinement; även
generation/conn/cap-bortfall/stop invaliderar den. Ny coarse har företräde.
Valfritt arbete kan aldrig bli raw-fallback eller normal återkö. ACK-väntan
kontrollerar avbrott i 20 ms-intervall; OS/USB-write kan ha egna fördröjningar.
High-res får ingen retryloop. Vanliga coarse/raw/ART2-retries bevaras.
Saknad eller sent mottagen kapabilitet/slot-signal kan lämna det aktuella
omslaget i low-res; nästa normala omslagsjobb får ett nytt försök.
Vid fel-CRC eller avbruten/ofullständig överföring ligger korrekt low-res kvar.
Om endast ACK förloras kan korrekt fullbild redan vara vald på ESP32;
ingen rollback eller ny överföring startas av detta valfria jobb.

## Visning och kontur

Atomiskt byte behåller samma kontext, storlek, position, vinkel och rörelse-
klocka; ingen ny default, tass, flip eller tonarmsstart. UI rekommenderade
detta före en fade som skulle binda båda slotar och komplicera nya bilders
prioritet. Late art och 5556:s dolda framsideväxling är bevarade.

Första previewn upptäckte verklig opak-konturskillnad: bbox coarse
**[1,1,110,110]**, rak fullcache **[2,2,109,109]**. Den valfria fullpayloaden
behåller nu exakt coarse-masken genom att återanvända jobbets redan packade
compactbytes. Där endera bilden blir RGB565-chroma behålls coarse-pixeln;
övriga detaljpixlar kommer direkt från112cachen. Även nära grönt som
RGB(3,253,5) kvantiseras korrekt. Normal encoder/cache/fallback ändras inte.
Extra beredning är begränsad PC-data; inget nytt bildminne på ESP32.

## Verifiering och separat paket

**23 nya tester PASS. Relevant regression: 158 upptäckta, 156 PASS,
två kända MSVC-SDK-skip, noll fel/externa nätförsök.** Ingen bred helsuite.
Proven kör riktig sender, reader, native produktparser/CRC/slots/notification
och renderer: bägge svarordningar, saknad ACK/SHOWN, gamla nonce/id/epoch,
same-cache-revision, chunks/END/ACK-avbrott, stop/reconnect, dispatch-race,
timeout/CRC, prioriterad ny coarse, stats/touch mellan batcher, mask/bbox
normal/Fokus vid 0/37/90°, verklig detaljökning och oförändrad rörelse.

- Companion `dist/companion-2026-10-19-artwork-refinement-dev/BongoDeskSpotify.exe`,
  **19 662 092 byte**, SHA-256
  **59FC2E3323B1B0682069A29AD16460C2F9E960771506DA6BEE5F128721A83B3B**.
  Standard-spec; 12 inbäddade moduler/fyra resurser matchar slutkällan,
  seek saknas. Aldrig körd/installerad av Code.
- Firmware `.pio/candidates/artwork-refinement-2026-10-19-EBB334A9.bin`,
  **937 184 byte**, SHA-256
  **EBB334A926709E047DA1D930684C76D02DFA162332C508E775F062AE492E2FF3**.
  ELF **520A80BBE00A9E4751E1FE3FAAC1155AB71812A9F078F2A254F6FB679AAA82D1**.
  Separat kompakt80-build 74,490 s. RAM **112 448 byte** (+32), program
  **936 453 byte**; image-checksum/validation hash giltiga. Ingen flash.

## Preview, bevarande och fysisk provgräns

Slutlig r4: `visuals/artwork-refinement-2026-10-19/r4/index.html`, manifest
**4100679C21BB4CE2E080BBA014E8521A5AE02EC3E1A8CE03AAAC789B9AE0C915**.
27 källpins/16 outputs. Faktiska sender-paket spelas genom native parser,
CRC, SHOWN, slotval/state och projektion; syntetiskt tidigare granskat omslag
och samma riktiga cachekonvertering. Sex GIF/tidsserier visar normal/Fokus/
paus, fel-CRC och snabba dubbelbyten. 2 155 pixelord får ny detalj i exemplet,
med exakt bevarad opakmask. r4 korrigerar även enbart previewns pausade
positionsskript. r1/r2/r3 och deras källkopior bevaras; första appen C7B2A597
(19 661 483 byte) samt mellanappen 05489A2C finns separat i nya buildmappen.

Modellen antar 350 ms kompakt och **4 680 ms fulltransport**, hämtat från
tidigare observationer. Den ger slotval 880 ms och fullbild 5 600 ms,
**4 720 ms senare**. Detta är varken fysisk tidsmätning eller femsekunders-
garanti. Scriptad rotation/progress och PIL-kantpixlar kan skilja från TFT.
Lead har godkänt slutkälla och paket. UI har godkänt exakt r4-manifest:
skarpare detalj med oförändrad kontur/diameter/registrering, ingen ny halo,
flip/default eller extra tass; fortsatt tonarm/rotation/progress och stilla
bild/tid vid paus. Pausjämförelsen ändrar inga pixlar utanför skivan.
Fel-CRC behåller low och retarget/dubbelbyte visar inte gammal high igen.
Detta är snäv **hostacceptans**, inte uppmätt TFT-jämnhet eller tid.

Efter separat distributionsgodkännande: mät från första faktiskt synliga
bild till skärpning på stabil låt, kontrollera kontur/storlek/crop/rotation/
tonarm/progress, ingen ny tass/default, samt snabba byten före/under/efter
full-END. Prova Fokus/DJ/meny/gester/åäö, sleep/resume/återsynkning och Exit.
Fysisk tid, jämnhet och långdrift är väntande. Ingen COM/live-API/profil/
installation/flash/commit/push/release från Code. Spotify-felsökning är pausad.

## Slutliga bevis och överlämning

Efter Lead/UI-review är **189 källfiler frysta**, **75 Pythonfiler**
syntaxkontrollerade. **8 584 äldre filer** är bytebevarade utan avvikelser,
inklusive 5556/C3/C2-kandidater, rapporter, previews och frysningar.
Även r1/r2/r3 och deras källkopior samt båda mellanapparna är hashkontrollerade.
`git diff --check` passerar; endast tidigare LF→CRLF-varningar för
`src/media_art_v2.h` och `tests/test_focus_countdown.py` visas.

Ändrat: engine/codec, firmwareintegration i `bongo_cat_featured.inc`, 00/01/02
och sex berörda fixture-/testfiler. Nytt: `src/media_art_refinement.h`,
`tests/test_artwork_refinement.py`, `tools/artwork_refinement_candidate.py`,
`tools/artwork_refinement_visuals.py` samt denna rapport och separat
[överlämning](lead-handoff-2026-10-19-refinement.md). Full filförteckning
finns i scope-manifestet. `src/media_turntable.h`, API/auth/poll/config/GUI,
normal encoder och befintliga albumformat är bevarade.

SHA-256 under `build/artwork-refinement-2026-10-19/`:

| Fil | SHA-256 |
| --- | --- |
| `source-frozen.json` | `AA5668E97EEAE865C6048C53C2F1633F2C51AB18FE9AD56F0C3DAFA5A710F792` |
| `firmware-verification.json` | `D7AE0EFC258483988CF75B11C161A84CA530A6949FABB9AA6EF3F21DAE453A1D` |
| `package-verification.json` | `55C6D4D20F186B532CFBD6423847838DDDF476B3F914766A3BB8332AD5538039` |
| `scope-verification.json` | `DF5E45148238A61A2EFD6B11D55CD27EB2657EE16FDCDBC6D82DB0C3A1650322` |
| `candidate.json` | `024E827A2814918FAC1A1A336B6FB1EB48AA7D82CA29ABBCF04581E49E8CCC5F` |

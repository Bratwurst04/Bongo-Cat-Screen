# Bongo Cat – Project Context

## Projekt

Bongo Cat består av:

- Windows-appen **BongoDeskSpotify**
- ESP32 med **240×320 TFT**
- Seriell kommunikation, normalt **COM6**
- ESP32-firmware i `src/`
- Windows companion-app i `companion/`

## Grundprincip

Windows-datorn ska i möjligaste mån skicka **enkla events och state-förändringar**.

Animationer, visuella effekter, timers och liknande ska i första hand köras lokalt på ESP32.

Undvik kontinuerlig högfrekvent serialtrafik.

Var särskilt försiktig medan Spotify-albumomslag överförs över serial.

## Viktiga filer

- `src/bongo_cat_featured.inc` – huvuddelen av ESP32-funktionaliteten
- `src/main.cpp` – entry point
- `animations_sprites.h` – sprite-definitioner och animation states
- `companion/engine.py` – Windows-motor
- `companion/spotify_api.py` – Spotify
- `companion/settings.ps1` – Windows-inställningar
- `companion/config.py` – konfiguration

## Befintlig funktionalitet som ska bevaras

- Bongo Cat-animationer
- Spotify-information
- Albumomslag
- Spotify-progress
- Spotify/DJ-skärm
- Touch:
  - tap på Bongo-skärmen = bonk
  - tap på mediasidan = play/pause; dubbeltryck = nästa; tre tryck = föregående
  - sidsvep på mediasidan = föregående/nästa; svep ned = omslag/DJ
  - långtryck på båda skärmarna = öppna/stäng gemensam panelmeny
- Stabil seriell kommunikation
- Systemstatistik: CPU, RAM, WPM, tid
- ESP32-diagnostik
- Spotify API-diagnostik
- ESP32 heap/min heap
- valfri ESP32 CPU-estimering
- idle-, sleep-, typing-, streak-, blink- och ear-twitch-animationer

Gör inte stora omskrivningar om de inte uttryckligen efterfrågas.

Bygg och verifiera firmware före flashning.

ESP32 behöver normalt sättas manuellt i bootläge innan flashning.

## Grafik

Projektets visuella export ligger under `visuals/`.

### När användaren säger:

- **"visa bilderna"**
- **"kolla bilderna"**
- **"hur ser det ut nu?"**
- **"utgå från bilderna"**
- **"jag vill ha bilderna"**

ska detta tolkas som:

1. Läs/visa `visuals/contact_sheet_composed.png`
2. Läs/visa `visuals/contact_sheet_sprites.png` om individuella lager är relevanta.
3. Använd `visuals/manifest.json` för namn, dimensioner och teknisk information.
4. Öppna enskilda filer i `visuals/composed/` eller `visuals/sprites/` vid behov.

Fråga inte användaren vilka bilder som avses om sammanhanget tydligt gäller Bongo Cat.

`contact_sheet_composed.png` är förstahandskällan för hur de befintliga Bongo-animationerna faktiskt ser ut.

### Nuvarande spritearkitektur

Bongo Cat bygger på 64×64 sprites i `LV_IMG_CF_RGB565A8`.

De kombineras i lager:

1. BODY
2. FACE
3. TABLE
4. PAWS
5. EFFECTS

ESP32 visar sedan den komponerade 64×64-bilden i 4× förstoring, alltså ungefär 256×256, utan antialiasing för att behålla pixelstilen.

## Arbetsprincip framåt

Innan en ny visuell feature föreslås:

1. Kontrollera befintlig firmware.
2. Kontrollera bilderna i `visuals/`.
3. Kontrollera om motsvarande funktion redan finns.
4. Förbättra befintlig implementation hellre än att skapa parallella system.

Nästa fokusområde är ESP32-skärmen och UI:t.

Inställningsfönstret på Windows ska inte byggas om utan ett konkret behov.

## Aktuellt fokus

Den gemensamma panelmenyn för Bongo och Spelare är implementerad. Menyn öppnas
med långtryck från båda skärmarna och behåller de befintliga mediagesterna när
den är stängd. Råtouchens träffytor behöver fortfarande dokumenterad kontroll
på den fysiska skärmen.

Den aktuella panelmenyversionens kompletta flashbild och kontrollsumma finns i
`release/`. `README.md` beskriver flashning från adress `0x0` och skiljer den
från appbinären som byggs och laddas vid `0x10000`.

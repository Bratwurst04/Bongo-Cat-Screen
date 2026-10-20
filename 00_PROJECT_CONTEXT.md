# Bongo Cat – Project Context

## Aktuellt 2026-10-20 – B7019579 installerad via Startmenyn och snävt accepterad

Installerat är nu **B7019579/EBB334A9 vid 921600**, efter användarens
appgodkännande och Leads verifierade appbyte. Den befintliga Startmeny-
genvägen startade rätt kanonisk EXE. Firmware skrevs inte. Användaren
bekräftade snabb bild och senare skärpning utan extra flip/hopp: **”Ja, det fungerar”**.
Uppstart kompakt READY→ACK 789 ms; senare sex 431–475 ms. Full SLOT→ACK
var 4 682–4 795 ms. Det är transport/slotmått, inga titel- eller LCD-tider.
Alla explicita caps kom; fysisk partial-inference och sleep/resume är
fortfarande oprövade. Se [separat driftrapport](docs/capability-partial-runtime-2026-10-20.md).
Den stående rutinen i [CHAT_ROLES](CHAT_ROLES.md) håller samma Windows-app
uppdaterad vid våra färdiga appuppgifter. Äldre avsnitt och frysta bevis bevaras.


## Aktuellt 2026-10-20 – separat app återhämtar partiella cap-svar

Installerat är fortsatt **94145746/EBB334A9 vid 921600**. Ny companion
**B7019579**, 19 664 148 byte, är byggd/paketkontrollerad, **inte körd eller
installerad**. Appens fullformatslåsning har reproducerats med bas+REFINE
utan COMPACT. Färska bas+REFINE för samma connection/epoch/nonce kan nu
bekräfta firmwarekontraktets kompaktstöd. Fysiska radbortfallet är obevisat.
12 nya PASS; 120 relevanta PASS/ett avsiktligt foto-SKIP. Inga nya frågor,
ny burst, firmwareändring eller release. Fysisk återhämtning väntar; ingen
LCD-/ensekundsgaranti. Se [underlag och provgränser](docs/capability-partial-2026-10-20.md).
Äldre statusavsnitt och frysta bevis bevaras som historik.


## Aktuellt 2026-10-19 – beskärningsapp installerad och snävt skärmprovad

Installerat är **94145746/EBB334A9 vid 921600**, efter exakt appgodkännande
och Leads verifierade appbyte. Firmware skrevs inte. Användaren godkände
Whoopty utan Spotify-remsa och skärpning utan hopp: **”Japp ser bra ut”**.
Jämförelsen med redan korrekt omslag är **osäker**, inte accepterad.
Första kompakta READY→ACK var 1 410 ms; refine kom efter ACK/resend och
ingen fullbild finns i uppstartsbaslinjen. Senare anonymt låtbyte gav
kompakt 444 ms och SLOT→full-ACK 4 748 ms på första försöket. Inga titel-
eller LCD-tider tillskrivs detta. Se [driftrapporten](docs/artwork-crop-runtime-2026-10-19.md).
Äldre statusavsnitt och frysta byggbevis bevaras som historik.


## Aktuellt 2026-10-19 – selektiv Spotify-beskärning endast i byggd app

Installerat lämnas **59FC2E33/EBB334A9 vid 921600**. Ny separat companion
**94145746**, 19 664 430 byte, är byggd/arkivverifierad men inte startad eller
installerad. Endast säkert igenkänd transparent Windows Spotify SMTC-ram
beskärs före RGB; referensen blir exakt 234×234 utan andra 6 %-inset.
API/andra spelare och icke-match behåller gammal bildkedja byteidentiskt.
8 nya/165 relevanta PASS; käll-/hostpreview är ingen fysisk TFT-acceptans.
Firmware är exakt EBB utan ny byggning/flash. Se
[beskärningsunderlaget](docs/artwork-crop-2026-10-19.md).
Alla äldre avsnitt och frysta bevis bevaras som historik.


## Aktuellt 2026-10-19 – progressivt omslag installerat och skärmprovat

Installerat är nu **59FC2E33/EBB334A9 vid 921600**, efter exakt godkännande
och Leads verifierade byte/flash. Användaren: **”Japp det ser asbra ut nu.”**
Det gäller snabb bild, senare skärpning utan ny flip/hopp och gammalt omslag
kvar till flipens mitt. Kompakt READY→ACK var 626/616 ms på första försöket;
tre SLOT→full-ACK var 4 749/4 797/4 700 ms. Detta är inte LCD-tidsmätning.
Legacy-uppstart tog 9 276 ms och ett kompaktjobb med retry 9 553 ms.
Engångs-CAPS-resend och färsk bas/compact/refine observerades. Ingen generell
under-en-sekunds-, rapid-skip-, Fokus/DJ-, sleep- eller långdriftsacceptans.
Se [separat driftresultat](docs/artwork-refinement-runtime-2026-10-19.md).
Alla äldre avsnitt, byggbevis och handoff nedan bevaras som historik.

## Aktuellt 2026-10-19 – kompakt först, senare detalj från samma cache

Installerat är fortsatt **FD9D811B/C6EBAE4B vid 921600**. Användaren vill få
skarpare omslag ungefär fem sekunder efter snabbilden, utan ny flip eller
ändrad storlek. Lead valde att invänta en komplett separat kandidat.
Nytt par **59FC2E33/EBB334A9** är byggt, **inte installerat eller flashat**.
Den tidigare granskade **5556B647** är exakt bevarad, också endast byggd.

Efter kompakt-ACK och färsk challenge-/id-bunden bekräftelse på vald bildslot
kan samma sender skicka ett enda konservativt full112-omslag ur befintlig
cache. Synlig low-res hålls kvar under mottagningen. Atomiskt detaljbyte
bevarar exakt coarse-mask; ingen ny flip/default/API-hämtning eller MCU-buffer.
Ny låt/cache/generation/stop avbryter refinement även under ACK-väntan.
156 relevanta PASS/två kända SDK-skip; r4 är godkänd av Lead/UI som hostpreview.
Modellens cirka 4,72 s från slotval till fullbild är **inte fysisk mätning**.
Se [byggunderlag och provgränser](docs/artwork-refinement-2026-10-19.md).
Äldre daterade statusar nedan är historiska bevis.

## Aktuellt 2026-10-18 – C3 installerad; nästa firmware håller kvar gammalt omslag

Installerat är **companion FD9D811B / firmware C6EBAE4B vid 921600**.
[C3-driftprovet](docs/capability-startup-runtime-2026-10-18.md) bekräftar kompakt
12 800-byteformat och tre lyckade första försök: 1 164 ms vid appstart,
374/351 ms vid två låtbyten. Användaren bekräftade snabbhet och bildkvalitet.
Ingen fallback-resend loggades; fysisk fallback/sleep/långdrift är inte bevisad.
Äldre bygg-/C2-rapporter nedan bevaras som historiska underlag.

Ny separat firmware **5556B647**, **endast byggd**, håller kvar visat omslag
till flipens kant (870 ms) eller helt ur bild (1 070 ms). De befintliga två
RGB565-slotarna används för visning/staging; tidig ACK kvitterar mottagen
CRC, inte visning. En ersättbar senaste identitet kan vänta på nästa dolda
brytpunkt. Ingen companionändring eller runtimeåtgärd ingår.
Förhandsvisning/källgranskning och fysisk provning skiljs åt; flash får ske
tidigast i morgon efter användarens godkännande. Se
[byggunderlaget](docs/turntable-face-2026-10-18.md).

## Aktuellt 2026-10-18 – C3-app byggd för tappad startkapabilitet

Installerat är **companion 356A5EC0 / firmware C6EBAE4B vid 921600**.
[C2-rapporten](docs/artwork-compact80-runtime-2026-10-18.md) visar endast
uppstart: kontakt men ingen loggad kapabilitet eller omslagsmätning till
22:45:01. Ett senare reset-/musikprov gav bas-ART2 men ingen kompaktkapabilitet;
två fullformatsomslag fick ACK efter 4,682/4,680 s. Det är inget kompaktfartprov;
se [separat uppföljning](docs/artwork-compact80-post-reset-2026-10-18.md).
Ny **C3-app FD9D811B** är byggd, **inte körd eller installerad**, och återanvänder
exakt C6-firmware. Den kan fråga en gång till med samma challenge efter giltig
status för aktuell conn/epoch. Hela bas+kompakt-tillståndet krävs för att hoppa
över omsändningen. Inga nya trådar, API-anrop eller periodiska prober införs.
Detta garanterar inte kompaktformat för ett första omslag som redan hunnit starta
eller att den saknade kompaktraden i det senare C2-provet återhämtas.
Se [C3-underlaget](docs/capability-startup-2026-10-18.md).
Äldre daterade avsnitt nedan är historiska bygg-/föreflashuppgifter.

## Aktuellt 2026-10-18 – kompakt omslag endast i ny byggd kandidat

Installerat är **445D72A0 / 860896DB vid 921600**, med underkänt fartprov
enligt [driftrapporten](docs/artwork-fast921600-runtime-2026-10-18.md).
Nytt separat par **356A5EC0 / C6EBAE4B** är byggt, **inte installerat/flashat**.
80×80 RGB565 ger 12 800 byte/100 chunks och skalas upp i befintlig inaktiv
112×112-slot efter CRC. Cache/API och utgående bildstorlek bevaras.
Profilen `esp32-024r-spotify-compact80` har egen färsk codec-kapabilitet;
den annonserar inte den äldre underkända FAST-tieren. Default 230400 och
flash 115200 är oförändrade. UI har godkänt stillbildsjämförelsen med väntad
detaljförlust. **Ensekundsmålet är oprövat för det nya paret.**
Se [kompaktrapporten](docs/artwork-compact80-2026-10-18.md).
Äldre avsnitt och frysta C/B/627-bevis bevaras; inga runtimeåtgärder från Code.

## Aktuellt 2026-10-18 – 921600 installerat, fartprovet underkänt

Installerat är nu **companion 445D72A0 / firmware 860896DB**, faktisk baud
**921600**, efter användarens uttryckliga godkännande och Leads installation/
appflash. Kanonisk appplats, Run-post och genvägar bevaras. Kodens default
är fortfarande 230400 och flash 115200. B:s tjockare arm ingår.
**Ensekundsmålet ART_READY→ACK är underkänt**: 703 ms snabb sändning gav
ett lyckat omslag på 1652 ms; art2_decode/art2_line avvisade andra försök,
och ett omslag tog 12344 ms med konservativ retry. Användaren rapporterade
”Nope de tar lång tid för vissa, en tog 11 sekunder typ.” Orsaken är inte
fastställd; kort sändtid bevisar inte snabb mottagarcommit.
Se [fryst driftresultat](docs/artwork-fast921600-runtime-2026-10-18.md).
[Byggrapporten](docs/artwork-fast921600-2026-10-18.md) är oförändrat
föreflashbevis. Spotify-felsökning/API-budget/auth ändras inte. Äldre
daterade statusar nedan är historik.

## Aktuellt 2026-10-18 – kattarm/tempo flashad och snävt skärmprovad

Spotify-felsökningen är pausad. Användaren avböjde flash av 3606F2E0 och
beställde en synlig kattarm samt långsammare lyft och nedläggning.
Firmware **627E6B93** har sammanhängande vit arm ut genom vänsterkanten,
greppaus och egna mjuka rörelsefaser (1,88 s normalt / 2,38 s komplett byte).
Efter användarens ”Flasha” skrev Lead den vid `0x10000` med verifierad
55669C87-backup; esptool verifierade skrivningen. Installerat par är nu
**companion 68721143 / firmware 627E6B93**. Oförändrad companion startades
om; första serieanslutningen misslyckades och försök två lyckades.
Resync och två omslag med art2-ACK är bekräftade. Användaren svarade
**”Ja. Armen kan bli lite tjockare”** på prov av ansluten vit kattarm,
lyft/nedläggning och tonarm play/pause. Det är snäv kvalitativ acceptans;
sällsynt komplett byte, Fokus, full touch och långdrift väntar. Önskemålet
om lite tjockare vit underarm finns nu i separat byggd kandidat **9961C753**,
**inte flashad eller fysiskt provad**; installerad firmware är fortsatt 627E6B93.
Se [armbreddsrapporten](docs/turntable-arm-width-2026-10-18.md).
Se [driftrapporten](docs/turntable-arm-tempo-runtime-2026-10-18.md).
[Byggrapporten](docs/turntable-arm-tempo-2026-10-18.md) beskriver föreflashläget
och bevaras som historiskt underlag.
Föregående 3606F2E0 och [dess rapport](docs/turntable-paw-2026-10-18.md)
är bevarade oförändrade.
Ingen companionbuild, profiländring eller release ingår. Äldre daterade
uppgifter nedan är historik; nya driftobservationer innebär ingen Spotifyfix.

## Aktuellt beslut 2026-10-16

Användaren har avbrutit seek och beställt att funktionen tas bort. Aktuell
arbetskälla återgår till vanliga mediegester; skivflip, åäö och neutral
låtidentitet bevaras. Installerat par är fortfarande **26A0FAF0 / C7E594B4**
tills Lead byter det. Nytt par och fysisk provstatus redovisas i
[borttagningsrapporten](docs/seek-removal-2026-10-16.md).
Äldre daterade uppgifter nedan är historik.

## Aktuellt underlag 2026-10-15

Installerat utvecklingspar är companion **17466EBF / firmware F406C485**,
med fortsatt **5 s grundintervall** för känd aktiv API-uppspelning dagtid.
Automatisk mobilföljning med rätt låttext/omslag och jämnhet är kvalitativt
godkänd; ingen separat uppmätt mobilhandlingstid eller end-to-end-latens.
Budget/Retry/natt/idle kan ge längre intervall. 3 s är endast analyserat;
användarbeslutet är att behålla 5 s.

**Seek-firmware 57894EE0 är byggd men inte flashad, ännu inte skärmprovad
eller fysiskt accepterad.** Aktuell arbetskälla och installerad firmware
ska hållas isär. Långdrift och sleep/resume med nuvarande companion väntar.
Se [daterade driftbevis](docs/api-budget-runtime-2026-10-15.md) och
[Lead-överlämning](docs/lead-handoff-2026-10-15.md) för exakta hashar,
roller och testat/väntande. Äldre daterade uppgifter nedan är historik;
app-v1.3 är senast publicerade release, utan ny release i detta steg.

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

Sedan 2026-10-11 är adaptiv Spotify Connect-pollning beställd: aktiv musik
ska följa API-pacingens minimum (0,5 s som lokal undre gräns) och backa vid
Spotify-begränsningar. En separat companionkandidat är byggd och testad i
isolering samt installerad och driftprovad av Lead. Användaren bekräftar
snabba mobilbyten och jämn skiva; exakt ändringslatens är omätt. Det gamla fasta Connect-
intervallet är avvecklat i källan utan att skriva om befintliga profiler.
Sparad Retry-After och kvotåterhämtning finns kvar. Publicerad app-v1.3,
ESP32-firmware och serialtrafik är oförändrade. Detaljer finns i
`01_CURRENT_STATE.md` och `companion/README.md`. UI-proven nedan är historik.

Sedan 2026-10-07 är en UI-ombyggnad av Windows-companionen uttryckligen
beställd: matcha skärmens stil och förbättra informationsstrukturen. Det
uppdraget ersätter de äldre begränsningarna för inställningsfönstret ovan.
Den aktiva WinForms-vägen `companion/settings.ps1` är nu ombyggd, granskad
med Lead och installerad efter användarens godkännande. Användaren har öppnat
vyn via tray-ikonen, provat sidbyte och avancerade inställningar samt godkänt
utseendet. Sparning har verifierats med omedelbar återläsning i motorn och
Connect är återställt till 15 s. Motor och tvåkärnig firmware är oförändrade;
detaljer och provens begränsningar finns i `01_CURRENT_STATE.md`. Nedan följer
den tidigare Fokus- och firmwarekontexten.

Källkoden har en gemensam panelmeny för Bongo, Spelare och den lokala
Fokus-timern. Menyn öppnas med långtryck från alla tre paneler och behåller
de befintliga mediagesterna när den är stängd. Tidigare lokalt flashad Fokus v1
fick begränsad fysisk kontroll, inklusive en kort observerad LED-blinkning.
Fokus v2 med valbara tider och automatisk paus är nu lokalt flashad som app vid
`0x10000`. Användaren har bekräftat val och sparning av 5/1 minuter, ett
kvalitativt 5+1-pass, att 5/1 finns kvar efter fysisk reset och efter ett
observerat companion-bortfall med släckning/väckning samt fungerande panelbyte,
mediegester, DJ och albumomslag. Exakta signal- och väcktider samt faktisk
strömförbrukning i deep sleep återstår före en eventuell release.

App-v1.3 är paketerad efter användarens releasebeställning med provad
tvåkärnig firmware, snabbare Spelare och det nya companion-UI:t. Drift är
230400 baud och flashning 115200; befintliga profiler migreras inte automatiskt.
Companionens installations-/anslutningsprov är godkänt; Lead sköter
publiceringen. App-v1.2 och äldre deep sleep-/panelmenyreleaser är bevarade;
se `01_CURRENT_STATE.md`
och `release/app-v1.3-verification.md` för aktuell verifieringsnivå.
`README.md` beskriver flashning från adress `0x0` och skiljer den från
appbinären som byggs och laddas vid `0x10000`.

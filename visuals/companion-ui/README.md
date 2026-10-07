# Companion UI · 2026-10-07

En genomförd, granskad och installerad UI med mörka Player/Fokus-ytor (`080A0C`, `101419`, `15191E`), grön accent (`1ED760`), Segoe UI och den befintliga pixelkatten. Amber används för väntan och fördröjd kontakt; fel har både text och fältmarkering. Färgerna ändrar inte skärmens lokala temaval. Bilderna här visar isolerade exempeldata; det verkliga Windows-provet beskrivs separat nedan.

## Struktur och inventering

Den aktiva öppningsvägen är tray → `settings.ps1` → WinForms. `gui.py` är den äldre Tkinter-vägen. Den nya presentationen ligger i `settings-view.ps1`, som laddas av samma entry point och paketeras i ordinarie spec tillsammans med kattbilden.

| Del | Befintlig funktion som visas |
| --- | --- |
| Översikt | Seriell kontakt, aktuell Spotify-källa, faktisk väntan/återhämtning och kompakt datorstatistik |
| Inställningar · Windows | Starta vid Windows-inloggning |
| Inställningar · Connect | Uppdateringsintervall 10–120 s, synligt direkt |
| Inställningar · avancerat | Snabbast tillåtet, vanlig API-gräns, API-gräns vid paus och omslagshämtning 1–5 försök; stängt från början |
| Diagnostik · Spotify | Totalt registrerade 429 med historikens begränsning, tre tidsfönster, adaptiv/säker/effektiv takt, senaste ändring och verkliga anrop |
| Diagnostik · skärmen | Kontaktens ålder, heap/min heap, eventuell PSRAM, valfri grov CPU-mätning |
| Diagnostik · åtgärder | Återställ inlärd API-gräns och slå på/av ESP32 CPU-mätning |

Spara och Ångra gäller de sex vanliga inställningarna. Ctrl+S sparar. Escape/stängning erbjuder spara, kasta eller avbryt vid osparade ändringar. Valideringsfel öppnar rätt sida, markerar och fokuserar fältet utan att skriva filen. En ny läsning före sparning bevarar andra inställningar och externa ändringar. Vanlig API-gräns valideras även mot den befintliga maxgränsen (normalt 30 s), så motorn inte avvisar ett nyss sparat värde.

Efter gemensam granskning med Lead är vardagsvyerna förenklade. Avancerade inställningar öppnas med en vanlig tangentbordsvänlig knapp som visar öppet/stängt. Döljning bevarar inmatade värden; ett fel i ett dolt fält öppnar sektionen och fokuserar rätt fält. Inmatningsfält presenterar decimaler på svenska utan att ändra JSON-värdena. Beräkningen av frågor per dygn ligger i fördjupningen. Normal Spotify-status beskriver källan med enkel text; BongoDesks egna resurser ligger i Diagnostik. Spara/Ångra visas på Inställningar och på andra sidor när värden är osparade. Den dolda sparraden tar inget utrymme och lämnar inte tangentbordsfokus på en dold kontroll. Diagnostikåtgärdernas besked visas lokalt vid respektive knapp, även utan sparrad.

Diagnostikåtgärder ändras direkt och är märkta som sådana. CPU-åtgärden väntar på skärmens rapport och visar utebliven bekräftelse efter 15 s. Återställning har en konkret bekräftelsetext och kan inte använda osparade värden. Retry-After kringgås inte.

Status äldre än 15 s visas som föråldrad och tidigare resursvärden döljs. Skärmtelemetri äldre än 20 s visas som fördröjd; CPU-åtgärden kräver färsk kontakt. Ingen sömnindikator, låttitel, uppspelningsknapp, temaändring eller kontoanslutning har hittats på: dessa saknas i denna statusvy eller hanteras redan på annan plats. Lokal Windows-Spotify visas fortfarande när Connect väntar på API-gränsen.

## Förhandsbilder

- `concept.png`: ritad visuell riktning från början av arbetet.
- `contact_sheet.png`: samlad granskning av sex vyer.
- `overview.png`, `settings.png`, `settings-advanced.png`, `diagnostics.png`, `diagnostics-screen.png`: den faktiska WinForms-layouten med isolerade exempeldata.
- Övriga bilder visar valideringsfel, Connect-väntan, lokal Spotify med API-väntan, tappad/föråldrad status, lång diagnostik, minsta fönster och 150 % layoutstress.
- `manifest.json`: bildstorlekar, kontrollsummor och källfiler. Exemplens värden och 429-historik är inte mätningar från installerad companion.
- `comparison-overview.png` och `comparison-settings.png`: före/efter den gemensamma förfiningen med Lead. `before/` bevarar första UI-passets två native vyer (kandidat `EC064E26…`).

## Verifiering med isolerade exempeldata

546 isolerade UI-kontroller (inklusive text/layoutkontroller), befintligt PowerShell-diagnostikprov och 58 Python-tester passerade under UI-arbetet. PyInstaller byggde `dist/companion-2026-10-07-ui-refined-dev/BongoDeskSpotify.exe`, 19 299 592 byte, SHA-256 `18465D92AA67E23F09FF0B3B1636D6CD7840A8B1B3B7C90D35D185B7A50D445E`. Settings-skripten, kattbilden och standardkonfigurationen i EXE:n är byteidentiska med källorna. Denna frysta EXE är nu installerad och grundprovad enligt nästa avsnitt.

`tests/test_settings_ui.ps1` skapar endast egen konfiguration och status under `build/ui-test`. Native kontroller renderas utan synligt fönster eller motor. Provet kontrollerar svenska decimaler, fältgränser, konfigurationsbevarande, sparning, ångra, stängningens tre val, valideringsfokus, tangentbordsordning, CPU-begäran/bekräftelse, lokal/Connect-status, lång text och layout vid 960×740 respektive 824×611 klientyta. Layoutstress med 150 % förstorar både typsnitt och kontrollgeometri; det är inte ett faktiskt byte mellan DPI-skärmar. Fönstret anpassas vid öppning till skärmens arbetsyta och har rullning vid behov. Fokus och text har granskats i genererade native bilder.

Förfiningspasset kontrollerar särskilt hopfällning/expansion, fel i dolt fält, osparade värden vid sidbyte, fokus efter att sparraden döljs, åtgärdsbesked utan sparrad samt normal/minsta storlek och 150 % layoutstress. Python-/motorkoden har inte ändrats sedan de tidigare 58 godkända testerna.

## Installation och verkligt Windows-prov

Efter användarens ”Ser bra ut” installerade Lead den frysta EXE:n på `%LOCALAPPDATA%/BongoDesk/BongoDeskSpotify.exe` och verifierade samma storlek och SHA-256 som ovan. Föregående `41BE575E…`-EXE sparades med verifierad hash som `BongoDeskSpotify.backup-20261007-ui-refined-41BE575E.exe`; konfigurationen sparades som `%APPDATA%/BongoCat/config.pre-ui-refined-20261007.json`. Konfiguration, credentials och Windows Run-post var oförändrade vid själva installationen. Start med `--startup` gav två normala processer kl. 11:19:02/04 (Stockholm), seriell anslutning på första försöket kl. 11:19:06 och art2-handskakning kl. 11:19:10. Färsk status visade ansluten ESP32 vid 230400 baud, cirka 182 516 byte ledigt heapminne samt Spotify redo, källa `spotify_api` och effektiv Connect-takt 15 s.

Användaren öppnade den paketerade vyn från kattens tray-ikon, bytte sidor, öppnade/stängde Avancerat och sade ”Japp ser bra ut”. Det är en kvalitativ visuell kontroll av den verkliga Windows-vyn. Connect ändrades till 20 s och sparades; Lead läste både sparat `spotify.api_only_poll_interval_seconds=20` och körande `media.effective_poll_interval_seconds=20.0`, med fortsatt färsk ESP32-kontakt. Sparning och motoråterläsning utan omstart är därmed verifierade.

Användaren återställde därefter 15 s, sparade och rapporterade ”15s nu” efter begärd återöppning. Lead bekräftade slutligen sparat 15 och effektivt 15,0 s, Spotify redo och ESP32 ansluten med statusålder cirka 1,13 s. De fem Spotify-värden som UI:t hanterar är semantiskt återställda, Windows-start är bevarad och all övrig konfiguration är identisk som JSON. Sparning kan lägga till tidigare implicita standardfält; konfigurationen påstås inte vara byteidentisk efter sparprovet. Återöppningen är användarrapporterad och är ingen separat tangentbords- eller tidsmätning.

Ett naturligt runtime-resultat från installerad `18465D92…` visar `MEDIA_TRACK seq1` och `ART_READY` för 37 632 byte, försök 1, kl. 11:25:42. `ART_SENT duration_ms=5000 protocol=art2 frames_per_write=2` loggades kl. 11:25:47.956 och lyckad `ART_ACK` kl. 11:25:47.963, 7 ms senare. Det är en lyckad första överföring utan extra provocerat prov; ingen separat visuell omslagsbedömning gjordes i UI-provet.

Faktisk DPI/monitorväxling, skärmläsare, mänsklig tangentbordsgenomgång och diagnostikåtgärdernas hårdvarubesked är inte separat provade. De begränsningarna skapar inte automatiskt nya releasekrav. Firmware `6A5366C1…`, motor, serialprotokoll, Spotify-pacing, tokens och autostartkod är oförändrade. Ingen push, merge eller release har gjorts.

Kör om förhandsbilderna från projektroten:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test_settings_ui.ps1 -PreviewDirectory "$PWD/visuals/companion-ui"
python tools/export_companion_ui.py
```

Ingen uppgift behöver skickas till Code 2 för denna kandidat. En uttrycklig firmwarestatus för sömn/väckning är ett separat möjligt framtida arbete; det är inte nödvändigt för denna UI-ombyggnad.

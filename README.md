# Bongo Cat för ESP32-024R

Firmware för en ESP32-024R med 240×320 ILI9341-pekskärm och en Windows
companion som skickar tid, systemvärden, mediastatus och albumomslag via serial.
ESP32 visar Bongo-animationer, en gemensam panelmeny och en mediasida med
omslag, vinyl och DJ-katt.

> [!Important]
> Vibe-coded project made by me

## Aktuell nedladdningsbar firmware

Använd [BongoDesk-deep-sleep-2026-09-30-full-0x0.bin](release/BongoDesk-deep-sleep-2026-09-30-full-0x0.bin)
för en komplett flashning från adress `0x0`. Tillhörande kontrollsumma finns i
[.sha256-filen](release/BongoDesk-deep-sleep-2026-09-30-full-0x0.sha256):

```text
SHA-256  7908115A4FD4D25E78E7BB46189DE57D8C044C63179AB9DD9D7E5C5CAC03CD6C
```

Bilden innehåller bootloader vid `0x1000`, partitionstabell vid `0x8000`,
startdata (`boot_app0`) vid `0xe000` och appen vid `0x10000`. Appen är
byte-identisk med utvecklingsversionen som laddades till användarens ESP32
den 2026-09-29: SHA-256
`AF51B963A5A3D8240D1DAD577D4DA3A9B5A94D930EEB02EA8E5C6D0329AF9E8C`.
Den sammanslagna bilden har verifierats i fil men har ännu inte flashats från
`0x0`.
Den äldre `release/BongoDesk-spotify-v6-stable.bin` är **inte** aktuell
firmware. Den äldre `release/BongoDeskSpotify.exe` är **inte** byggd från
nuvarande companion-kod. Båda äldre filerna ligger kvar lokalt men ignoreras
av Git.

## Aktuell Windows companion

Ladda ned [BongoDeskSpotify-deep-sleep-2026-09-30.exe](release/BongoDeskSpotify-deep-sleep-2026-09-30.exe)
och dess [.sha256-fil](release/BongoDeskSpotify-deep-sleep-2026-09-30.sha256).
EXE:ns SHA-256 är `65D3DAEAFAA4E1CE87A5F9FE52F66923B832E46D8DFBC56917F60EBD6A25128C`.
Den är byggd från den nya companion-koden med projektets ordinarie
`BongoDeskSpotify.spec`; inga personliga inställningar eller Spotify-token
ingår. EXE:n är inte kodsignerad, så kontrollera hashen före start. Både denna
companion och ESP32-firmwaren behövs för mediedata och albumomslag.

Stäng först en redan körande Bongo Desk-app med **Exit** i systemfältet så att
endast en companion använder serialporten. Starta sedan den nedladdade EXE:n
med dubbelklick och välj rätt COM-port i inställningarna om `AUTO` inte hittar
enheten. Appen använder samma instanslås och användarprofil som tidigare
versioner. När den startas normalt kan den befintliga autostartposten peka om
till den körda EXE:n om autostart är aktiverad i användarens inställningar.
Se [companion/README.md](companion/README.md) för hur ett eget Spotify-konto
kopplas till profilen.

### Verifieringsstatus

- Firmware byggdes från aktuell källkod med `esp32-024r-spotify`: RAM 33,9 %, flash
  38,8 %. Appbinärens hash matchar exakt den som flashades till `0x10000` via
  COM6 den 2026-09-29; esptool verifierade då skrivningen.
- Den nya fullbildens fyra delar och adresser har kontrollerats mot byggfilerna,
  och appens checksummor är giltiga. Fullbilden har ännu inte flashats från `0x0`.
- Alla 14 companion-tester passerade. EXE:n har provats på COM6, installerats
  lokalt och visat aktuell statistik, albumomslag, meny och panelbyte.
- Användaren rapporterade fungerande Windows sleep/resume och ett senare
  shutdown/power-on-prov. Vid shutdown-provet var uppgiften att låta datorn
  vara avstängd minst elva minuter och kontrollera mörk skärm före start och
  UI inom ungefär en minut efter inloggning; svaret var ”Det funkar”. Det är en
  kvalitativ observation utan uppmätt släcktid, väcktid eller deep sleep-ström.

## Skärmsläckning och deep sleep

Källkoden från 2026-09-29 innehåller en ny, separat 10-minutersgräns för
companionens närvaro. En aktiv companion skickar redan statistik ungefär varannan
sekund. Om giltig statistik uteblir i tio minuter släcker ESP32 bakbelysningen
på GPIO 27, sätter ILI9341 i vila och går i deep sleep. ESP32 gör sedan en
mörk kontrollvakning var 25:e sekund och tänder skärmen först efter två nya,
giltiga statistikpaket. Companion återansluter vid serialfel och skickar om tid,
statistik, mediedata och cachat omslag efter skärmens omstart. Kattens befintliga
`SLEEP_TIMEOUT` är oförändrad.

Funktionen finns i det nya versionsmärkta firmware- och companion-paketet ovan.
Båda delarna behövs; den äldre panelmenyreleasen från 2026-09-24 saknar
skärmsläckning och återanslutning. Appbinären har flashats på `0x10000` och ett
kort prov med källkörd companion visade normalt UI, meny, panelbyte och
albumomslag. I ett bortfallsprov höll aktiv companion skärmen tänd
cirka 1,5 timme; efter att källprocessen stoppades sågs panelen senare släckt.
Vid återstart loggades första giltiga statistikpaketet kl. 15:47:40.588 den
2026-09-29 och normalt UI rapporterades senast 15:48:23. Det ger högst cirka
43 sekunder till användarsvaret, men ingen exakt visuell tidtagning gjordes.
Tid, statistik, samma låts omslag och meny/panelbyte fungerade efter väckning.
Användaren såg ingen ljusblixt under mörk period eller vid väckning. Vid ett
separat Windows sleep/resume-prov var skärmen släckt före väckning och normalt
UI återkom inom ungefär en minut enligt användaren, utan exakt tidtagning.
Ett senare shutdown/power-on-prov rapporterades också fungera, men utan
detaljerad logg eller exakt tidtagning. Faktisk deep sleep-ström är inte mätt.

En separat lokal companion-kandidat byggdes från `companion/BongoDeskSpotify.spec`.
Vid isolerad körning på COM6 bekräftade användaren UI, statistik, samma omslag,
meny och panelbyte; tray Exit stängde appen. Efter användarens godkännande
installerades samma kandidat lokalt 2026-09-30 som
`%LOCALAPPDATA%\BongoDesk\BongoDeskSpotify.exe` med SHA-256
`65D3DAEAFAA4E1CE87A5F9FE52F66923B832E46D8DFBC56917F60EBD6A25128C`.
Den tidigare installerade filen finns som
`BongoDeskSpotify.backup-20260930-185311-3c46b403.exe` i samma mapp.
Autostarten pekar på den nya installerade filen. Användaren bekräftade normalt
UI med aktuell tid/statistik och albumomslag samt fungerande långtrycksmeny och
panelbyte även med den installerade versionen.
Den nya versionsmärkta EXE:n i `release/` är byteidentisk med denna installerade
och provade kandidat.

### Föregående release från 2026-09-24

Den äldre [fullständiga panelmenybilden](release/BongoDesk-panel-menu-hit-2026-09-24-full-0x0.bin)
har SHA-256 `9472424046566406A486509294CAF2995DEA9FA2A73E3AF0C3FBBFCD1961FDCC`.
Dess [Windows companion](release/BongoDeskSpotify-panel-menu-2026-09-24.exe)
har SHA-256 `3257ABB16B11A4E569AC22CEF59B2E3BAD00F073FC7138EC2118378C56F43459`.
Filerna finns kvar för den tidigare panelmenyversionen; den releasen innehåller
inte den nya strömstyrningen eller `SYNC_REQUEST`.

### Fysisk kontroll när skärmen är ansluten

1. Kör den nya companion och firmwaren tillsammans. Låt datorn vara oanvänd
   minst elva minuter och kontrollera att skärmen fortsätter visa Bongo.
2. Stäng av datorn med USB-strömmen kvar. Mät tiden från sista statistikpaketet:
   efter omkring tio minuter ska bakbelysning och LCD vara släckta och ESP32
   ha gått i deep sleep. Observera särskilt om de korta timerväckningarna ger
   någon ljusblixt; en sådan måste rapporteras som ett kvarvarande hårdvarufel.
3. Starta datorn och den nya installerade companion. Mät från att companion
   börjar skicka data tills skärmen visar UI. Målet är högst 60
   sekunder. Kontrollera tid, CPU/RAM/WPM,
   låttitel, progress och samma låts albumomslag utan låtbyte.
4. Upprepa med Windows sleep/resume. Kontrollera därefter Bongo-bonk,
   långtrycksmenyn, medietap, dubbel-/trippeltryck, sidsvep och svep ned till DJ.

## Flasha från Windows

1. Ladda ned den aktuella `.bin`-filen och `.sha256`-filen till samma mapp.
   Installera Python och esptool om de saknas: `py -m pip install esptool`.
2. Stäng Bongo Cat companion via **Exit** i systemfältet och stäng eventuell
   serialmonitor, så att porten är ledig. Hitta enhetens COM-port i
   Enhetshanteraren; ersätt `COM6` nedan med dess faktiska port.
3. Öppna PowerShell i nedladdningsmappen och kontrollera filen:

   ```powershell
   Get-FileHash .\BongoDesk-deep-sleep-2026-09-30-full-0x0.bin -Algorithm SHA256
   ```

   Hashen ska vara `7908115A4FD4D25E78E7BB46189DE57D8C044C63179AB9DD9D7E5C5CAC03CD6C`.
4. Flasha **hela bilden från `0x0`**:

   ```powershell
   py -m esptool --chip esp32 --port COM6 --baud 460800 write-flash 0x0 .\BongoDesk-deep-sleep-2026-09-30-full-0x0.bin
   ```

   Om anslutningen fastnar vid `Connecting`, håll **BOOT** nedtryckt och tryck
   kort på **RESET/EN** vid behov. Släpp BOOT när chippet har identifierats och
   skrivningen börjat. Vänta på verktygets skrivverifiering och omstart.
5. Starta Windows companion igen. Den behövs för mediainformation,
   Spotify-data, albumomslag och systemvärden; firmwaren hämtar inte dessa
   uppgifter själv. Se [companion/README.md](companion/README.md) för
   nedladdning, Spotify-koppling och körning från aktuell källkod.

En fullständig flashning skriver även över området för enhetens NVS-data i
bildens adressintervall. Kontrollera COM-porten och filens hash före körning.

## Bygg från källkod

```powershell
pio run -e esp32-024r-spotify
```

Detta bygger appfilen `.pio/build/esp32-024r-spotify/firmware.bin`, som hör
hemma vid `0x10000`. Den är inte samma fil som den sammanslagna
`release/*-full-0x0.bin`, som flashas vid `0x0`. Bygginställningarna finns i
`platformio.ini`. Visuella, simulerade förhandsbilder finns i `visuals/`.

Personliga inställningar och Spotify-token ligger i `%APPDATA%\BongoCat`,
utanför projektet, och ska inte läggas till i Git.

# Bongo Cat för ESP32-024R

Firmware för en ESP32-024R med 240×320 ILI9341-pekskärm och en Windows
companion som skickar tid, systemvärden, mediastatus och albumomslag via serial.
ESP32 visar Bongo-animationer, en gemensam panelmeny och en mediasida med
omslag, vinyl och DJ-katt.

## Aktuell nedladdningsbar firmware

Använd [BongoDesk-panel-menu-hit-2026-09-24-full-0x0.bin](release/BongoDesk-panel-menu-hit-2026-09-24-full-0x0.bin)
för en komplett flashning från adress `0x0`. Tillhörande kontrollsumma finns i
[.sha256-filen](release/BongoDesk-panel-menu-hit-2026-09-24-full-0x0.sha256):

```text
SHA-256  9472424046566406A486509294CAF2995DEA9FA2A73E3AF0C3FBBFCD1961FDCC
```

Bilden innehåller bootloader vid `0x1000`, partitionstabell vid `0x8000`,
startdata (`boot_app0`) vid `0xe000` och appen vid `0x10000`. Appen är
byte-identisk med panelmenyversionen som laddades till användarens ESP32:
SHA-256 `A1BCFC0B70F1EF83126FB8539385D66C155AACCB02C39B6E412FC6A18D15A8A4`.
Den äldre `release/BongoDesk-spotify-v6-stable.bin` är **inte** aktuell
firmware. Den äldre `release/BongoDeskSpotify.exe` är **inte** byggd från
nuvarande companion-kod. Båda äldre filerna ligger kvar lokalt men ignoreras
av Git.

## Aktuell Windows companion

Ladda ned [BongoDeskSpotify-panel-menu-2026-09-24.exe](release/BongoDeskSpotify-panel-menu-2026-09-24.exe)
och dess [.sha256-fil](release/BongoDeskSpotify-panel-menu-2026-09-24.sha256).
EXE:ns SHA-256 är `3257ABB16B11A4E569AC22CEF59B2E3BAD00F073FC7138EC2118378C56F43459`.
Den är byggd från nuvarande `companion/` med projektets ordinarie
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

- Panelmenyappen byggdes från aktuell källkod med miljön
  `esp32-024r-spotify`: RAM 33,5 %, flash 36,9 %.
- Just den appbinären laddades till `0x10000` via COM6 den 2026-09-24.
  Uppladdningsverktyget rapporterade `Hash of data verified`.
- Användaren har enligt uppgift provat versionen manuellt. Detaljerade
  skärm-, touch-, DJ- och albumomslagsresultat är ännu inte dokumenterade i
  projektet.
- Den sammanslagna bilden har verifierats som fil och dess delar har
  kontrollerats mot byggutdata. Den har ännu inte flashats separat från `0x0`.
- Den nya produktions-EXE:ns `--help` har bekräftats fungera. Normal start och
  **Exit** med ansluten skärm återstår att verifiera. Den kompletta
  firmwarebilden återstår att prova genom flashning från `0x0`.

## Flasha från Windows

1. Ladda ned den aktuella `.bin`-filen och `.sha256`-filen till samma mapp.
   Installera Python och esptool om de saknas: `py -m pip install esptool`.
2. Stäng Bongo Cat companion via **Exit** i systemfältet och stäng eventuell
   serialmonitor, så att porten är ledig. Hitta enhetens COM-port i
   Enhetshanteraren; ersätt `COM6` nedan med dess faktiska port.
3. Öppna PowerShell i nedladdningsmappen och kontrollera filen:

   ```powershell
   Get-FileHash .\BongoDesk-panel-menu-hit-2026-09-24-full-0x0.bin -Algorithm SHA256
   ```

   Hashen ska vara `9472424046566406A486509294CAF2995DEA9FA2A73E3AF0C3FBBFCD1961FDCC`.
4. Flasha **hela bilden från `0x0`**:

   ```powershell
   py -m esptool --chip esp32 --port COM6 --baud 460800 write-flash 0x0 .\BongoDesk-panel-menu-hit-2026-09-24-full-0x0.bin
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

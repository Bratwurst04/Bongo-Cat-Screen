# Bongo Cat app-v1.2

## Nytt

- Fokus med valbara fokus- och paustider, förloppsbåge, fassignaler och sparade lokala inställningar. Panelmenyn har nu BONGO, SPELARE, FOKUS och INSTALLNINGAR.
- Skärmen släcks efter tio minuter utan giltig companion-trafik och kan vakna när companionen återkommer. Den vanliga Bongo-animationens vilotid är separat.
- Windows companion visar väntstatus under Spotifys API-spärr, begränsar automatisk API-pollning utan lokal Spotify-session och har begränsad diagnostik som kan exporteras från systemfältet.
- Lokal Spotify på datorn behåller aktuell låt och rätt omslag även vid snabba låtbyten och långa omslagsöverföringar. Touchkommandon loggas utan låtdata.

## Filer och kontrollsummor

- `BongoDesk-app-v1.2-2026-10-03-full-0x0.bin` — SHA-256 `B25028C1995AEFA81C99123133FA0A24898D2DA264DBBF2CDA9A2DBA3345B095`. Komplett ESP32-bild för flashning vid `0x0`.
- `BongoDeskSpotify-app-v1.2-2026-10-03.exe` — SHA-256 `71756E01987D8A84C76DDCF83B76E9C512A7B5B2E09439DB94D10E36109ABF9F`. Windows companion; osignerad.

Appdelen i fullbilden är byteidentisk med appen som flashades och provades vid `0x10000` den 2026-10-02. Companion-filen är byteidentisk med den installerade och provade EXE:n. **Den kompletta bilden har ännu inte flashats från `0x0`**; en sådan flashning skriver över lagrade enhetsinställningar i NVS-området.

## Kvar att mäta

Faktisk strömförbrukning i deep sleep, exakta släcknings- och väcktider, LED-pulser och återhämtning för samma låt/omslag efter en verklig API-spärr utan lokal Spotify-session är ännu inte uppmätta. Tidigare versioner finns kvar som separata releasefiler.

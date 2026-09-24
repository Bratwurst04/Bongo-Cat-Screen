# Bongo Cat – Current State

Senast uppdaterad: 2026-09-24

AKTUELLT:
- Långtryck öppnar eller stänger samma panelmeny från både Bongo- och mediasidan. Menyn ligger på LVGL:s översta lager och markerar den aktiva panelen.
- Menyn har två stora val: BONGO och SPELARE. Tryck på den andra panelen växlar skärm; tryck på den aktiva stänger menyn. Menyn fångar övrig touch och stängs efter sex sekunder.
- En väntande medietap avbryts när menyn öppnas. Medietap skickas inte medan ett finger hålls nere. Med menyn stängd behålls Bongo-bonk, medietap, dubbel-/trippeltryck, sidsvep och svep ned till DJ.
- Menyval kräver träff med båda råa touchaxlarna vid både nedtryckning och släpp inom samma faktiska knapprektangel. Rå X mappas till skärmens höjd och rå Y till bredd med nominell skala 200–3900; axlarnas verkliga ändlägen och sidriktning behöver bekräftas på enheten. Svep och tryck utanför knapparna fångas utan panelbyte.
- Dashboardens statistik, mediastatus, låttitel och bonk-räknare finns kvar som sekundär information och respekterar inställningar som döljer systemvärden.
- PNG-källsprites finns i `assets/`. `tools/export_ui_visuals.py` genererar sju simulerade 240×320-vyer, kontaktkartor och manifest i `visuals/`, inklusive menyn från båda skärmarna.
- DJ-kompositionen använder befintlig katt och lokala DJ-lager. Noter och effekt väljs oberoende ungefär var 450 ms endast under uppspelning; den sista rutan fryser vid paus.
- Firmware med korrigerad menyträff byggdes utan fel från aktuell källkod (RAM 33,5 %, flash 36,9 %). Appbinären med SHA-256 `A1BCFC0B70F1EF83126FB8539385D66C155AACCB02C39B6E412FC6A18D15A8A4` flashades via COM6 till `0x10000` den 2026-09-24; esptool rapporterade `Hash of data verified`.
- Användaren har enligt uppgift provat denna version manuellt. Detaljerade observationer för menyträffar, övriga gester, DJ och albumomslag finns ännu inte protokollförda här. Lyckad uppladdning är inte en verifiering av skärm- eller touchbeteende.
- En komplett flashbild för adress `0x0` finns nu i `release/`. Den innehåller bootloader, partitioner, `boot_app0` och exakt samma appbinär vid `0x10000`. Bildens segment och kontrollsumma är verifierade i fil; den sammanslagna bilden har inte flashats separat.
- En ny Windows companion från ordinarie spec finns i `release/BongoDeskSpotify-panel-menu-2026-09-24.exe` (SHA-256 `3257ABB16B11A4E569AC22CEF59B2E3BAD00F073FC7138EC2118378C56F43459`). Sju livscykeltester och isolerat prov av `SPOTIFY API`/`SPOTIFY`/`MEDIA_STATE:NONE` passerade. Produktions-EXE:ns `--help` har bekräftats fungera; normal start och tray-Exit med ansluten skärm har ännu inte verifierats.
- Serialprotokoll, Spotify-progress och albumomslagsöverföring är oförändrade. Companion är oförändrad i detta arbete.

NÄSTA STEG:
- Dokumentera resultaten av fysisk kontroll av menyknapparnas råa touchträffar, långtryck, timeout och panelväxling samt att inga mediekommandon eller bonks skickas från menyn.
- Dokumentera övriga gester, DJ-animation och albumomslag på enheten innan panelmenyn betraktas som fullt hårdvaruverifierad.
- Prova den kompletta flashbilden från `0x0` samt normal start och tray-Exit för produktions-EXE:n med ansluten skärm.

INTE NU:
- Windows settings
- Wi-Fi eller OTA
- Ändringar i serialprotokollet

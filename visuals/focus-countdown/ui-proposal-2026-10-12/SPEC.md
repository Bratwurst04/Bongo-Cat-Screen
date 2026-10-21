# Godkänd UI-specifikation: Fokus-nedräkning

Lead har godkänt denna avgränsade utformning för Code2:s implementation.
`render_proposal.py`, PNG och `manifest.json` i samma mapp är designreferens.
Detta dokument ändrar ingen firmware.

Alla koordinater avser 240×320 och rektanglar anges som x,y,bredd,höjd.

| Del | Ruta | Font / färg / justering |
| --- | --- | --- |
| Bongo fas | 171,28,64,9 | `lv_font_unscii_8`, `0x505860`, höger |
| Bongo tid | 139,44,96,17 | `lv_font_unscii_16`, `0x303840`, höger |
| Player fas | 68,15,36,11 | `lv_font_montserrat_10`, `focusAccentHex()`, mitten |
| Player tid | 109,15,48,11 | `focus_digits_14_tight`, `0xE6EBEF`, mitten |
| Player pausmarkör | 163,17,7,7 | Två staplar: x163 och x168, y17, vardera 2×7, `0xE6EBEF` |

Labels är transparenta utan ram/bakgrund och tar inte touch.

- Bongo fastext: `FOKUS` eller `PAUS`; lägg till ` ||` när Fokus-timern
  är fryst. Player fastext: `FOKUS` eller `PAUS`; separata pausstreck
  visas bara när Fokus-timern är fryst, oberoende av musikens tillstånd.
- Båda vyerna visar samma lokala tid: minst två minutsiffror och två
  sekundsiffror, till exempel `04:59`, `00:59`, `120:00`. Befintlig
  avrundning uppåt till visad sekund bevaras.
- `focus_digits_14_tight` är ett separat statiskt subset för `0–9` och
  kolon: oförändrade bitmappar, advance och kerning från Montserrat 14,
  men line-height=11 och base-line=1. Dessa glypher har ofs_y=0 och är
  högst 10 px höga. Referensdata finns i `font-player.json`. Ändra inte
  ordinarie Montserrat 14 eller fontfiler i `.pio/`. Aktivera Unscii 8.
- Under befintlig **kompakt Player-PAUS-notis** döljs bara det dubblerade
  fasnamnet. Tiden får ruta 96,15,48,11, centrerad vid x120. Eventuella
  pausstreck: x147 och x152, y17, vardera 2×7. Notisen ligger kvar på
  85,0,70,14 och anger fasen. Stora övergående fasnotiser bevaras.
- Idle, Prepared/nollställd och Completed döljer hela nedräkningen.
  Bevara fasbyte och båda pausade faser. Skapa labels/statiska buffertar
  en gång och behåll sekund-/fas-/pauscache. Ändra cue-layout bara vid
  notisens tillståndsbyte. Ingen ny timer, serialtrafik eller companionkod.
- Flytta inte befintlig klocka, statistik, katt, omslag, låttext eller
  touchytor. Behåll gester, panelmeny och DJ. Layouten ryms för RAM 100 %,
  WPM 200 (befintligt companiontak), 120:00 och pausmarkör.

Code2 synkar native font, firmware, riktade kontroller och nya 240×320-bilder.
Lead verifierar den frysta kandidaten och gör det begärda fysiska provet
av läsbarhet/tillstånd, gester, omslag samt heap och jämnhet under art2.

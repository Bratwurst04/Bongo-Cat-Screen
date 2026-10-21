# Selektiv beskärning av Windows Spotify-omslag – 2026-10-19

## Status och exakta versioner

Installerat och igång lämnas **59FC2E33/EBB334A9 vid 921600**. Den nya,
separata companionen är **byggd och arkivverifierad, inte startad eller
installerad**:

- `dist/companion-2026-10-19-artwork-crop-dev/BongoDeskSpotify.exe`
- 19 664 430 byte; SHA-256
  `9414574673DDCE6019C57D45A954FB23B11F33682C461D112471E3D5C92D7CA3`.
- Firmware återanvänds exakt: `.pio/candidates/artwork-refinement-2026-10-19-EBB334A9.bin`,
  937 184 byte, SHA-256
  `EBB334A926709E047DA1D930684C76D02DFA162332C508E775F062AE492E2FF3`.
  Ingen firmwarebyggning eller flashning ingår.

## Avgränsad regel

`companion/artwork_crop.py` känner igen den observerade transparenta
PNG-ramen från **Windows Spotify SMTC**. Källa, kvadratisk känd layout,
albumets alfafyllnad, transparenta sidfält/mellanrum, nästan vit footer och
minst 97 % IoU mot footerns normaliserade alfamask måste stämma. Geometrins
tolerans utgår från en pixel i 300px-referensen, avrundad uppåt vid skalning.
Tre referenspixels kantmarginal tillåter resamplingsfransar.

Analysen sker före RGB-konvertering. Referensbilden med SHA-256
`25F4B3A2733D1BB4557D9A4A0D734F0374B9F0B462367490A2C7148C69F0E6F7`
ger exakt **(33,0,267,234)**, en 234×234-albumkvadrat. Den får inget andra
6 %-inset. Samma vanliga 112-RGB888-cache går därefter till befintlig
kompaktbild och senare detaljbild.

`media_bridge.py` aktiverar regeln endast för redan identifierad
`windows_spotify`-thumbnail. API-omslag och andra Windows-spelare använder
ursprunglig konvertering. Icke-match behåller den gamla konverteringen
byteidentiskt. Ingen titel/artist, OCR, ny hämtning, nättrafik eller extern
bildtjänst används. Okänd layout, opak/flattened bild, JPEG och osäkra små
resamplingar lämnas avsiktligt kvar i den gamla vägen. Regeln är därför
inte en generell lösning för alla Spotify-bilder.

## Verifiering och granskningsmaterial

- **8 nya riktade PASS**, med det riktiga fotoreferensprovet, skalade
  varianter, annat/svart album, 16 negativa fall mot fryst 59FC-konverterare,
  faktisk Windows/API-gate, engångskonvertering/cache och native bildkedja.
- **165 relevanta PASS**, noll fel/skip/externa nätförsök. Artwork,
  turntable/flip, UTF-8, capability-startup, diagnostik, manuell refresh och
  lokal mediestyrning ingår; detta är ingen ny bred helsuite.
- Utan det lokala originalfotot: **7 PASS, endast fotoreferensprovet SKIP**.
  Övriga prov använder ett syntetiskt album och separat hashpinnad 192×53
  footer-alfa, utan albumfoto. Den smala 59FC-testreferensens metod jämförs
  exakt med historisk AST i kandidatkontrollen.
- Verklig sender, C++-parser/CRC, två bildslotar och render visar gemensam
  cache, bevarad coarse-mask/pose och samma crop i kompakt/refinement.
  Detta är hostbevis, ingen fysisk TFT- eller tidsmätning.
- PyInstaller-paketets **13 moduler och fyra resurser** matchar aktuell
  källa. Retired `media_seek` saknas fortsatt.
- Före ändrade statusrubriker verifierades **9 583 äldre filer exakt**.
  Slutkontrollen återverifierar dem, alla äldre statusavsnitt och EBB-firmware.

Förhandsvisning finns i ignorerad
`build/artwork-crop-2026-10-19/preview/r2/`: `index.html`, `comparison.png`,
exakt crop och native kompakt/full-bilder. Manifest SHA-256:
`75EC9706F2B89BC67AF2727198EC9DB10CA54EA189C990B307A83FB5098A9F8F`.
Originalfoto och samtliga fotoderiverade previewbilder ligger endast i
ignorerad build. Historisk r1 med egna källkopior bevaras separat.
Bygg-, test-, frys- och paketinventarier finns i samma byggmapp.

## Kvarvarande fysiskt prov

Efter Leads granskning och användarens nya godkännande av exakt apphash:
byt endast companion, spela den berörda låten och kontrollera att footern
försvinner. Jämför ett redan korrekt omslag och en annan Windows-spelare.
Kontrollera samma utsnitt från snabbild till detalj, utan extra flip,
storlekshopp eller kantändring. Kodens resultat ändrar inte tidigare
avgränsad fysisk acceptans för det installerade paret. **Den nya appens
crop på TFT är ännu oprövad.** Ingen profil/auth/config/COM/runtime eller
Windows-inställningsvy har hanterats av Code i detta steg.

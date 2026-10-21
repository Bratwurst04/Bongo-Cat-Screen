# C2 efter extra reset: fullformat, ingen kompaktförhandling – 2026-10-18

**Installerat par: companion 356A5EC0 / firmware C6EBAE4B, 921600 baud.**
Detta är ett senare uppföljningsprov. Den tidigare
[uppstartsrapporten](artwork-compact80-runtime-2026-10-18.md) bevaras exakt;
dess sista observation var 22:45:01 och innehöll inga omslagsmätningar.
Tider här är svensk sommartid, UTC+02.

## Observerat efter normal RESET/EN och musik

Användaren bekräftade Leads extra reset-/musiksteg med ”ok”. Säker
eventhistorik visar DEVICE_RESYNC **23:01:23.582** och lyckad bas-
ART_CAPABILITY **23:01:23.649**. Ingen ART_COMPACT_CAPABILITY finns i den
frysta säkra historiken sedan appstart. Två omslag fick lyckad ART2-kvittens
på första försöket:

| Omslag | ART_READY | ART_ACK | READY→ACK | Sändtid | Byte |
| --- | --- | --- | --- | --- | --- |
| 1 | 23:01:34.789 | 23:01:39.471 | 4 682 ms | 4 625 ms | 37 632 |
| 2 | 23:01:59.466 | 23:02:04.146 | 4 680 ms | 4 625 ms | 37 632 |

Båda ART_SENT anger två frames per write och 15 ms intervall. Det är
**äldre fullformat**, inte det avsedda kompaktformatets 12 800 byte.
Detta är därför inget giltigt prov av kompaktformatets ensekundsmål.

Status **23:04:09.203** visade ansluten ESP32, uptime 160 s, heap
154 236/min 151 508 av 261 064 byte och CPU-mätaren av. Snapshotens kontroller
för installerad apphash, förväntad konfiguration, credentials, Run-post och
genvägar var samtliga true. Ingen ny UI-/gest-/sleepacceptans ingår.

## Slutsats och provgräns

Extra reset återställde bas-ART2 men ingen kompaktförhandling är belagd.
Varför kompaktraden saknas är inte fastställt. Att Lead hittade strängen
och korrekt guard i C6-källan/binären bevisar inte att raden mottogs.
Den separat byggda [C3-appen](capability-startup-2026-10-18.md) är inte körd
eller installerad och är **inte bevisat** åtgärda detta senare bortfall.
Fysisk C3-återhämtning och kompaktfart återstår efter eget appgodkännande.

Enda runtimekälla för denna rapport:
`%LOCALAPPDATA%/BongoDesk/deployment-artwork-compact80-20261018-222444-812590-post-reset-fullformat.json`,
SHA-256 verifierad före läsning:
**18F115FAFB6A97E4D425B41155B89749081BB9A96C4A212E31809D21BC649E69**.
Inga privata backupreferenser följdes. Code gjorde ingen runtimeåtgärd,
serial-/API-trafik, installation eller flashning. Äldre rapporter,
kandidater och frysta byggbevis bevaras.

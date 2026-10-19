# Bekräftad Spotify-bakgrundsincident – 2026-10-16

Alla tider är Europe/Stockholm. Underlag:
[innehållsfri incidentjournal](C:/Users/gusta/AppData/Local/BongoDesk/runtime-playback-endpoint-incident-20261016-1604.json),
och Leads senare användarbesked. Par: **3EDD2187/55669C87**.

## Bekräftat förlopp

Användaren bekräftade Waiting medan musiken fortsatte. iPhone 13 Pro
var upplåst med Spotify i bakgrunden; appen hade inte öppnats under
rapporteringen. Detta skiljer sig från
[första A–B–A-provet under paus/stopp](playback-endpoint-diagnostics-runtime-2026-10-16.md).

| Endpoint | Tid | HTTP |
| --- | --- | ---: |
| A: playback_state | 16:01:49.600 | 200 |
| A | 16:01:57.454 | 204 |
| B: currently_playing | 16:02:27.741 | 204 |
| A | 16:02:57.972 | 204 |

B hade accepted/started/completed, ett försök. A204 fortsatte därefter.
Båda gav tomma svar: inget belägg för B-fallback som rättning.
Ingen pollningsökning gjordes.

## Kontakt, skydd och osäkerhet

Oförändrat processpar 14588/4004, färsk ESP32-kontakt.
API ready men idle/30 s, Windows Spotify saknades. Reserver, Retry-väntan
och klockspärr var noll; totalt 429 fortsatt två. Config var bevarad.
Enligt Lead förnyades access-token/expiry normalt 15:44, medan refresh-token
och scopes bevarades; ingen kredentialreset gjordes.

Strömsparläge och Låg dataförbrukning för aktuellt WiFi var av.
AppStore erbjöd ingen uppdatering. Orsak och permanent rättning är
inte fastställda.

## Avgränsade prov och väntande steg

Efter WiFi→mobildata utan Spotifyöppning, med begärd väntan cirka 40 s,
svarade användaren: ”Nej, Waiting står kvar”. Begränsa IP-spårning angavs på, DNS
1.1.1.1 och ingen övrig VPN. Inställningarnas omfattning över båda näten
är okänd; DNS/relä kan inte uteslutas som hypotes av detta prov.
Global Bakgrundsuppdatering var Wi-Fi och mobildata, men Spotifyreglaget
av. Efter begäran att slå på endast Spotifyreglaget och vänta cirka
60 s utan Spotifyöppning svarade användaren åter: ”Nej, Waiting står kvar”.
Åtgärdstiderna mättes inte. Leads läsning 16:14:36 visade fortsatt
A204, senast 16:14:04.101, frisk kontakt och inga nya 429.
Detta bevisar ingen permanent orsak och utesluter inte ett annat utfall
efter en ny foreground-/bakgrundscykel.

Efter återställt Wi-Fi och foreground→bakgrund bekräftade användaren låt
och omslag tillbaka. A200/available 16:16:08.903, aktivt 7,5 s, färsk
kontakt och oförändrade skydd; ingen omstart/appändring. Längre bakgrundsprov väntar.

Endast denna rapport tillkommer. 155 aktuella och 155 frysta källor, binärer,
manifest och tidigare rapporter bevaras. `git diff --check` och textkontroll:
godkända. Ingen produkt-, profil-, API- eller runtimeåtgärd utfördes av Code.

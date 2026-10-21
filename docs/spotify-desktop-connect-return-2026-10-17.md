# Spotify Connect: återkomst via datorappen – 2026-10-17

Europe/Stockholm. Fryst baseline: **17:44:26.718754+02:00**.
[Sanerat underlag](C:/Users/gusta/AppData/Local/BongoDesk/runtime-spotify-connect-return-20261017-1744-baseline.json),
verifierad SHA-256:
`AA6DBEB71AD6A2FA49422E658447817D18A53D0081BBDB037E5D7FAB0BA7F40A`.

## Bekräftat och läsgränser

Tidigare 30-minutersprov med DNS AV avslutades **ofullständigt** vid avfärden.
Bortatiden är inget kontrollerat prov. Vid återkomst cirka 17:40 var datorSpotify
öppet utan mobilens uppspelning. Musik fortsatte på iPhone med låst/släckt
**skärm**, inte avstängd telefon; 1.1.1.1 var åter PÅ.

Loggad A200 **17:09:12.902** följdes av A204 **17:09:18.062**,
senast **17:26:59.466**; källa blev Windows **17:27:10.023**.
Detta belägger ingen API-pollning efter källbytet. Telefonläget är inte
bekräftat under hela 17:09-perioden.

17:41:38: godkänd companion **68721143**, firmware **55669C87**, processpar 37336/39128 med
Explorer-förälder, frisk ESP32-status 0,159 s, CPU AV. Tak/Retry/klockspärr
blockerade inte; totalt 429 fortsatt två, senaste timmen noll.
Enligt Lead återställdes CPU AV med verifierad backup 14:35 och färsk
bekräftelse 14:36, efter den frysta 14:30-rapporten. Detta var enda
configändringen; Spotify-preferenser bevarades.

## Återkomst och nytt väntande prov

Lead begärde DNS helt AV och mobilSpotify öppet 30 s, datorappen kvar,
utan enhetsbyte. Användaren: ”Direkt jag gick in på spotify dök de upp
på dator och skärm. DNS bortkopplad”.
Åtgärderna tidsmättes inte separat. Utfallet stärker gemensamt
Connect-/telefonbakgrundsspår utanför Bongo, utan fastställd orsak.

17:44:26 kom visningen från **windows_spotify**; ingen ny A200 observerades.
Art2 seq60/64 fick ACK **17:43:12.698/17:44:04.608**.
Fyra NEXT **17:43:48–17:43:58** före baseline var inte Leadåtgärder.
14:29-provet är historik, utan omläsning eller återarmering. Ingen appstart,
flash eller kodändring gjordes i återkomststeget.

Begärt nytt 30-minutersprov räknas från denna baseline: DNS helt AV,
datorSpotify öppet, hemskärm/låst iPhone, fortsatt musik och ingen
mobilSpotify-foreground. Låstidpunkten är inte separat uppmätt.
Svar efter 30 minuter eller nytt bortfall:
**utfall väntar**. Ingen tidsacceptans eller fix påstås.

Endast denna rapport tillkommer; alla tidigare filer bevaras.

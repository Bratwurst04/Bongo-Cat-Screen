# C3 installerad: kompaktförhandling och tre omslag – 2026-10-18

**Faktiskt installerat: companion FD9D811B / firmware C6EBAE4B vid 921600.**
Användaren godkände exakt appfix. Lead installerade efter pending=0 med tre
verifierade profilbackuper och ZIP av föregående 356A5EC0. Konfiguration,
inloggning, Run-post och genvägar bevarades vid bytet. **Ingen firmware skrevs.**
Den tidigare [C3-byggrapporten](capability-startup-2026-10-18.md), dess frysning
och C2-rapporter är bevarade som historiska bevis.

- App SHA-256: `FD9D811B0356818A56AA0787AD3041820DA8D45D6083D8E0E822D3B59426DB06`.
- Oförändrad firmware SHA-256: `C6EBAE4B13DE934449E2F32738D2CBFAEEC2693C5ECF8EE8A3A71FDB6254D275`.

## Observerat driftprov

Explorerstart **23:21:16.914**, anslutning på första försöket **23:21:19.090**.
Bas-ART2 och kompaktkapabilitet för 12 800 byte bekräftades **23:21:22.377/.382**,
före första omslaget. Tider är svensk sommartid, UTC+02.

| Prov | ART_READY→ACK | Sändtid | Format / försök |
| --- | --- | --- | --- |
| Första efter appstart | 1 164 ms | 250 ms | 12 800 byte / första |
| Nästa låtbyte | 374 ms | 250 ms | 12 800 byte / första |
| Nästa låtbyte | 351 ms | 233 ms | 12 800 byte / första |

Alla tre fick lyckad ART2-ACK, åtta frames/write och 0 ms extra intervall.
ART_READY anger ursprunglig cachebild på 37 632 byte; **ART_SENT anger den
faktiska kompakta överföringen på 12 800 byte**. Ingen failure/retry eller
ART_CAPABILITY_RESEND finns i denna snapshot. Initialfrågan fungerade;
den nya fallbackvägens fysiska körning och orsak till förbättringen är inte
bevisade. Första omslaget överskred en sekund; de två efterföljande klarade
målet i detta prov. Det ger ingen garanti för alla byten eller mobil→skärm.

Användaren svarade **”Ja, snabbt och bilden ser bra ut”** på två begärda
låtbyten cirka tio sekunder isär och bildkvalitet. Detta är snäv fysisk
acceptans av observerad snabbhet/bild. Fulla gester, sleep/resume,
långdrift och sällsynt komplett exchange är inte provade här.

Senare credentialkontroll visar normal förnyelse: access-token ändrad,
utgångstid ökad och refresh-token oförändrad. Det är skilt från bytebevarad
inloggning vid installationen; ingen credentialreset påstås.

## Källgräns

Enda runtimekälla, hashverifierad före läsning:
`%LOCALAPPDATA%/BongoDesk/deployment-capability-startup-20261018-232028-898394-speed-test-baseline.json`,
SHA-256 **A2580A679C80EDF7E8DF3872ED4EDEAC6D4A90F9E0818264CF07D8E7A0D8CB20**.
Inga privata backupreferenser följdes. Code utförde ingen runtime-, serial-,
API-, profil-, installations- eller flashåtgärd.

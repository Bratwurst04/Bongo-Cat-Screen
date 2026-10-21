# Omslagsbeskärning installerad och snävt skärmprovad – 2026-10-19

**Installerat: companion 94145746 / firmware EBB334A9, 921600 baud.**
Tider är svensk sommartid, UTC+02. Whoopty-provet är kvalitativt accepterat;
**jämförelsen med redan korrekt omslag är osäker**. Tidigare
[byggunderlag](artwork-crop-2026-10-19.md), frysta källor, manifest,
förhandsbilder och äldre rapporter bevaras som historiska bevis.

## Godkänt appbyte

Användaren godkände exakt appen med ”Ja, installera appuppdateringen”. Lead
installerade den 19:02:34 efter tre verifierade profilbackuper och verifierad
backup av föregående 59FC-app. Samma kanoniska plats, config/auth,
Run-post, genvägar och baud behölls. **Firmware skrevs inte.**

- Companion, 19 664 430 byte:
  `9414574673DDCE6019C57D45A954FB23B11F33682C461D112471E3D5C92D7CA3`.
- Oförändrad firmwarereferens, 937 184 byte:
  `EBB334A926709E047DA1D930684C76D02DFA162332C508E775F062AE492E2FF3`.

Första förkontrollen stoppade före processstopp på redan utgången åtkomsttoken.
Leads stabilitetskontroll under minst tolv sekunder med aktuell Windows Spotify
tillät därefter denna i byteshjälparen. Tokenfälten bevarades vid byte/start;
Lead begärde ingen tokenförnyelse eller API-åtgärd. Detta är bytekontroll,
ingen Spotify-felsökning.

Appen startades genom befintliga Explorer desktop med `--startup` 19:02:48.
Två observationer, 19:03:14 och 19:04:45, bekräftar rätt installerad hash,
oförändrade config/authfält/Run/genvägar, två normala processer, ansluten
ESP32 och aktuell källa `windows_spotify`.

## Uppstartens överföring

APP_START loggades **19:02:50.164**, och första serieanslutningsförsöket
lyckades **19:02:52.328**. Bas- och kompaktkapabilitet kom **19:02:55.598/.600**,
före ART_READY **19:02:55.626**. Kompaktbilden skickades som **12 800 byte**
med åtta frames/0 ms; sendern tog **235 ms**. ACK **19:02:57.036** gav
**READY→ACK 1 410 ms**, varav SENT→ACK 1 167 ms. READY:s 37 632 byte
beskriver cachebilden, inte faktisk kompaktpayload.

Engångs-CAPS-resend loggades **19:02:57.624**. Basbekräftelse följde
**19:02:57.693** och refinekapabilitet först **19:02:57.695**, efter
kompakt-ACK. Ingen **ART_REFINE_SLOT eller fullöverföring** finns i denna
uppstartsbaslinje. Orsaken fastställs inte här.

## Senare drift och avgränsad fysisk acceptans

Ett senare anonymt låtbyte gav kompakt READY→ACK **444 ms** och
SLOT→full-ACK **4 748 ms**, båda på första försöket. Dessa kvittenser
tillskrivs ingen viss titel eller Whoopty. ACK visar mottagning och SLOT
vald bildslot; tiderna är ingen LCD-mätning eller generell ensekundsgaranti.

På frågan om Whoopty utan Spotify-remsa och senare skärpning utan hopp
svarade användaren **”Japp ser bra ut”**. Det accepterar den frågade
sekvensen kvalitativt. Jämförelsen med redan korrekt omslag är **osäker**:
användaren mindes inget referensomslag. Automatiskt bevisad bytebevaring
redovisas separat i byggrapporten.

Senaste observationen 19:06:46 bekräftar apphash/config/Run/genvägar och
Windows Spotify. Efter normal appkörning hade åtkomsttoken och giltighetstid
förnyats; refresh-token var exakt samma och nya åtkomsttoken inte utgången.
Lead ändrade/förnyade inte credentials. Detta är förenligt med normal
appförnyelse, skilt från oförändrade authfält vid installation/start.

## Källa och dokumentationsscope

Endast två privata snapshots lästes, båda hashverifierade före läsning:

- `%LOCALAPPDATA%/BongoDesk/deployment-artwork-crop-20261019-190204-909431-startup-baseline.json`:
  **0BF54368C081EDBE64164F9960E8A3D360B7CDE6F42D3062CE1EFFEC867FF7B2**.
- `%LOCALAPPDATA%/BongoDesk/deployment-artwork-crop-20261019-190204-909431-physical-crop-baseline.json`:
  **F0340D6E97B64DF56BCBEF913A0DFEFCD4742194B9E257C698795C1F32EDEA9D**.

Inga länkade profiler/backuper/loggar eller andra privata filer lästes.
Code har endast skrivit denna rapport och nya statusrubriker; ingen
produktkod, test, COM/runtime/API, installation, firmwarebyggning/flash,
commit, push eller release hanterades i dokumentationssteget.

# API-budget – driftrapport 2026-10-15

## Status och underlag

**17466EBF/F406 är installerad och automatisk API-mobilföljning med
5 s-grundintervall är kvalitativt godkänd av användaren.**
137:s manuella väntetryck var kvalitativt godkänt: snabb rätt låt,
oförändrad musik och rätt omslag. Dess senare 60 s-släp ledde till den
nya dagpolicyn. B8-felet, CB-controls, 137-omprovet och 17466-installationen
skiljs åt nedan.
Dag/natt, friskt 5 s-automatgolv och sleep/resume återstår.
Alla tider nedan är **2026-10-15, Europe/Stockholm**.

Underlag är Projektledarens verifierade installations-, logg- och
statusuppgifter, överlämnade till Kodskrivaren. Kodskrivaren har endast
skapat och kompletterat denna separata rapport i `D:\DEV\Ai\Github\Bongo-Cat-Screen` och
har inte läst eller ändrat den riktiga profilen, tokenfilen eller driften.

Den [frysta utvecklingsrapporten](api-budget-2026-10-14.md) beskriver läget
vid frysningen 2026-10-14. Dess dåvarande uppgift om en ännu ostartad
kandidat behålls som historik. Denna rapport redovisar det senare driftprovet
och ingår inte i det frysta 66-filersmanifestet. Frysta källkopior,
manifest, kandidatrapport, EXE, firmware och releasefiler har inte ändrats
i detta dokumentationssteg.

## Första installationen, B8C7BB28, utförd av Projektledaren

Användaren bad uttryckligen Projektledaren installera den nya companionen
för driftprov. Installationen gjordes utan flashning eller källändring.

| Uppgift | Verifierat resultat |
| --- | --- |
| Installerad EXE | `C:\Users\gusta\AppData\Local\BongoDesk\BongoDeskSpotify.exe` |
| Storlek | **19654754 byte** |
| SHA-256 | `B8C7BB2859F86737686899C86C2FA48CDE3702BD5CCBF28A86B13D45C7CC417E` |
| Rollback | `BongoDeskSpotify.backup-20261015-pre-api-budget-68CC5BC1.exe`, verifierad tidigare 68CC5BC1-hash |
| Config-/tokenbackup | Projektledaren verifierade backup med stämpel `20261015-113926` |
| Deploymentprotokoll | `C:\Users\gusta\AppData\Local\BongoDesk\deployment-api-budget-20261015-113926.json` |
| Firmware | Fortsatt **F406**, ingen flashning |

Det gamla processparet stoppades endast på exakt installationssökväg,
med Windows-källa och noll registrerade API-anrop senaste 15 minuterna.
Ingen budgetledger fanns före bytet. Den nya appen startades dolt med
`--startup`; Projektledaren observerade normalt processpar **81368/83756**.

Vid kopieringen var config och tokenfil byteidentiska. Efter start var
config fortfarande byteidentisk, credential-fälten access/refresh/expiry/
scope/type semantiskt bevarade och Windows Run-post oförändrad.
Detta innebär inte att hela tokenfilen påstås byteidentisk efter driftstart.

## Första sessionen

| Lokal tid | Loggverifierad händelse |
| --- | --- |
| 11:39:30.276 | `APP_START` |
| 11:39:32.461 | `SERIAL_CONNECT`, första försöket |
| 11:39:35.765 | art2-kapabilitet etablerad |
| 11:39:42.122 | `ART_SENT`, **4937 ms**, försök 1 |
| 11:39:42.161 | Lyckad art2-ACK, **39 ms** efter `ART_SENT` |

En tidigare omslagsöverföring avbröts avsiktligt vid seq2-byte med
`track_mismatch`. Den senare överföringen ovan lyckades på första försöket.
Det är loggverifierad transport; rätt omslag på den fysiska skärmen och
upplevd bild-/låtbyteslatens har ännu inte bekräftats för denna session.

## Statusprov 11:39:56.878

| Område | Observerat värde |
| --- | --- |
| Windows Spotify | Tillgänglig, `windows_spotify` som aktuell källa |
| API-anrop | **0** senaste 30 s och **0** senaste 15 min |
| Totalt registrerade HTTP 429 | **2**, ingen ny observerad |
| Lokal budgetprofil | `day`, effektivt intervall **60 s** |
| Historik | `history_complete=false` |
| Kvotåterhämtning | `quota_recovery=true` |
| Snabbperiod | `fast=false` |
| 24 h-gränser | Totalt **4000**, automatik **3600** |
| 30 s-gränser | Totalt **24**, automatik **18** |
| Förbrukning/reservationer | **0/0** |
| Lokal väntan/Retry/clockguard | Samtliga **0** |
| ESP32 | Ansluten, statusålder **0,731 s** |
| Heap | Ledigt **180052**, minimum **175916**, totalt **261608 byte** |
| Uptime, rapporterat värde | **233354** |

Statusen visar ofullständig historik och kvotåterhämtning med ett
60-sekundersgolv. Den visar ingen aktiv Retry-After eller clockguard vid
detta prov. Windows-källan gjorde inga API-anrop; **60 s är här ett
statusvärde, inte uppmätt stationär API-takt eller mobilupptäcktstid**.
Det friska daggolvet 5 s har inte verifierats i denna session.

## Övergång till mobil/API och första API-omslaget

Efter avslutad PC-Spotify och start från mobilen svarade användaren:
**”Spelar, men syns inte på skärmen”**. Det är den första fysiska
observationen under övergången, inte ett senare godkännande av API-bilden.

Projektledaren verifierade följande logg- och statusföljd:

| Lokal tid | Observation |
| --- | --- |
| 11:42:20.631 | `ART_MISSING`, `no_thumbnail`, i den sista Windows-thumbnailvägen |
| 11:42:21.002 | `ART_API_FALLBACK`, `skipped/track_mismatch` efter dess API-anrop |
| 11:42:21.110 | En `MEDIA_REFRESH`, `refresh_error`, `OSError`, vid stängningen av PC-sessionen |
| 11:42:32 | `source=spotify_api`, Windows Spotify inte tillgänglig. Ett budgeterat anrop, från thumbnail-fallbacken; profil `day/60 s`, ofullständig historik och kvotåterhämtning. Förbrukning 1, lokal profilväntan **48,109 s**, totalt 429 fortsatt 2 |
| 11:43:18.042 | Lokal väntan **2,953 s**, totalanropsräknare **217264**, API-snapshot ännu inte tillgänglig |
| 11:43:20.809 | `SPOTIFY_API_LOCAL_WAIT`, `profile/day`, `wait_seconds=1`, `interval_ms=60000` |
| 11:43:21.255 | `MEDIA_SOURCE spotify_api` och `MEDIA_TRACK seq4` |
| 11:43:21.325 | `ART_READY`/`ART_QUEUED`, **37632 byte**, försök 1 |
| 11:43:26.427 | API-källa, snapshotålder **5,188 s**, totalanropsräknare **217265**, två budgeterade automatförsök inklusive tidigare thumbnail-fallback. Lokal väntan **54,812 s**, Retry/clockguard **0**, ESP32 fortsatt ansluten |
| 11:43:26.554 | `ART_SENT`, **5235 ms**, art2, `frames_per_write=2` |
| 11:43:26.600 | Lyckad ACK, **46 ms** efter `ART_SENT` |

Detta visar den första riktiga API-snapshoten och dess naturliga,
kvitterade omslagsöverföring på den nya EXE:n, utan en ny observerad 429.
Den första automatiska playback-läsningen kom cirka **60 s efter den
tidigare thumbnail-fallbacken**. Övergångens väntan följde det importerade
60-sekundersskyddet under kvotåterhämtningen; den var inte ett prov av
frisk femsekundersprofil.

Exakt mobilstart och tidpunkt för färdig fysisk bild är inte uppmätta.
Ingen end-to-end-latens eller visuell omslagsacceptans påstås därför.
Den enstaka OSError-händelsen redovisas ovan; senare API-snapshot och ACK
är verifierade, men händelsens bakomliggande orsak är inte utredd här.

Projektledaren bad därefter användaren bekräfta rätt låt, omslag och tid
samt trycka **NÄSTA en gång på skärmen**, för prov av explicit reserv och
bekräftelseläsning. Det senare utfallet visade regressionen nedan.

## Regression i explicit control, installerad B8C7BB28/F406

Användaren rapporterade: **”Bytte men tar aslång tid innan skärmen uppdaterar.
Paus går fram också men inte play, men inget händer på skärmen på30+s”**.
Senare precisering: **”Tog1m20s attvisa nya låten”**.
Det är användarens uppskattning, inte en separat stoppursmätning.

| Lokal tid | Projektledarens verifierade logg/status |
| --- | --- |
| 11:45:08.489 | `MEDIA_CMD_RX NEXT` |
| 11:45:08.938 | `MEDIA_CONTROL NEXT skipped/api_error` |
| 11:45:29.824 | `MEDIA_CMD_RX PLAY_PAUSE` |
| 11:45:30.320 | `MEDIA_CONTROL PLAY_PAUSE skipped/api_error` |
| 11:45:32.329 | Ny `MEDIA_CMD_RX PLAY_PAUSE` |
| 11:45:32.808 | Ny `MEDIA_CONTROL PLAY_PAUSE skipped/api_error` |
| 11:46:33.080 | Nästa automatiska API-uppdatering, `MEDIA_TRACK seq5`, cirka **84,6 s efter NEXT-mottagningen** |
| 11:46:37.209 | API-källa, snapshotålder **4,141 s**, totalanropsräknare **217270** (sju sedan start). Budgetförbrukning **7**, varav **4 automatiska/3 explicita**, reservationer **0**, profilväntan **55,859 s** med 60 s-golv. Retry/clockguard **0**, totalt 429 fortsatt **2**, ESP32 ansluten med statusålder **0,357 s** |
| Efter seq5 | `ART_SENT` **5297 ms**, ACK **11 ms** senare |
| 11:49:34.650 | Automatisk API-uppdatering `seq6`, senare `ART_SENT` **5140 ms** och ACK **44 ms** efter sändning |

Kommandona tycks alltså utföras i Spotify enligt användaren, medan
companionen loggar fel och ingen snabb auktoritativ bekräftelse visas.
Den observerade fördröjningen godkänns inte som fungerande explicitcontrol.
De senare automatiska läsningarna och cirka fem sekunder långa, kvitterade
bildöverföringarna visar fortsatt API-/omslagsdrift; de bevisar inte att
controlkedjan fungerar.

Projektledarens skrivskyddade kontroll visade att alla tre behövda scopes
finns: read-playback-state, modify-playback-state och read-currently-playing.
Tokenförnyelse skedde **11:42:20.735**, med framtida utgång efteråt.
Endast boolesk närvaro/utgångsläge återgavs; inga tokens eller klient-id
ingår här. Behörighetsbrist eller en ny Spotifybegränsning är inte påvisad.

Lokala prov med riktig FileBudgetStore och hela media-workerflödet har
återskapat en matchande felväg i den frysta API-klienten: ett lyckat control
med 200/202 och icke-JSON-svar kan följas av `JSONDecodeError`, tappad
bekräftelse/grant och väntan på nästa automatläsning. 204 med simulerad
icke-tom body visar samma kodväg, men är en syntetisk variant; verklig
stdlib kan behandla 204 som längd noll. **Den faktiska felklassen eller
responsformen i ovanstående driftsfel är ännu inte fångad.** Reproduktionen
är en matchande hypotes, inte bevis för den riktiga rotorsaken.

En [separat korrigeringskandidat](api-control-fix-2026-10-15.md) för
responsehantering och tillåten felklass/HTTP-status är nu byggd och fryst:
**CB31317492880698421BB0DEF7EEBCEAABEF7F8D13FA2C82318B2DB810C4A130**,
**19653708 byte**. Tio hela-worker-prov och 143 körda regressionstester
passerar; två befintliga C++-prov är överhoppade. Dessa är lokala prov,
inte fysisk acceptans. Klartecken för Projektledarens säkra byte är lämnat;
utfall från installation/knappomprov väntar.

Den installerade B8-versionen, profilen, ledgern och firmware har inte
ändrats av Kodskrivaren. Frysta B8-rapporter, källkopior och artifacts
bevaras. Projektledaren hanterar byte och nytt verkligt knappomprov.

## Sparad CPU-mätarpreferens

Projektledaren läste `diagnostics.esp32_cpu_meter_enabled=true` i sparad
config, byteidentisk med backup. Nystartens CPU-mätarstatus var aktiverad
med rapporterade **32 % / 5000 ms**, i enlighet med den sparade preferensen.
Projektledaren ändrade inte inställningen. Ett äldre volatilt statusvärde
`false` är inte underlag för att ändra den sparade profilen.

## CB313174 installerad och verkligt kontrollomprov godkänt

Projektledaren installerade den separat granskade bodyfixen, exakt
**CB31317492880698421BB0DEF7EEBCEAABEF7F8D13FA2C82318B2DB810C4A130**,
**19653708 byte**, **12:04:52.893565**. Start med dold `--startup` skedde
**12:04:54.446**. Endast installerade B8-processparet **81368/83756**
stoppades; nya processparet var **83208/79648**.

Stopp/kopiering gjordes under profilens gemensamma ledgerfil-lås med
**pending=0**. Ledger/config/tokenbackup hade stämpel
`pre-control-fix-20261015-120450`. Ledgerns förkopieringshash
`AF7FF539F5FAB4D8B5D94D0AA12BB0B1F816022BBEB466320D86835FD41F4EB2`
bevarades vid kopieringen. Config var byteidentisk (rapporterad hashprefix
E128…), credentials semantiskt bevarade och Windows Run-post oförändrad.
Deploymentprotokoll: `C:\Users\gusta\AppData\Local\BongoDesk\deployment-control-fix-20261015-120450.json`.
Firmware var fortsatt F406, utan flashning.

Projektledaren verifierade före bytet även 68 aktuella och 68 frysta
källhashar, 254 tidigare artifacts samt elva arkivmoduler och fyra resurser.

| Lokal tid | Verifierat utfall |
| --- | --- |
| 12:04:55.986 | `APP_START` |
| 12:04:58.149 | Serialanslutning, första försöket |
| 12:05:01.443 | art2-kapabilitet |
| 12:05:42.371 | Första GET efter bevarad lokal 60 s-väntan, ledgerförbrukning **25 → 26**; ingen pending-/clockspärr eller ny 429 |
| 12:06:32.438 | `NEXT_RX` |
| 12:06:33.972 | API-`MEDIA_TRACK seq2`, cirka **1,534 s efter NEXT_RX** |
| 12:06:34.065 | `ART_READY` |
| 12:06:38.703 | Första `PLAY_PAUSE_RX` |
| 12:06:39.240 | `ART_SENT`, **5172 ms** |
| 12:06:39.256 | ACK, **16 ms** senare |
| 12:06:43.346 | Andra `PLAY_PAUSE_RX` |
| 12:06:59.819 | API-källa, snapshotålder cirka **15 s**, sju API-anrop sedan omstart och sex senaste 30 s. Ledger totalt **32**, varav **23 automatiska**; kontrollrundan tillförde **sex explicita** kostnader. Reservationer **0**, warm/kvotgolv **60 s** bevarat, totalt 429 fortsatt **2**. ESP32 ansluten, statusålder **1,255 s**, heap ledigt **180036** / minimum **175916 byte** |

På frågan om NÄSTA/ny låt och omslag samt paus → play på mobil och skärm
svarade användaren: **”Japp nu funkar det.”** Detta är **kvalitativ
acceptans av de tre kontrollerna på CB313174/F406**, med uppmätt loggavstånd
för NEXT och kvitterad omslagsöverföring enligt ovan. Ingen separat fysisk
stopptidslatens för alla moment är påstådd. Den faktiska tidigare B8-
exceptionen eller svarsbodyn är fortfarande okänd.

CB-kandidaten, dess 68 källkopior/manifests och tidigare fixrapport är
frysta och ändras inte av dessa nya driftsfakta. Den fungerar som rollback
för den separat beställda [manuella statusläsningen](manual-api-refresh-2026-10-15.md).

## 1370651D installerad: väntetryck godkänt, automatisk mobilföljning släpar

Projektledaren installerade exakt
**1370651DF6FCC28D70FE4736B39818AA71F8BCEE13EF0992C90EC92EA97F7762**,
**19655597 byte**, **12:46:36.459225 +02:00**. CB-rollback verifierades.
Config/token/ledgerbackup och kopiering kontrollerades byteidentiskt under
det befintliga gemensamma ledgerlåset, med **pending=0** vid stopp.
Windows Run-post var oförändrad. Deploymentprotokoll:
`C:\Users\gusta\AppData\Local\BongoDesk\deployment-manual-refresh-20261015-124633.json`.

Efter start var config byteidentisk, credential-fälten access/refresh/
expiry/scope/type bevarade och Run-post fortsatt oförändrad. Firmware var
samma F406; ESP32 var ansluten och rapporterat minheap fortsatt **175916**.

| Lokal tid | Verifierad händelse/status |
| --- | --- |
| 12:46:39.153 | `APP_START` |
| 12:46:41.318 | Serialanslutning |
| 12:46:44.602 | art2-kapabilitet |
| Före/efter första auto | Bevarad ledger **74 totalt/61 auto → 75 totalt/62 auto** |
| 12:47:27.983 | Windows → API-vänteläge |
| 12:47:29.868 | Väntetryck `PLAY_PAUSE_RX` |
| 12:47:30.448 | API-`MEDIA_TRACK`, **0,580 s efter trycksignalen** |
| 12:47:35.568 | `ART_SENT`, **5062 ms** |
| 12:47:35.582 | ACK, **14 ms** senare |
| Efter väntetrycket | Ledger **76 totalt/62 auto**, alltså exakt **en ny explicit GET**. Reservationer **0**, fast **false**, Retry/clock **0**, totalt 429 fortsatt **2** |
| 12:48:31.019 | Nästa automatiska API-uppdatering, cirka **60,571 s efter manuella MEDIA_TRACK** |
| 12:48:32 | Effektivt intervall **60 s**, färsk API-ålder cirka **1 s**, ledger **77 totalt/63 auto**, reservationer/clock/Retry **0**, totalt 429 fortsatt **2** |

På frågan om snabb rätt låt, oförändrad musik och rätt omslag efter
väntetrycket svarade användaren: **”Japp allt”**. Detta godkänner den
manuella engångsläsningen och dess synliga resultat kvalitativt; loggen
ovan anger avståndet från seriell trycksignal, inte från fysisk nedtryckning.

Därefter rapporterade användaren **”Fast när jag bytar hänger den inte med
igen”**, förtydligat som byte på **mobilen** där **låttexten** ligger efter.
Nästa automatiska läsning och 60 s-statusen visar fortsatt lokal
återhämtnings-/warmprofil, inte en ny observerad HTTP 429 eller ett fel
på det manuella trycket/omslagstransporten.

En [separat aktiv dagpolicy](active-api-recovery-2026-10-15.md) är nu
granskad i lokala prov och fryst som **17466EBF/19656937 byte**: känd
daguppspelning följer valt 5 s-golv före pressure/högre backoff, med verklig
Retry-After, halva/75 %-budgetar och alla tak kvar. Den blandade 72 h-
simuleringen fick högst 5,12 s daggap, men kontinuerlig stress fick sämre
sen tail, högst 120 s. Det är simulerade mått, inte fysisk acceptans.

Inga skydd eller riktiga profil-/token-/ledgerdata återställs av
Kodskrivaren. 137:s EXE, 71 frysta källkopior/manifests och funktionsrapport
förblir orörda. Den senare 17466-installationen redovisas nedan; dess
fysiska API-mobilföljning väntar fortfarande på verifierat utfall.

## Pågående och återstående prov

### 17466EBF installerad, första kontrollerna endast Windows

Projektledaren installerade exakt
**17466EBFC95B14FDFB93D717BB9700F5937087AC27933CCDF82DF98E8C77C1C0**,
**19656937 byte**, **13:16:12.522090 +02:00**. Deploymentprotokoll:
`C:\Users\gusta\AppData\Local\BongoDesk\deployment-active-recovery-20261015-131610.json`.
Verifierad rollback:
`C:\Users\gusta\AppData\Local\BongoDesk\BongoDeskSpotify.backup-20261015-131610-pre-active-recovery-1370651D.exe`.

Det befintliga ledgerlåset hölls under stopp/kopiering, med **pending=0**.
Alla tre config-/token-/ledgerbackuper var hashverifierat byteidentiska
under bytet; ingen historik återställdes. Run-post, configbyte och
credential-fälten access/refresh/expiry/scope/type var oförändrade även
efter start. Projektledaren verifierade oberoende **75 aktuella/75 frysta
källor** samt **elva paketmoduler/fyra resurser**.

Nya normala processparet var parent **57080** / child **85540**. ESP32 var
ansluten med statusålder **1,53 s**, heap **180040** / minimum **175916 byte**.
Firmware var fortsatt F406, utan flashning.

**Spotify på PC var öppet efter start.** Status **13:16:30** och fem
stickprov **13:17:08–13:17:30** visade konsekvent `windows_spotify`,
ingen aktuell API-snapshotålder, ledger **79 totalt/65 auto**, reservation/
Retry/clock **0**, fast **false** och totalt 429 fortsatt **2**.

Detta verifierar installation/profilbevarande och native Windows-vägen
i status. Det är **inte uppmätt 5 s-API-pollning eller fysisk acceptans av
snabb mobilföljning**. Projektledaren har bett användaren stänga Windows-
Spotify, spela på mobilen och prova två mobilbyten med låttext och omslag.
Det senare mobilutfallet redovisas nedan. Fryst 17466-EXE, dess
källor/manifests och policyrapport ändras inte av denna notering.

### Automatisk API-mobilföljning godkänd 17:50–17:52

Användaren återkom 17:49. Projektledaren verifierade fortsatt exakt
17466-EXE och samma normala processpar **57080/85540**. Spotify på PC var
stängt; ingen ny 429 observerades (totalt fortsatt **2**).

| Lokal tid | Verifierad status/händelse |
| --- | --- |
| 17:50:31 och 17:50:37 | API-källa, `idle=true`, effektivt **30 s**, ledger **274 totalt/260 auto** |
| 17:50:43 | Växlat till `idle=false`, effektivt **5 s** |
| 17:50:48.849 | Automatiskt `MEDIA_TRACK seq17` |
| 17:50:49 | Ledger **278/261 auto** |
| 17:50:54.185 | Automatiskt `MEDIA_TRACK seq18` |
| 17:50:55 | Ledger **280/263 auto** |
| 17:51:01 | Ledger **281/264 auto** |
| 17:51:10.117 | Automatiskt `MEDIA_TRACK seq19` |
| Seq18-omslag | `ART_SENT` **5250 ms**, ACK **42 ms** senare |
| Seq19-omslag | `ART_SENT` **5342 ms**, ACK **12 ms** senare |
| 17:51:47 | Extra `PLAY_PAUSE` från skärmen |
| 17:51:50 | Extra NEXT, metadata **1,656 s** senare |
| 17:51:56 | Extra NEXT, metadata **1,324 s** senare; senaste cover **5266 ms**, ACK **46 ms** |
| 17:52:04 | API-källa, Windows inte tillgänglig, `idle=false`, effektivt **5 s**, API-ålder **0,36 s**. Ledger **299 totalt/276 auto**, halvbudget **4000/3600**, reserv/Retry/clock **0**, fast **false**, totalt 429 fortsatt **2**. ESP32 ansluten, heap **179984** / minimum **177088 byte** |

Reservationer, Retry och clock var noll och fast false i samtliga angivna
stickprov. Mellan de tre automatiska MEDIA_TRACK-händelserna fanns ingen
seriell RX från skärmen. Seq17:s äldre omslag avbröts med `track_mismatch`
när seq18 tog över; detta är förväntad ersättning av en gammal överföring.
Skillnaden mellan MEDIA_TRACK-tider mäter när nya låtar observeras, inte
samtliga HTTP-pollintervall.

På uttryckligt prov med mobilstart, två mobilbyten, rätt text inom ungefär
fem sekunder, rätt omslag och jämnhet svarade användaren:
**”Aa nu ser de rätt ut.”** Detta är **kvalitativ acceptans av automatisk
API-mobilföljning på 17466/F406**. Faktiska telefon-action-tidsstämplar och
end-to-end-latens är inte separat uppmätta. De extra skärmkontrollerna
ovan visar också fortsatt control-/omslagsfunktion, utan en ny separat
användarrunda för dessa. Ingen firmware flashades.

Därefter frågade användaren om **3 s i stället för 5 s** använder för mycket
API. Den [separata isolerade analysen](api-cadence-3s-analysis-2026-10-15.md)
är klar: åtta 72 h-fall med samma två traceformer visar snabbare lätt
användning men tidigare budgettryck och sämre p95 under lång uppspelning.
Rekommendationen är **behåll 5 s generellt**. Installerad kod, standard och
faktisk profil behåller befintlig takt; inget driftprov av 3 s har gjorts.
Frysta artifacts och tidigare funktions-/policyrapporter är bevarade.

### Samlad provstatus

| Prov | Status |
| --- | --- |
| Exakt kandidat installerad, rollback/profilbevaring | Verifierat av Projektledaren enligt ovan |
| Uppstart, första serialanslutning, art2-kapabilitet/överföring | Loggverifierat enligt ovan |
| API-väg från mobil | 137:s manuella API-snapshot/omslag och **17466:s automatiska API-mobilföljning kvalitativt godkända** |
| Mobilbyte, faktisk upptäcktstid och uppdaterat omslag | 137-väntetryck: 0,580 s signal → metadata. 17466: mobilstart/två automatiska byten, rätt text/omslag/jämnhet godkända; ingen fysisk end-to-end-stoppursmätning |
| Explicit NÄSTA, paus/play, reserv och bekräftelseläsning | B8-regression dokumenterad; omprov med **CB313174/F406 kvalitativt godkänt**, inklusive nytt omslag |
| Manuell statusläsning från vänteläget | **1370651D/F406 installerad och kvalitativt godkänd**, exakt en extra explicit GET och rätt omslag |
| Fortsatt automatisk mobilföljning | **17466/F406 godkänd** i ovanstående prov. Sparad halvbudget/återhämtning kvar, effektivt 5 s vid spelande och 30 s idle observerat |
| Möjlig 3 s-takt | Isolerad 8-fallsanalys klar; rekommendation **behåll 5 s generellt**. Ingen implementation, installation eller verklig taktändring gjord |
| Fysiskt UI, tid/statistik, panelmeny, gester och DJ | Ingen separat komplett genomgång av 17466/F406. Tidigare CB-controls och 137-väntetryck/omslag redovisas ovan |
| Långdrift, initialt historikdygn och dag/natt | Väntar |
| Windows sleep/resume och serialåteranslutning/återsynkning | Väntar med denna companion |
| Sömn/väckning, ljusblixt och återställt innehåll | Ingen ny fysisk acceptans med detta installerade par dokumenterad |
| Seek-skärmprov | Fortsatt uppskjutet; separat fryst seek-firmware har inte flashats här |

Simuleringar och tidigare användarobservationer av F406/68CC ersätter inte
drift-/hårdvaruprov med B8C7BB28. Den korta sessionen ovan ger inget löfte
om långsiktig 429-frihet eller viss API-/omslagslatens. Senare verifierade
observationer läggs till i denna driftrapport efter Projektledarens underlag.

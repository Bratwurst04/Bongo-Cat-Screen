# Produktgranskning och första förbättringspaketet – 2026-10-20

## Status och avgränsning

Baslinje: `2b579b329ba491e352a01f1dad6a81381eb0246c`, därefter grenen
`codex/product-hardening`. Appen är uppdaterad; installerad firmware **EBB334A9**
är oförändrad. Firmwarekällan har separat labeleffektivisering och en gated
mätprofil, båda endast byggda. Ordinarie serialkontrakt, rotation/full
invalidiering, touch/fonter och releasefiler bevaras. Diagnosprofilen har extra
gles numerisk TX; den är av i övriga profiler. App-v1.3 är senaste release.

### Senast: C42112AD installerad; spelstatus rätt, rullningsfel öppet

Lead har installerat **C42112AD/EBB334A9 vid 921600** efter verifierad B701-
ZIP-backup och tre aktuella profilbackuper. Noll väntande API-reservationer vid
stopp; endast EXE byttes och aktuella config/auth/budget bevarades byteidentiskt.
Run och båda genvägarnas mål/argument/arbetsmapp var korrekta och oförändrade.
Faktisk Startmenygenväg startades via Explorer. Första tidiga observationen hade
en bootloaderprocess; den senare hade två normala PyInstaller-processer.

Andra observationen **13:35:14,692 +02:00**: statusålder 0,165 s, ansluten ESP,
Windows Spotify tillgängligt/aktiv källa, lokalt API-tillstånd `ready`.
Installerad hash, config, access-/refresh-/expiry-fält, Run och genvägar var
fortsatt oförändrade. Ingen privat journal lästes av Code. Leads innehållsfria
tvåobservationssammanställning har SHA-256
`A662C1EBD66D9C0418AF216B9580351EACBF134DAC7F3AEC7FA4DB55E07EBCF4`.

Första anslutningen lyckades på första försöket. Bas+REFINE följdes av faktiskt
observerade `ART_COMPACT_CAPABILITY`/`ART_COMPACT_INFERRED`-händelser. Det bevisar
en inference-kodväg i drift, inte vilka råa UART-rader som saknades eller varför.
Fyra kompakt READY→ACK var **541/459/479/640 ms**; tre full SLOT→ACK var
**3099/3118/3937 ms**, första försök. Sändtid: kompakt 240–241 ms, full
3017–3019 ms. Två NEXT-mottagningar följdes av lyckad `MEDIA_CONTROL` i logg.
Detta är transport-/kontrollbevis, inga LCD-tider eller generella fartgarantier.

Användaren bekräftade exakt **”Spelstatus rätt, rullningen rycker fortfarande”**
och sedan **”Den rycker inte när den är pausad”**, även mer än tio sekunder
efter färdigt omslag. Ny PLAY/PAUSE-status är snävt accepterad. Ingen utökad ny
acceptans av omslag/skärpning/animationer följer av det svaret. Rullningsfelet är
öppet; aktiv vinylrotation/renderbelastning är nu en starkare hypotes än enbart
tresekundersmetadatan. Separata oflashade mätkandidater är nu byggda; ingen
rotations-/render-/font-/touchändring eller ny firmwareflash ingår i appbytet.

### Separat firmware – endast byggd, ingen rullningsfix påstås

Normal labelkandidat **B846FF52**, 937 360 byte, och separat diagnoskandidat
**D7DA9953**, 938 192 byte, är byggda/granskade vid 921600, appoffset 0x10000.
Båda är **oflashade**, C421-EXE och installerad EBB är bevarade. Nativeprov
verifierar färre redundanta setteranrop och mätackumulatorn; inte faktisk LVGL-
fas eller jämnare rullning. Ordinarie profil saknar mätkod/symboler, diagnosen
har RAM-histogram/max och anonyma rader högst var 15:e sekund.

Slutlig ren källkontroll: **368 funna/359 PASS/nio klassade SKIP/noll fel och
noll blockerade operationer**, inklusive fem label- och sex ackumulatorprov.
38 firmwarepins, bibliotek och offline-imagevalidering PASS; Root granskade
kandidaterna oberoende. Se [fulla hashar, format och separat flashgrind](render-measurement-2026-10-20.md).
Inget nytt firmwaregodkännande eller fysiskt mätresultat antas av bygget.

### Bakgrund: 092E4E7D underkänd och B701 återställd före C421

Den första installerade kandidaten **092E4E7D underkändes i verkligt prov**:
Spelaren visade paus trots pågående uppspelning. Lead återställde exakt
**B7019579/EBB334A9 vid 921600** 13:26:42. Nuvarande profiler/auth/budget
behölls; credentials återställdes inte till äldre värden. Run/genvägar var
oförändrade och Startmenygenvägen startades på nytt. 092 och privata backuper
bevaras; den tidigare korta uppstartsobservationen nedan är historik.

Efter återställningen bekräftade användaren att B701 fungerar igen men beskrev
texten som ”lite hackig” och preciserade senare att **rullningen rycker**.
Orsaken utreds skrivskyddat separat; ingen text-/firmwareändring ingår här.
Leads innehållsfria B701-prov 13:28 visade rätt apphash, statusålder 0,763 s,
ansluten ESP och aktiv Windows Spotify. Det är en återställd driftfunktion,
inte en ny acceptans av textkvalitet eller C421.

Rotorsaken är reproducerad med verklig WinRT-enum utan privata metadata:
`PLAYING` har värde 4. Python 3.10 gav enumens namn via `str()`, medan 3.13 ger
`"4"`. Den äldre `endswith("PLAYING")` gav därför falskt på den nya byggbasen.
Lead verifierade även en verkligt spelande SMTC-session med typad jämförelse
sann och äldre strängjämförelse falsk. Se
[Python IntEnum-ändringen från 3.11](https://docs.python.org/3.13/library/enum.html#enum.IntEnum).

Minimifixen importerar den verkliga statustypen och jämför `PlaybackStatus.PLAYING`
i `_read_session` och `_find_media_sources`. Inga API-/pacing-/UI-/firmwareändringar.
Fyra nya regressioner använder verkliga PLAYING/PAUSED/STOPPED-värden och provar
snapshot→seriell state, samma låts play/pause/play samt sessionval. Tre äldre
testfixtures använder nu samma riktiga typ. **31 fokuserade prov PASS**.

Rättad **byggd, paketgranskad och nu installerad** kandidat:

- SHA-256: `C42112AD2C774B0814B40B688AE8FA80BD0858D1308DA9130719362492CAC135`.
- **22 856 796 byte**, Python 3.13.16/Pillow 13.0.0/PyInstaller 6.22.3.
- `dist/companion-2026-10-20-winrt-playback-fix-dev/BongoDeskSpotify.exe`.
- Ny separat r5-frysning med 25 publika filer, 14 matchade produktmoduler och
  sex byteidentiska resurser. Source-SHA:
  `1D430C1178BA0F9D62419B13D766C6F23C850F5488B8B9093AF71C69A7F9A5FE`.
  Paketkvitto-SHA:
  `6C6771EBF1EE07C12D893736F8A05976DFBEC41F4AD50732E8536EAD73E92DA9`.
  Leads oberoende arkivgranskning PASS, kvitto-SHA:
  `5CB5A63A6ED0624121C7A9AB3CAB6148BF19F275EBAC356E93F9E4D3C4F9721A`.
- Ren omkörning på exakt 3.13.16/Pillow 13.0.0: **357 funna/348 PASS/nio
  klassade SKIP/noll fel och noll blockerade operationer**. De fyra nya
  enumproven passerar även separat. Summary-SHA:
  `355FC8F7260C41AE65D968585DED9AA6FB7379A7CEB9FA44997B7CA6D01B577E`;
  källmanifest-SHA:
  `8055DFAB28A764714E1E858BE787ABB7FF8DE67A957A506946ACB3921F253F59`.
- Ny snäv PLAY/PAUSE-acceptans finns enligt senaste driftavsnittet ovan;
  rullningsfelet är fortsatt öppet. Ingen acceptans följer av det tidigare
  gröna värdtestet; strängmockar missade felet.

### Tidigare kandidat 092E4E7D – bygg- och installationshistorik

- SHA-256: `092E4E7D2250FDAB9E74EB1BC3F82F9818A37335CE3C6ABE1899C5F50E84683B`.
- Storlek: **22 856 667 byte**.
- Lokal kandidat: `dist/companion-2026-10-20-product-hardening-dev/BongoDeskSpotify.exe`.
- Byggbas: officiell **CPython 3.13.16**, **Pillow 13.0.0**, **PyInstaller 6.22.3**.
- Lead installerade appen **13:19–13:21 Stockholm**. Denna version återställdes
  senare till B7019579 efter det underkända fysiska provet ovan.

Detta är ett avgränsat rättningspaket och en produktbedömning. Det är inget
intyg om full säkerhet, Spotifygodkännande eller färdig kommersiell produkt.

## Rättat i källan

| Område | Reproducerat problem och åtgärd |
| --- | --- |
| Start utan skärm | Misslyckad första anslutning stängde appen. Tray, Settings och lokal media fortsätter nu; befintlig femsekundersstyrd återanslutning används med samma reader/sender. |
| Automatisk port | Flera enheter kunde ge `input()` i en fönsterapp eller godtyckligt förstaval. AUTO väljer nu endast en entydig enhet, även vid återanslutning; annars krävs uttrycklig COM-port. |
| Inställningar | Python kunde trunkera aktiv JSON och sedan förstöra bra backup. Unik tempfil, flush/fsync och atomiskt byte skyddar aktiv fil; endast validerad aktiv fil får ersätta backup. Giltig backup kan återställas, okända fält bevaras. |
| Aktivt Settings-fönster | COM-port och baud finns nu i den använda WinForms-vägen. Ändring kräver appomstart. Sparning läser färsk JSON, ändrar bara berörda UI-fält och använder unik tempfil/atomiskt Windows-byte. Ingen liveapply eller OAuth-GUI utlovas. |
| OAuth-callback | Ett orelaterat anrop kunde avsluta länkning. Exakt GET-sökväg/Host, enstaka parametrar och state kontrolleras nu; ogiltiga anrop lämnar flödet öppet till monoton deadline. Accepterad socket har både kort lästimeout och total deadline. Servern stängs alltid. Webbsidan säger endast att svaret mottagits före tokenutbytet. |
| Tokenägarskap | CLI-länkning och Client-ID-skrivning låg före instanslåset. De kräver nu låset före profiländring/OAuth; en redan körande app ger tydlig felåterkoppling även i fönsterläge. |
| Tokenintegritet | Unika atomiska tempfiler och validerade tokenfält/expiry ersätter statisk tempfil och okontrollerat payload. JSON är begränsad till 2 MiB, 32 strukturled och 50 000 noder. Fel återställer gammalt minne och lämnar fungerande fil orörd. Korrupt auth ger neutralt fel och lokal media fortsätter. |
| HTTP och bilder | Autentiserade anrop går endast till fasta Spotify-HTTPS-origins och följer inga redirects. JSON-läsning begränsas; felbody visas inte. Omslag hämtas separat utan Bearer, högst 8 MiB, och avkodas endast som stilla JPEG/PNG, högst 4096 per sida och 16 777 216 pixlar. Normal JPEG/PNG-konvertering och gemensam kompakt/detaljcache bevaras. |
| Byggning och leverans | Ny aktuell Python/Pillow-bas, avgränsad ren checkout-runner, CI med SHA-pinnade actions och läsbehörighet samt Dependabot-konfiguration. Projektets LICENSE och THIRD_PARTY_NOTICES ingår uttryckligen i EXE:n. |

PKCE S256, slumpmässig state, extern webbläsare och loopbackbindning fanns redan
och har behållits. Ingen förbikoppling av state/PKCE eller kontokapning visades.
Ursprunglig urllib-logik kunde behålla Bearer vid originbyte/HTTP-redirect; detta
var ett verifierat biblioteksegenskapstest, **ingen påvisad skadlig Spotify-redirect**.
Se [Spotify PKCE](https://developer.spotify.com/documentation/web-api/tutorials/code-pkce-flow)
och [RFC 8252](https://datatracker.ietf.org/doc/html/rfc8252).

## Första 092-paketets verifiering och bevisgränser – historik

- Fokuserad backend på nya 3.13-grenen: **100/100 PASS**; därefter sista
  auth/config-regressionerna **24/24 PASS**, inklusive djupt skadad JSON.
- Separat säkerhetsgranskare: sju felprov och **16 säkerhetstester PASS**.
  Verklig lokal socketpair med långsamma byte stoppades efter cirka 0,313 s
  mot en 0,30 s deadline. Detta är inget verkligt Spotify-inloggningsprov.
- UI: **72 nya + 580 befintliga kontroller PASS**, samt pacingformattering,
  med syntetiska profiler och isolerat WinForms-fönster. Verklig användning av
  det nya portfältet och mänsklig tillgänglighetskontroll återstår.
- Bred slutkontroll på exakt **3.13.16/Pillow 13.0.0** från en ny källsnapshot:
  **353 funna, 344 PASS, nio klassade SKIP, noll fel och noll blockerade
  externa operationer**. Första passets enda fel var ett äldre WEBP-test;
  det verifierar nu avsiktlig avvisning. JPEG/PNG-bytejämförelser ligger kvar.
  SKIP gäller sex frånvarande historiska arkiv, ett privat fotoreferensprov
  och två dokumenterade värd-/SDK-begränsningar; aktuella beteendeprov kördes.
- Arkivet: **14 produktmoduler** jämförda med kompilerad fryst källa,
  **sex resurser** byteidentiska. Python-DLL matchar officiell runtime,
  Pillow-version och Tcl/Tk-resurser är kontrollerade. Tomt standard-Client-ID;
  inga privata profil-/tokenresurser. Lead gjorde en oberoende arkivjämförelse.
- Ingen riktig profil/token lästes i kodgranskningen, inga Spotify-API-anrop,
  ingen COM-anslutning, kandidatstart eller firmwareflash utfördes av Code.
  Leads efterföljande driftunderlag redovisas nedan; fysisk acceptans är separat.

## Historik: Lead-installerad 092 och kort driftkontroll före underkänt prov

Lead ersatte den kanoniska Windows-appen efter verifierad B7019579-ZIP-backup
och tre privata profilbackuper för config/auth/budget. Noll väntande API-
reservationer vid stopp. Installerad hash/storlek matchar kandidaten ovan.
Ingen profil ändrades vid själva bytet. Firmware **EBB334A9/921600** bevarades;
ingen firmware skrevs.

Båda befintliga Startmeny-/skrivbordsgenvägars mål, `--minimized` och arbetsmapp
kontrollerades; genvägsfilerna var oförändrade. Faktisk Startmenygenväg startades
via Explorer. Två normala PyInstaller-processer observerades. Huvudprocessens
Explorerförälder bekräftades vid första observationen; startstubben hade avslutats
vid den andra, vilket inte var ett nytt startfel.

| Lokal observation 2026-10-20 | Resultat |
| --- | --- |
| 13:21:08 +02:00 | Status 0,019 s gammal; ESP ansluten, Windows Spotify tillgängligt/aktiv källa. |
| 13:21:54,515 +02:00 | Status 0,654 s gammal; fortsatt ansluten och Windows Spotify aktiv källa. Lokalt API-tillstånd `ready`, inget tokenfilfel. |
| Integritet vid båda | Installerad apphash, config, access-/refresh-/expiry-fält, Run och båda genvägar verifierades oförändrade. Inga tokenvärden ingår i rapporten. |

Första serialanslutning lyckades **13:20:59**, första försök. Explicit bas och
COMPACT kom före READY. Första kompakta överföringen var 12 800 byte:
READY **13:21:02,308** till ACK **13:21:02,938**, **630 ms**; sender 241 ms.
Den befintliga engångs-CAPS-resenden 13:21:10,068 fick bas+COMPACT+REFINE.
Ingen SLOT/full-ACK fanns ännu i dessa uppstartsobservationer. Siffrorna visar
transportkvittens, inte faktisk LCD-tid, ny skärpningsacceptans eller en allmän
ensekundsgaranti. Lead gjorde inget separat Spotify-API-anrop.

Källa är Leads två innehållsfria driftobservationer. Sammanställningens SHA-256:
`2F0C3B1878563715C98CE82111C9CD570785DE21D316B8D5D670AC1FF68AAA49`.
Privat installationsjournal/profilbackuper lästes inte av Code och publiceras
inte. Efter dessa observationer underkände användaren pausstatusen; Lead
återställde B701 enligt statusavsnittet ovan. Ingen acceptans av 092 påstås.

Frysta bygginput: 25 publika filer; manifest-SHA
`B9FA171CA9F4A09E693A56044D58C8AE44848EBA537CCC0B25D6E0B6EA1B34CA`.
Paketkvitto-SHA:
`6851D475250AA6124E4494F87BD9F4A13E6195ECD7E0A868E61D5A3859EE0AB3`.
Slutsvitens summary-SHA:
`8EA44CA94922D2B149BCD684477FDF4AF565F67C0C5DF813242367853FFE58A5`;
dess källmanifest-SHA:
`80D8F0EFC0A6CFF4702830C7B25B758DD18DB8D66F05B263B43A40C438C971E7`.
Lokala bevis finns under `build/product-committee-2026-10-20/`, inklusive
`app-package-r4/`, `code-audit/`, `security-peer/`, `ui-hardening/` och
`quality-delivery/`. Tidigare r1/r2/r3 är bevarade men ersatta mellanbyggen;
de ska inte installeras. Efterföljande användardokumentation ändrar inga
paketerade kod-/resursbytes.

Officiell full runtime-ZIP hämtades utan installerare eller registerändring.
Publicerat manifest och ZIP verifierades mot SHA-256; Python EXE/DLL hade giltiga
PSF-signaturer. ZIP-SHA:
`BBF675BB5E763C1EFBB09A3A461B259D81598A63C30C4B0D7EA11B9F063DF159`.
Tcl 8.6.15/Tk 8.6 finns kvar. Äldre installerad Python lämnades orörd.
Källor: [Python 3.13.16](https://www.python.org/downloads/release/python-31316/),
[Windows-manifest](https://www.python.org/ftp/python/3.13.16/windows-3.13.16.json),
[Pillow 13 säkerhetsändringar](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html).
Ingen FPX-exploatering eller annan kodkörning demonstrerades; `olefile` saknas
i granskade paket och ingen multiframe-seek-väg påvisades. Formatbegränsningen
ersätter inte biblioteksuppdateringen.

## GitHub och läckagegranskning

Skrivskyddad granskning av 15 nåbara commits, 779 unika blobs och fyra uppackade
Windows-releasepaket hittade **ingen bekräftad levande credential**. Det är ett
begränsat resultat från anpassade kontroller, inte bevis för att allt är fritt
från hemligheter. Privata profiler, oåtkomliga refs/forkar och verkliga credentials
ingick inte. Client-ID är en offentlig klientidentifierare, inte Client Secret.

Leads direkta GitHub-API-verifiering 2026-10-20 12:57 Stockholm: vulnerability
alerts och private vulnerability reporting aktiverades. Repo är fortsatt publikt;
secret scanning och push protection är aktiva. Automatiska security-fix-PR:er är
avstängda. Noll öppna Dependabot-alerts vid kontrollen avser **defaultgrenen main**,
inte hela denna featurebranch eller frånvaro av sårbara beroenden. CI- och
Dependabot-filer i källan är separata från framtida fjärrkörningsresultat.

## Rekommendation och nästa prioriteringar

Behåll publik källkod och utveckla främst en gratis hobbyprodukt med en användbar
lokal kärna: Bongo, Fokus och systeminformation. Spotify API-läget är fortfarande
en experimentell integration. Första paketet rättar konkreta fel; bred distribution
och betalning kräver fler beslut:

1. **Credentials:** separat DPAPI/Credential Manager-lager med verifierad migrering
   och återställning. Tokens och privata backuper är fortfarande klartext; inga
   faktiska profil-ACL granskades. Skydd mot komprometterad samma användare kan
   inte utlovas. Se [Security](../SECURITY.md) och [Privacy](../PRIVACY.md).
2. **Kontolivscykel:** lättåtkomlig länkning/frånkoppling och användarkontroll i den
   aktiva appen. Nu finns bara skyddad CLI-länkning och manuella instruktioner.
3. **Distribution:** full transitiv beroendelåsning med integritetshashar,
   reproducerbar inventering, signerad proveniens/EXE och lämpliga obligatoriska
   main-/releasegrindar. CI-källan är inget påstående om körd/passerad GitHub CI.
4. **Spotify:** klarera åtkomstmodell, attribution/återlänkning och omslagsvisning
   före bred release. Development Mode har begränsad allowlist; publik källkod
   ger inte automatiskt en allmänt tillgänglig API-tjänst. Cirkulär beskärning,
   animation och overlays behöver hanteras mot designreglerna. API-styrning av
   en bakgrundsspelare räknas in i Spotifys Streaming-definition, som påverkar
   kommersiell användning. Ingen betalvägg eller donationsdispens för denna
   integration har klarerats. Detta paket ändrar ingen grafik eller affärsmodell.
   Källor: [Quota modes](https://developer.spotify.com/documentation/web-api/concepts/quota-modes),
   [Developer Terms](https://developer.spotify.com/terms),
   [Developer Policy](https://developer.spotify.com/policy),
   [Design Guidelines](https://developer.spotify.com/documentation/design).
5. **Licenser:** de två medföljande projekttexterna är början på en inventering.
   Full LGPL-hantering för pynput/pystray, transitiva paket, fontlicenser och
   grafikursprung behöver verifieras för distributionsformen. Projektets MIT
   överför inte Spotifyinnehåll eller okända tredjepartsrättigheter.
6. **Drift:** fysisk regressionskontroll av ny app, långkörning, Windows sleep/
   resume, mörk väckning, touch och samma omslag efter återanslutning. Den äldre
   Waiting-/bakgrundsutredningen är pausad och förklaras inte löst av detta paket.
7. **Lokal processhårdning (P3):** Settings startas med en säker argumentvektor,
   men `powershell.exe` anges utan absolut systemsökväg. En senare liten ändring
   bör välja betrodd Windows-sökväg och testa lokalt manipulerad arbetsmapp/PATH.
   Ingen kommandosträngsinjektion, elevation eller fjärrkodkörning påvisades.

### Kort fysiskt efterprov för ny companion – väntande

1. Starta den vanliga Windows-genvägen utan skärm: tray/Settings ska finnas.
   Anslut sedan skärmen; den ska återansluta utan extra reader/sender. Prova
   uttrycklig port/baud i Settings med Exit/omstart och rätt firmwarehastighet.
2. Låt companion gå under mer än tio minuters tangentbordsinaktivitet. Skärmen
   ska förbli vaken. Stoppa sedan appen: efter tio minuter utan aktuell trafik
   ska den äldre firmwarelogikens bakbelysning/LCD/deep sleep observeras separat.
3. Prova shutdown och Windows sleep/resume med kvarvarande USB-ström. Observera
   mörka timerväckningar, eventuell ljusblixt och mät tiden från återupptagen
   companiontrafik till normalt UI; målet är högst 60 sekunder.
4. Kontrollera aktuell tid/statistik, samma låts omslag efter väckning, Spelarens
   tryck/svep/DJ, långtrycksmeny, panelbyte och Fokus/TIDER. Bygg-/värdtester
   ersätter inte dessa observationer och inget nytt flashprov ingår här.

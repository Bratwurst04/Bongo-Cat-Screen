# Överlämning: Bongo Cat Project Lead 4 → Lead 5

**Historisk överlämningsbild före normalflashningen senare samma dag.**
Aktuell installation och efterprov finns i
[driftrapporten för C421/61BE](render-viewport-runtime-2026-10-21.md).
Tidigare installations-/föreflashuppgifter nedan bevaras som historik.

**2026-10-21, Europe/Stockholm.** Användaren har begärt en ny Lead-chatt och
fortsatt arbete där samt en utredning av bildkvalitet, kontrast, mättnad och
eventuellt behov av annan panel. Detta dokument sammanför befintliga bevis.
Ingen ny driftavläsning, installation, COM-åtkomst, flashning eller provning
har gjorts för överlämningen. Observationen 20 oktober är historisk.

## Roller och arbetsyta

| Chatt | ID och ansvar |
| --- | --- |
| Avgående **Bongo Cat Project Lead 4** | `01a14061-2445-7cc0-9178-79fb0625be18`; lämnar över planering och runtimeansvar |
| Ny **Bongo Cat Project Lead 5** | `01a15d81-3c6d-7a31-8214-6f80e8645c20`, host `local`; har läst befintligt projektunderlag och meddelat övertaget runtimeansvar |
| **Code 2 / Kodskrivaren** | `01a0ec49-da6f-7b00-be86-06822053344a`; avgränsade kod-, gransknings- och dokumentuppdrag |
| Befintlig **UI** | `01a11581-4a2c-7e80-9742-adcd989df5ca`; UI-underlag och layoutgranskning |
| **Idébollplank** | `01a14fba-80ff-7eb1-b3a0-d75492f7bdc3`; idéer, produktväg och beslutsunderlag |

Arbeta endast i **`D:\DEV\Ai\Github\Bongo-Cat-Screen`**. Använd inte
OneDrive-kopian. Lead planerar, granskar och delegerar produktkod/dokument till
Code samt UI till UI-chatten enligt [CHAT_ROLES](../CHAT_ROLES.md). Lead 5 är
nu ensam runtimeägare; samordna appstopp, COM och eventuell flash där.
Code läser inte privata profiler eller installationsjournaler på eget initiativ.
Denna nya handoff lämnas nu för Leads slutgenomläsning.

Vid nästa överlämning: bedöm behovet under aktivt arbete, låt Code spara ett
daterat underlag, skapa efterträdare inom användarens tillstånd och invänta
bekräftad läsning/ansvarsövergång. Ingen bakgrundsbevakning utlovas.

## Användarbeslut och tillstånd

- Produktinriktningen är **Windows-app och firmware**. Användaren vill hålla
  källkoden publik och utreda bästa produktväg. **Gratis hobbyprodukt först är
  kommitténs rekommendation**, inte ett bindande användarbeslut om gratisdistribution.
  Ingen ny release, merge eller tagg är beställd.
  `app-v1.3` är senaste publicerade release, skild från utvecklingskandidaterna.
- **Seek är borttaget** på användarens begäran. Den äldre handoffen från
  15 oktober beskriver då väntande seek och är historik. Återinför det inte.
- **Waiting-/bakgrundsutredningen är pausad.** Senare apphärdning eller
  bild-/renderarbete innebär inte att Spotifyproblemet är löst.
- Bevara Bongo, Fokus, panelmeny, befintliga touchgester, mediekontroller, DJ,
  svensk åäö-text, Windows-/Spotifyflöde, normal serialtrafik, kompakt omslag,
  refinement och mörk väckning. Undvik stora omskrivningar.
- Den stående companioninstruktionen i CHAT_ROLES gäller färdiga normala
  uppdateringar inom beställt arbete: Lead bygger/testar/granskar, tar verifierad
  backup, bevarar aktuella profiler/auth/budget/Run, ersätter den kanoniska
  `%LOCALAPPDATA%\BongoDesk\BongoDeskSpotify.exe`, verifierar SHA och kontrollerar
  Startmeny-/skrivbordsgenvägar samt verklig start från samma appikon.
  Upprepa inte en redan täckt appinstallationsfråga för varje ny apphash.
- **Ny firmwareflash kräver separat uttryckligt godkännande för konkret binär.**
  Appinstruktionen ger inget flashgodkännande. D7DA:s tidigare mät-/återställnings-
  cykel är avslutad; dess avgränsade tillstånd gäller inte 61BE/1252.

## Exakt senast installerat

Följande installation är bekräftad av Leads tidigare säkra kvitton; den har
inte lästs om från datorn/enheten den 21 oktober.

| Del | Storlek | SHA-256 |
| --- | --- | --- |
| Companion **C42112AD** | 22 856 796 byte | `C42112AD2C774B0814B40B688AE8FA80BD0858D1308DA9130719362492CAC135` |
| Firmware **EBB334A9** | 937 184 byte | `EBB334A926709E047DA1D930684C76D02DFA162332C508E775F062AE492E2FF3` |

- Kanonisk app: `%LOCALAPPDATA%\BongoDesk\BongoDeskSpotify.exe`.
  Bevarad kandidat: `dist/companion-2026-10-20-winrt-playback-fix-dev/BongoDeskSpotify.exe`.
  C421 byggdes med Python 3.13.16/Pillow 13.0.0 och rättar två verkliga
  WinRT-enumjämförelser. Den tidigare 092-kandidaten underkändes fysiskt.
- EBB har progressivt omslag med kompakt först och senare 112-detaljbild.
  Normal anslutning är **COM6/921600**, appoffset **0x10000**; flashhastighet
  och driftshastighet har olika uppgifter. Ingen port har öppnats här.
- Senast bekräftade **CPU meter är av (`false`)**. Den grova idle-tick-diagnosen
  är ingen exakt CPU-/task-/FPS-mätare och ska inte lämnas på av gammal vana.

### D7DA-cykeln är avslutad

Lead provade tillfälligt mätbinären **D7DA9953**, 938 192 byte, SHA
`D7DA9953E85449685912005B4062F9F15A8BCA720A9861781EFB946CCDE66B82`,
med syntetiskt innehåll och återställde sedan den ursprungliga appsektorbackupen.

- Backupen omfattade **942 080 byte vid `[0x10000,0xF6000)`**, med exakt EBB-prefix
  och ursprunglig sektorsvans. SHA:
  `855CAF3A40715512E46D4B1EC5FA0367E75E0AFD35A8940897E48E1F233DD896`.
- Återställning: 43,047 s, exit 0, `Hash of data verified`. Ingen bootloader/NVS
  skrevs. C421, aktuella profiler/auth/budget, Run och båda genvägarna bevarades.
- Efter vanlig Startmenystart och manuell RESET lyckades andra anslutningsförsöket;
  det första skedde medan bootstubben låg kvar. Kontakt, resync, fullbilds-ACK och
  senare kompaktkapabilitet loggades.
- **Senaste säkra driftobservation: 2026-10-20 kl. 14:56:25,996 svensk tid**:
  statusålder 0,957 s, ESP-statusålder 0,596 s, uptime 70 s, ansluten ESP,
  Windows Spotify aktiv och API `ready`. Detta är **inte färsk status 21 oktober**.
- Användarens fysiska kontroll efter återställningen **väntar fortfarande**.
  Tidigare snäv acceptans av rätt PLAY/PAUSE-status bevisar inte återställd
  bild-/gestfunktion idag eller en åtgärdad ryckig rullning.

## Nya viewportkandidater – endast byggda

| Kandidat | Storlek | SHA-256 | Lokal leverans |
| --- | --- | --- | --- |
| Normal **61BE3B63** | 937 600 byte | `61BE3B633AF700B27F0DDF55F9B26D41E1B9E0916F187848A470B50988701440` | `dist/firmware-2026-10-20-render-viewport-dev/normal-compact80.bin` |
| Diagnos **1252EBAC** | 938 400 byte | `1252EBAC2C3CBFEC4915DADB172CC06DB5799DF7E0482B17710E474DD4274C33` | `dist/firmware-2026-10-20-render-viewport-dev/render-diagnostics.bin` |

**Ingen av dem är flashad eller fysiskt accepterad.** Båda använder 921600 och
appoffset 0x10000, DIO. Normalprofilen saknar diagnossträng/symboler; diagnosen
har tre relevanta symboler. Oberoende offline esptool gav giltig checksumma och
valideringshash för båda. Ingen ny companion ingår.

Fryst källa/build/cache/libdeps: `build/product-committee-2026-10-20/render-viewport-r1/`.
**38 källpins och 3042 bibliotekspins** matchar. Källmanifest-SHA:
`3D535775DEC303DF452ED9534EC09AA7595EEF275A710D7FD50E83371ACAA414`.
Byggkvitto `firmware-verification.json`, SHA:
`41F456AADFFB156136AE0463689B1FA8391523C304243944B45CA681F87DDF96`.
Leveransmanifestet är `dist/firmware-2026-10-20-render-viewport-dev/candidates.json`.
Tidigare skyddade r2:s 38+3042 pins, manifest och B846/D7DA-binärer är bevarade.

Viewporten är transparent/rektangulär; bilden är permanent barn. Overflow tillåts
under förändring, arm/tass förblir skärmsyskon ovanpå och gamla transformerade
gränser invalidieras före klipp-/layoutbyte. Full art-box-invalidering bevaras.
60 ms/18 vinkelenheter och RX/CRC/cache/refine-kontraktet ändras inte.

### Vad hostproven faktiskt visar

- **2930 positiva jämförelser** av ny inkrementell flushrekonstruktion mot ny
  full omritning är bitexakta. Negativkontrollen fyller **hela 112×112-slotten
  vit utan invalidiering** och upptäcker avvikelsen; enpixelskänslighet provas inte.
- Globala koordinater/pivot/zoom kontrolleras separat mot den gamla formeln.
  Legacy-scenen jämförs exakt i projektion och på returframen efter avbrott.
  Själva avbrottsframen jämförs exakt mot **ny full omritning**, utan legacyjämförelse.
- Isolerad stadig gammal/ny sampling tillåter symmetriskt högst en displaypixel
  till samma färg och högst 32 avvikande pixlar per bild. Uppmätt max är 5 för
  112 och 30 för 56-fallback; gammal/ny rotation är inte rasterbitidentisk.
- 400 syntetiska rotationer gav 11 368 000 flushpixlar mot 17 828 796 med äldre
  parent, ungefär **36 % mindre syntetisk flushyta**. Detta är **inte TFT-tid,
  FPS, CPU eller fysisk jämnhetsacceptans**. Ytterligare 400 bilder provar OOM-fallback.

Se [viewport-rapporten](render-viewport-2026-10-20.md) för hela provgränsen och
D7DA:s instrumenterade tidsfönster. Även paus hade några långa handlers; inga
enskilda flushmax får subtraheras från handlermax. Det blev inget komplett
trefas-PASS, utan ett separat paussupplement. Ingen säker rotorsak för alla ryck.

## Git, draft PR och faktisk CI

Före denna dokumentändring var arbetsytan ren på `codex/product-hardening`.
Lokal HEAD och lokal `origin/codex/product-hardening` kontrollerades till
**`5305057683afd67518881edd226fb3712f13a7f8`**. Lead 4 verifierade även remote
vid publiceringen 20 oktober. Ingen ny remote-/nätkontroll görs i denna handoff.

[PR 1](https://github.com/Bratwurst04/Bongo-Cat-Screen/pull/1) är fortsatt **draft**,
titel **Harden companion and reduce rotating artwork redraws**. Ingen merge,
tagg eller ny release. Denna handoff lämnas som dokumentändringar för Leads granskning.

| Faktisk körning på 5305057 | Resultat |
| --- | --- |
| [PR-run 39433506986](https://github.com/Bratwurst04/Bongo-Cat-Screen/actions/runs/39433506986) | SUCCESS: 381/388 PASS, sju klassade SKIP, noll fel |
| [Push-run 39433501728](https://github.com/Bratwurst04/Bongo-Cat-Screen/actions/runs/39433501728) | SUCCESS: 381/388 PASS, sju klassade SKIP, noll fel |

Sju CI-undantag är sex historiska arkiv och ett privat foto. De fulla SDK-/C++-
fixturerna kördes på hosted Windows. Lokal ren svit gav **379/388 PASS och nio
klassade SKIP** (samma sju samt två lokala SDK-fixturer), noll fel/blockerade
operationer. Äldre rapporters före-CI-formuleringar beskriver dåvarande läge;
de nya faktiska länkarna finns även i PR-texten. Starta ingen dokument-/CI-loop
för att skriva om de frysta rapporterna.

## Underlag och integritetsgräns

Alla nedanstående JSON-kvitton är avsiktligt säkra projektexemplar under
`build/product-committee-2026-10-20/render-runtime-evidence-20261020-1455/`.
De kan saknas i en ren klon eftersom buildkvitton är ignorerade. Läs inte privata
TEMP-journaler, profiler, tokenfiler eller appbackuper för att fylla luckor.

| Säkert kvitto | SHA-256 |
| --- | --- |
| [Faktisk CI](../build/product-committee-2026-10-20/render-runtime-evidence-20261020-1455/github-viewport-ci-20261020.json) | `2A13B90D00A092B8B345E97F37E553E557EEE3FD2630C0858CB4A77DE98B608F` |
| [Oberoende Root-granskning](../build/product-committee-2026-10-20/render-runtime-evidence-20261020-1455/bongo-render-viewport-root-review-20261020.json) | `74E15EF2098FFFB9647C4AC2028A226CFE26271319A3485B5A25F28193CD9BCA` |
| [Historisk återställd drift 20 oktober](../build/product-committee-2026-10-20/render-runtime-evidence-20261020-1455/bongo-render-restored-runtime-safe-20261020.json) | `53E4530A7B6F287F92144FA6CEB6DDA68CF322C47A198FC08D9BD92A437E0CC9` |
| [Syntetiska D7DA-tider](../build/product-committee-2026-10-20/render-runtime-evidence-20261020-1455/bongo-render-timing-root-evidence-20261020.json) | `7BBA2B4345EED67B8B0EF4AD80E0CB55BC8F5A81C94C0C4CE9C8C6C85C1783FA` |

Lokal slutsvit: `build/product-committee-2026-10-20/viewport-clean-final-r3/check-g5wnwd2z/`.
Summary-SHA `03493A67B394627435494DBB30C78215244E4A3F9707C556C84229D272B9D323`;
snapshot-källmanifest-SHA
`C7D4592DAF4B70BD0A0DC6B397E50AC44E2CF8BDFFE8B5CD4D2CBCAE4BC9F001`.
Root kontrollerade inga kod-/testinputändringar efter den körningen; efterföljande
resultattexter är dokumentation. Två ofrysta genererade äldre fixturecacher skrevs
om av misstag under ett fokuserat prov; exakta sökvägar och avgränsning står i
viewport-rapporten. Ingen äldre binär/frysning rekonstruerades eller skrevs över.

## Närmaste arbete: utred bildkedjan före åtgärd

Användaren upplever låg kontrast/mättnad och vill veta om programkedjan kan
förbättras eller om annan panel behövs. **Ingen paneluppgradering, färgboost
eller produktändring är beslutad.** Lead 5 har en separat granskningsprompt;
Code slutför denna handoff först. Börja med skrivskyddad produktkod och säkra
syntetiska offlineunderlag i nya mappar, utan ny firmware/appbyggning, COM,
privata profiler eller Spotify-nättrafik.

Spåra båda faktiska källvägarna och håll observation, slutsats och hypotes isär:

1. Windows/Spotify-thumbnail respektive Spotify API JPEG/PNG: faktisk upplösning,
   ICC/sRGB, gamma, EXIF och alpha/premultiplikation.
2. Selektiv alpha-crop och eventuell generell inset: kontrollera faktisk kod även
   för API/andra spelare, inklusive påståendet om generisk sexprocentsbeskärning.
3. RGB888/vinylyta → kompakt **80×80 RGB565** → senare **112×112 refinement**:
   kvantisering, återanvänd cache, mask, skalning, zoom och sampleförluster.
4. LVGL → TFT-init, gamma, byte-/kanalordning och aktivt hög GPIO 27-bakbelysning.
   Skilj kodinställning från faktiskt observerad panel och ljusmiljö.

Förbered deterministiska färgramper, neutral gråskala, mörka/ljusa och avsiktligt
dämpade bilder samt alpha-kanter. Visa stegvis hostkonvertering tydligt märkt
**simulering**, med reproducerbara kvitton. Bedöm om ICC-/premultiplikationsfel
kan förklara normal sRGB eller enbart särskilda format. Automatisk kontrast- eller
mättnadsboost kräver underlag; neutralt standardläge och konservativa valbara
alternativ kan utredas utan att påstå återvunnen bildinformation.

Fysisk kontrollramp och jämförelse i samma ljus/betraktningsvinkel behövs innan
panelens kontrast/färgförmåga eller ett köp bedöms. Ett sådant framtida prov
behöver Leads samordning men är inte utfört här. Bevara fart, kompakt/refine,
animationer och svensk text. Rapportera fil/rad, mätbart steg, risk och minsta
möjliga framtida åtgärd; ge inga ogrundade köpråd.

## Kvarvarande fysisk acceptans och backlog

- Användaren behöver först kontrollera återställd C421/EBB: riktig låt/bild,
  tid/statistik, meny, gester och övrigt normalt UI.
- Ny viewport väntar på separat konkret firmwaregodkännande, eventuell
  kontrollerad installation och faktisk bild-/rullnings-/stale-pixelacceptans.
  Även nya refinement-, snabbbytes-, Fokus-/DJ-avbrotts- och långdriftsprov återstår.
- Windows sleep/resume, mörk timerväckning och exakt väcktid/ström på aktuellt
  utvecklingspar är separata fysiska prov; gamla kvalitativa prov bevaras som historik.
- [Kommittérapporten](product-committee-2026-10-20.md), [Security](../SECURITY.md)
  och [Privacy](../PRIVACY.md) beskriver kvarvarande klartexttokens/DPAPI eller
  Credential Manager-migrering, aktiv kontofrånkoppling, transitiv låsning/licenser,
  signering/proveniens, releasegrindar och mindre lokal processhårdning.
- Spotifyåtkomst, attribution, omslagsvisning och kommersiella villkor behöver
  granskas inför bred distribution. Publik källkod och godkänd CI är ingen
  garanti för Spotifygodkännande, säkerhet eller kommersiell distributionsrätt.
  Inga nya policy-/köp-/prisrekommendationer görs i denna överlämning.

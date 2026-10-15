# Överlämning: Bongo Cat Project Lead 3 → nästa Lead

**Datum: 2026-10-15, Europe/Stockholm.** Dokumentationsöverlämning vid
avslutad 3 s-analys. Användaren vill byta Lead-chatt och att efterträdaren
själv bedömer framtida överlämningsbehov under aktivt arbete.
**Inget nytt kodarbete eller långtidstest ska startas nu.**

## Arbetsyta, roller och beslut

- Arbeta endast i **`D:\DEV\Ai\Github\Bongo-Cat-Screen`**. Använd inte
  OneDrive-kopian. Gren: `codex/runtime-artwork-speed`; många befintliga
  ändringar och ospårade filer är avsiktligt kvar. Bevara dem. Ingen ny
  Git-commit eller release ingår i överlämningen.
- Lead planerar, granskar och delegerar kod/projektdokument till Code och
  UI till UI-chatten. Lead kan hantera runtime/flash inom användarens
  tillstånd. Kodskrivaren ändrar inte verklig profil eller drift på eget
  initiativ. Ny flashning kräver uttryckligt godkännande för aktuell binär.
- Bevara animationer, Fokus, panelmeny, touch, mediekontroller, Windows-
  prioritet, seriell trafik och art2/omslag. Undvik stora omskrivningar.
- **Behåll aktiv dagtakt 5 s.** 3 s är tekniskt tillåtet men analyserades
  enbart isolerat. Lead rekommenderade 5 s med låg API-belastning som
  prioritet; användaren svarade **”Bra”**. Lead har bekräftat faktiskt
  konfigurerat dagvärde **5,0** och installerad 17466-hash. Ingen taktändring.
- Seek-skärmprovet är fortsatt uppskjutet på användarens begäran.

| Chatt | ID / ansvar |
| --- | --- |
| Avgående **Bongo Cat Project Lead 3** | `01a10cc6-9bf4-78d2-8272-bf44acefa7c7` |
| Befintlig **Code 2** | `01a0ec49-da6f-7b00-be86-06822053344a`; återanvänd för avgränsade kod-/dokumentuppdrag |
| Befintlig **UI** | `01a11581-4a2c-7e80-9742-adcd989df5ca`; layout, UI-underlag och granskning |
| Ny **Bongo Cat Project Lead 4** | `01a14061-2445-7cc0-9178-79fb0625be18`; host `local` |

Följ den stående överlämningsrutinen i
[`CHAT_ROLES.md`](../CHAT_ROLES.md): bedöm behovet före svåröverskådlig
historik, spara daterat underlag genom Code vid lämplig milstolpe, skapa
efterträdare på användarens begäran eller gällande uttryckliga stående
auktorisation, kontrollera att efterträdaren läst underlaget och lämna över
ansvaret. Ingen bakgrundsbevakning eller automation utlovas.

## Läsordning och vilket underlag som gäller

Läs `00_PROJECT_CONTEXT.md`, `01_CURRENT_STATE.md`, `02_DECISIONS.md`,
`README.md` och `CHAT_ROLES.md`, kontrollera Git-status och berörd källa.
**De breda 00/01/02-filerna innehåller äldre versions-/driftuppgifter.**
Använd daterade bevis nedan för nuvarande installation och acceptans:

| Rapport i `D:\DEV\Ai\Github\Bongo-Cat-Screen\docs\` | Vad efterträdaren ska ta med |
| --- | --- |
| [`api-budget-runtime-2026-10-15.md`](api-budget-runtime-2026-10-15.md) | Senaste installation, rollback och fysisk mobilacceptans 17:50–17:52. Läs den senaste sektionen/samlade provstatusen; tidigare väntande uppgifter är historik |
| [`active-api-recovery-2026-10-15.md`](active-api-recovery-2026-10-15.md) | Fryst 17466-källa/paket, skydd och 166 PASS/2 SKIP. Rapportens då väntande installation/mobilprov är senare utförda enligt driftrapporten |
| [`api-cadence-3s-analysis-2026-10-15.md`](api-cadence-3s-analysis-2026-10-15.md) | Åtta isolerade 72 h-jämförelser 3/5 s; rekommendation 5 s, ingen verklig ändring |
| [`media-seek-2026-10-12.md`](media-seek-2026-10-12.md) | Byggd seek-kandidat och väntande fysiska prov. Där angiven installerad companion 68CC gäller 12 oktober, inte dagens 17466 |

Frysta funktions-/policyrapporter och källmanifest ska bevaras som historik.
Senare driftbevis läggs i separat daterad driftrapport. Att en aktuell
arbetskälla innehåller seek betyder inte att skärmen har fått seek-firmware.

## Exakt installerat och endast byggt

**Installerad companion 17466**, 19656937 byte:

- Installationssökväg: `C:\Users\gusta\AppData\Local\BongoDesk\BongoDeskSpotify.exe`.
- Bevarad kandidat i arbetsytan:
  `dist/companion-2026-10-15-active-api-recovery-dev/BongoDeskSpotify.exe`.
- SHA-256: **`17466EBFC95B14FDFB93D717BB9700F5937087AC27933CCDF82DF98E8C77C1C0`**.
- Installerad av Lead **13:16:12.522090 +02:00**. Deploymentprotokoll:
  `C:\Users\gusta\AppData\Local\BongoDesk\deployment-active-recovery-20261015-131610.json`.
- Fryst källa: `build/active-api-recovery-2026-10-15/source-frozen.json`,
  **75 filer**, med kopior i `source-frozen/`. Manifest-SHA:
  `0311312B2631F2E0F59CB66F80C6BF6DB0F9F01F60EA46C93D52E7384632DA86`.

**Firmware på skärmen F406**, 928960 byte:

- `.pio/candidates/focus-status-tap-F406C485.bin`.
- SHA-256: **`F406C485C775E3D907A04BC82620CB305E4EC48FAC10F0CF52754DB508EA2984`**.
- Fortsatt installerad under companionbytena; ingen ny flashning.
  Normal serial är COM6/230400. F406 har inte tidslinjesvepens seek.

**Seek är byggd och fryst, men inte flashad/fysiskt accepterad:**

- Firmware `.pio/candidates/media-seek-57894EE0.bin`, 929984 byte,
  SHA-256 `57894EE0D9249A6651F9210BD24ED1548CFD7E784E6DF20A1DC0919B534B6CEC`.
- Den äldre tillhörande frysta EXE:n
  `dist/companion-2026-10-12-seek-dev/BongoDeskSpotify.exe`, 19303449 byte,
  SHA-256 `A52946E59180390D892A80909E66002F8C3F92CC9CACD2D2540CEC7C4CBC55A6`.
  Detta är en bevarad byggkandidat, inte nuvarande installerad EXE.
- Manifest/provplan: `build/media-seek-2026-10-12/` och seek-rapporten.
  Inget nytt seek-prov eller byte är beställt nu.

**Närmaste återställningskandidat för companion är 137**, 19655597 byte:

- `dist/companion-2026-10-15-manual-api-refresh-dev/BongoDeskSpotify.exe`.
- SHA-256: **`1370651DF6FCC28D70FE4736B39818AA71F8BCEE13EF0992C90EC92EA97F7762`**.
- Hashverifierad installerad backup:
  `C:\Users\gusta\AppData\Local\BongoDesk\BongoDeskSpotify.backup-20261015-131610-pre-active-recovery-1370651D.exe`.
- 137:s manuella väntetryck/omslag var accepterade, men dess automatiska
  daguppföljning hade cirka 60 s-släp. 17466 rättade den policyn. En rollback
  är därför en medveten funktionsavvägning och ska bevara nuvarande historik.

De fem kandidatfilerna ovan har lästs och hashkontrollerats i arbetsytan
vid dokumentöverlämningen. Installerad fil/profil lästes inte av Code i
detta steg; installationsbeviset kommer från Lead.

## Senaste verifierat, och vad som väntar

**Fysiskt kvalitativt accepterat med 17466/F406:** Windows-Spotify stängt,
musik startad på mobilen och två mobilbyten. På frågan om rätt låttext inom
ungefär fem sekunder, rätt omslag och jämn animation svarade användaren
**”Aa nu ser de rätt ut.”** Inga tidsstämplar för mobilhandlingarna eller
stoppursmätta end-to-end-tider finns; lova inte uppmätt femsekunderslatens.

Lead observerade 17:50:43 aktivt 5 s-intervall efter 30 s idle och tre
automatiska `MEDIA_TRACK` utan mellanliggande serial-RX från skärmen.
Omslag tog **5250/5342 ms**, ACK **42/12 ms**. Extra NEXT gav metadata efter
**1,656/1,324 s**. Dessa loggtider är inte telefonens ändringstidpunkter.

Senaste överlämnade status **17:52:04**: API-källa, Windows saknas,
`idle=false`, API-ålder 0,36 s, ledger **299 totalt/276 auto**, gränser
**4000/3600**, reserv/Retry/clock **0**, fast **false**, totalt 429 fortsatt
**2**. ESP32 ansluten, heap **179984** / minimum **177088 byte**. Normalt
processpar var **57080/85540**; PID:erna är historik, inte framtida mål.

| Underlag | Status / gräns |
| --- | --- |
| 17466 regression och paket | Historiskt **166 PASS, 2 C++ SKIP** p.g.a. ofullständig MSVC/headers; 11 paketmoduler/4 resurser och 75 källor verifierade. Inga nya tester körda för överlämningen |
| 3/5 s-analys | **8/8** modellfall. Blandat 3 s ger **44–48 %** fler anrop och cirka 1,8 s bättre p95 för dagtext. Kontinuerligt ger tidigare tryck och sämre p95. Lokala tak höll; ingen garanti om Spotifys verkliga kvot |
| Bevarande efter analysen | **840/840** skyddade filer och **75/75** aktuella frysta källor oförändrade enligt separat analyskontroll |
| Långdrift, komplett historikdygn, natt/idle | Väntande fysisk acceptans med 17466/F406; starta inte nytt prov nu |
| Windows sleep/resume, serialåteranslutning och återsynkning | Väntande med aktuell companion |
| Full UI-/gestgenomgång, sömn/väckning/ljusblixt | Äldre F406-prov är historik; ingen ny komplett acceptans med 17466/F406 dokumenterad |
| Seek | Endast bygg-/kodverifierad. Fysiskt uppskjuten, inte flashad |

Aktivt 5 s är ett grundgolv för **känd spelande musik dagtid**, inte en
dygnsgaranti. Retry-After, högre inlärd pacing, halva/75 %-budgetar,
tryck/tail, natt 00–08 och idle kan ge längre väntan; kontinuerlig modell
visar upp till 120 s-luckor. Manuellt väntetryck finns kvar. Omslagens
överföringstid förkortas inte av tätare metadata. Framkalla ingen verklig
429 för test och nollställ inte historik för att få kortare intervall.

## Säker rutin vid ett senare godkänt runtimebyte

Detta beskriver Lead-rutinen; inget byte ska göras nu.

1. Kontrollera exakt godkänd kandidat-SHA och fungerande rollback. Läs
   aktuell installerad sökväg/profil; använd aldrig historiska PID:er som
   mål. Profilen ligger i `C:\Users\gusta\AppData\Roaming\BongoCat`.
2. Ta **samma befintliga** `spotify_api_budget.json.lock` som appen använder:
   öppna befintlig fil, position **byte 0**, lås **en byte** med Windows
   `msvcrt.locking`. Skapa eller ersätt inte ett annat lås. Under låset ska
   ledger visa **pending=0**: ingen HTTP i flykt. Om låset inte kan tas eller
   pending finns, avvakta; kringgå inte spärren.
3. Håll låset över stopp och kopiering. Stoppa endast processer med **exakt
   installerad EXE-sökväg**, vänta på hela det normala parent/child-paret.
   Bevara och hashverifiera EXE-rollback samt `config.json`,
   `spotify_tokens.json` och `spotify_api_budget.json` med daterade backuper.
4. Kopiera endast godkänd EXE och verifiera bytes/SHA. Config, token och
   ledger ska vara byteidentiska genom själva bytet; bevara Run-post och
   övriga inställningar. **Nollställ aldrig ledger, deadlines, token eller
   sparad begränsningshistorik**, inte heller vid rollback.
5. Släpp låset före start. Starta installerad EXE dolt med befintlig
   `--startup`-rutin, kontrollera normalt processpar, status/COM6, art2 och
   kvarvarande skydd. Efter driftstart kan pacingmetadata i tokenfilen
   ändras legitimt; jämför credential-fälten utan att exponera hemligheter.
   Dokumentera installation och riktiga observationer separat från bygget.

## Ansvar vid övertagandet

Efterträdaren ska bekräfta att dessa fyra rapporter och `CHAT_ROLES.md` är
lästa, att **17466/F406 och faktiskt 5 s** är nuläget och att seek väntar.
Ta därefter över planering och framtida överlämningsbedömning. Code 2 och
UI-chatten finns kvar. Inget nytt arbete, driftbyte eller test startas
enbart på grund av chattbytet.

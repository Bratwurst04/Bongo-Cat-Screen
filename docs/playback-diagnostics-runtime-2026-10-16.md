# Spotify-diagnostik och Connect-seek – drift 2026-10-16

Alla tider avser Europe/Stockholm. Underlag: den lästa
[säkra driftjournalen](C:/Users/gusta/AppData/Local/BongoDesk/runtime-playback-diagnostics-20261016-111305.json),
Leads installationsbesked och användarens skärmobservationer. Denna rapport
kompletterar den frysta [bygg-/före-start-rapporten](playback-diagnostics-2026-10-16.md)
och [byggmanifestet](../build/playback-diagnostics-2026-10-16/candidate.json).
Historiska uppgifter om ännu inte installerad eller skärmprovad kandidat
gäller respektive äldre rapporttidpunkt.

## Installation och bevarade skydd

Lead installerade diagnostikcompanion **26A0FAF0**, 19 656 980 byte,
11:13:05–11. SHA-256:
`26A0FAF078E7E1C8A35CB53F064027D5C1E2BC2799B5437A4983DC4735E167F2`.
Firmware förblev **C7E594B4**; ingen flashning gjordes. Journalens
[installationsprotokoll](C:/Users/gusta/AppData/Local/BongoDesk/deployment-playback-diagnostics-20261016-111305-284385.json)
är hänvisningen till Leads installationsbevis.

Enligt Lead användes samma befintliga ledgerlås med pending=0 och
hashverifierad **0D397F89** som rollback. Profilfiler och autostart var
byteidentiska genom kopieringen. Det betyder inte att normal budget- eller
tokenpersistens därefter upphörde. Ingen pacingändring eller skyddsreset
ingick. APP_START kom 11:13:12.314, seriell anslutning lyckades på första
försöket 11:13:14.498 och art2 bekräftades 11:13:17.784.

## Tomma svar och fungerande manuella läsningar

Första automatiska GET gav **uppmätt HTTP 204** 11:13:17.936. Loggen visade
tom kropp, saknat item och automatiskt workerutfall empty. Ytterligare
automatiska läsningar gav samma resultat trots användarens uppgift att
mobilen spelade. Väntan började före seekprovet.

Trycket 11:14:01.885 följdes av accepted, started 11:14:02.163, HTTP 204
11:14:02.257, shape empty, completed empty 11:14:02.276 och manuellt
snapshot empty 11:14:02.277. Ett andra tryck 11:14:12.597 gav samma hela
kedja med 204 11:14:12.918. Inget musikstyrande PUT skickades av dessa
väntetryck. **Tap to check fungerade alltså som läsning**, även när bilden
förblev i väntan. Svaren bevisar frånvaro av låtdata vid just dessa
API-läsningar; orsaken till Spotifys 204 är inte fastställd.

## Återhämtning

Användaren avslutade Spotify helt på mobilen, öppnade igen och startade
musik. Ett efterföljande manuellt tryck 11:15:00.195 gav HTTP **200**
11:15:00.419, item present/type track och completed/manual available
11:15:00.443. MEDIA_TRACK följde 11:15:00.449. Användaren bekräftade:
”Låttext och omslag återkommer”.

Art2 överförde 37 632 byte på 5 233 ms och fick lyckad ACK
11:15:05.798, 29 ms efter ART_SENT. Automatiska GET gav därefter 200
available 11:15:05.712, 11:15:10.952 och 11:15:16.154. Återkomsten följde
**mobilomstart och sedan manuell läsning**; varken enbart omstartens effekt
eller en permanent rotfix är bevisad.

## Fysiskt grundprov av Connect-seek

Användaren bekräftade ”Båda riktningarna fungerar” efter prov av ljud och
tid ±15 sekunder utan NEXT eller oönskad paus. Loggen visar:

| Kommando | Mottaget | Control success | Bekräftande snapshot |
| --- | --- | --- | --- |
| +15 | 11:15:43.613 | 11:15:44.781 | 11:15:45.802 |
| −15 | 11:15:51.063 | 11:15:52.619 | 11:15:53.856 |
| +15 | 11:16:03.233 | 11:16:04.488 | 11:16:05.488 |

På efterföljande paus-/följdsvepsfråga svarade användaren ”Allt fungerar
även pausat”. Det loggade snabba paret var faktiskt **två minuskommandon**,
11:16:56.948 och 11:16:57.509, 561 ms isär. Båda lyckades och fick separata
bekräftelser 11:16:59.276 respektive 11:17:01.953. Detta visar hanterade
följdsvep och kvalitativ pausacceptans; det är inte en oberoende mätning av
+30 sekunder eller ett verifierat par pluskommandon. Ingen exakt latens
från fingerrörelse till ljud/skärm mättes.

Vid prov nära låtslut sade användaren att framåt når slutet, låten
förblir pausad och inte byts. Bakåt upplevdes inte fungera. Den fasens
logg visade bara två lyckade pluskommandon, inga minusbegäranden.
Framåtgränsen är kvalitativt accepterad. Ett kontrollerat pausat prov
från 0:30 gav sedan ”Den backar till ungefär 0:15”. **Börjanprovet från
0:05 är däremot underkänt**, även efter att användaren inväntat rätt låt
och tid på skärmen. RX −15 11:21:30.284 följdes av GET 200 med item
present och `seek_unsupported` 11:21:30.562. Ett senare låtbyte kan förklara
ett gammalt kontextavslag, men bevisar inte orsaken. Vid den synkade
retetsten sågs endast PLAY_PAUSE, ingen minusbegäran; samma avslag får
inte tillskrivas varje försök. Exakt isolerat 5 000 ms → 0 passerar med
verklig worker/filbudget för både fryst 26A0 och arbetskällan. Inte heller
det sista centersvepet godkändes, trots lyckade PUT/bekräftelser i loggen.
Användaren avbröt då seek och beställde
borttagning; någon ytterligare seekrättning eller diagnostikkandidat görs inte.

## Status och kvarvarande prov

Status 11:17:42 visade färsk ESP32-kontakt, API-källa med aktivt
femsekundersintervall, budget 1 040/978 av 4 000/3 600 och noll reserver,
Retry-väntan och klockspärr. Totalt 429 var fortsatt två; senaste timmen
noll. Ett aktivt snapshot bevisar inte att varje seek gjordes pausat;
pausbedömningen ovan är användarens kvalitativa besked.

Connect-seek blev delvis grundprovat; börjanfallet godkändes aldrig.
Windows-GSMTC, utökade
gester/layouter, races, sleep/resume och långdrift med detta par återstår.
Driftuppgifterna sparas i denna nya rapport. Befintliga frysta underlag
bevaras; ingen permanent rotfix påstås. Borttagning redovisas separat.
Dokumentändringen kontrolleras
med `git diff --check`, textkontroll och jämförelse av skyddade filers
byte/hash. Inga ytterligare kodtester behövs för själva dokumentationen.

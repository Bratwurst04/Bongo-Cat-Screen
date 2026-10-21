# Spotify-väntan: avgränsad diagnostikkandidat 2026-10-16

## Slutsats och versionsgräns

Ingen konkret lokal grundorsak har påvisats. Kandidaten lägger till
innehållsfria logghändelser för att skilja API-svar utan visbar låt från
fel i den manuella kontrollkedjan. Den är **byggd, fryst och provad i
isolering**. Code har inte startat eller installerat den, ändrat verkliga
profiler, gjort riktiga API-anrop, flashat eller publicerat något.

Lead rapporterade vid uppdraget installerad companion **0D397F89** och
firmware **C7E594B4**. Användarens tidigare bekräftelse av skivflip och ö
gäller det paret; den verifierar inte denna diagnostikkandidat eller seek.
Historiska rapporter, kandidater och releaser är bevarade.

## Incidentunderlag från Lead

- Vänteläget började före det planerade seekprovet. Ingen SEEK loggades.
  Mobilen fortsatte spela, och låtbyte samt mer än 30 s väntan hjälpte inte.
- Fyra `PLAY_PAUSE` togs emot 10:57:59.371, 10:58:03.443,
  10:58:05.102 och 10:58:06.090. Därmed finns bevis på att tryck nådde
  companionen; dagens logg kan inte visa hela manuella läskedjan.
- Färsk ESP32-kontakt och API-status fanns kvar. API-källan gick i idle
  med 30 s intervall, snapshotåldern återställdes och automatisk
  budgetdebitering fortsatte. Lead fann inga relevanta fallback-,
  refresh-, 429- eller state-I/O-fel i den granskade allowlistloggen.
- 10:57:19 var total/auto 952/915, 10:58:09 961/922. Differensen ökade
  från 37 till 39: förenligt med två manuella HTTP-debiteringar inom
  befintlig femsekundersgräns, men ingen separat bevisning av deras svar.
- Lead provade kontrollerad omstart av exakt samma 0D397-version
  11:03:24–26, med backup, befintligt ledgerlås, pending=0 och profiler
  byteidentiska fram till start. Väntan kvarstod. Ingen skyddsreset gjordes.

Kodens tomma svar och `item: null` leder båda till Waiting for Spotify.
Att API-läsningarna returnerade utan visbar låt är därför en **stark
kodinferens**. HTTP 204, en viss svarskropp, kontoproblem eller Spotifyfel
är **inte uppmätt eller fastställt** i dessa äldre loggar. En fördröjd
extern bekräftelse som nämner Retry 02/10 hör inte till denna incident.

## Ändrade filer

- `companion/diagnostics.py`: fasta tillåtna enumfält för de nya händelserna.
- `companion/spotify_api.py`: faktisk HTTP-status per playback-GET-försök
  och svarens form efter samma strikta JSON/UTF-8-avkodning som tidigare.
- `companion/media_bridge.py`: manuell läsning och workerutfall loggas.
  Inputplatsens lås släpps innan mottagningshändelsen loggas.
- `tests/test_playback_diagnostics.py`: åtta beteende-/sekretesstester.
- Denna rapport.

Mot den frysta installerade 0D397/C7-källan ändras endast dessa tre
companionmoduler och det tillagda testet. Tidigare arbetsändringar för
flip/UTF-8 ligger kvar. Firmware, engine, `api_budget`, seek, UI-resurser,
tokenflöde, femsekundersstandard, deadlines, grants och omslagsprotokoll
är bevarade. Inga extra API-anrop, arbetstrådar eller serialmeddelanden
har lagts till.

## Läsning av den nya loggen

| Händelse | Innehåll och begränsning |
| --- | --- |
| `SPOTIFY_PLAYBACK_HTTP` | `source=spotify_api`, request_kind, success/failure och faktisk HTTP-status när ett svar finns. Success betyder mottaget HTTP-svar, inte bevis på giltig låt. Även 401 före en tillåten tokenretry syns. |
| `SPOTIFY_PLAYBACK_SHAPE` | body_shape empty/object/other/invalid, item_state present/null/missing/other, playback_type track/episode/ad/unknown/missing och outcome available/empty/invalid. Available här beskriver ett item-objekt; workerhändelsen visar om normaliseringen också blev klar. |
| `MEDIA_API_SNAPSHOT` | Workerretur available/empty med read_origin manual/automatic/confirmation. Bekräftar inte att en människa sett bilden. |
| `MEDIA_REFRESH` | accepted, coalesced, suppressed, started, completed, expired eller cancelled. Started räknar det befintliga sista startvillkorets försök; HTTP-händelsen visar mottaget svar. Completed anger available/empty/discarded. |

Titlar, artister, track keys, device-ID, URL:er, kroppar, headers, tokens
och råa felmeddelanden ingår inte i de nya händelserna. Okända typer
mappas till en fast enum. Transportfel utan HTTP-svar använder befintliga
felhändelser. Samma roterande logggräns, 256 KiB med tre backupfiler,
gäller fortsatt; de nya raderna förkortar loggens historiska räckvidd.

## Verifiering

- **196 upptäckta Python-prov: 194 PASS, 2 SKIP, 0 fel.**
  Båda SKIP är de kända C++-runtimeproven för Fokus/touch eftersom komplett
  MSVC-runtime/headers saknas. De är inte godkända prov.
- Åtta nya prov passerar. De omfattar 204, 200 med null/saknat item,
  track/episode/ad/okänd typ, felaktig JSON/UTF-8/form, manuell tom/lyckad
  retur, Windows-övertagande, gestsammanläggning, cooldown, expiry före HTTP,
  401 med högst två manuella försök samt återlämnade reserver.
- Nio förlopp genom verklig worker och filbaserad budget jämfördes med
  fryst 0D397-källa. HTTP-metoder/tidpunkter, manuella starter, publicerade
  snapshots och budgetdebitering/reserver var exakt lika. Inkluderar tomma
  svar, burst, långsam tokenförberedelse, Retry-spärr, spacing, 401,
  JSON-fel och normal play från paus.
- Separata testprofiler under denna arbetsyta; **0 externa nätförsök**.
  Verklig Spotify-, token-, konfigurations- eller ledgerfil lästes inte.
- PyInstaller bygge från fryst källa: PASS. Paketets elva Pythonmoduler,
  fyra resurser och Stockholm-tzdata matchar. 47 Pythonkällor kompilerades
  även i minnet, utan att skapa pycache i frysta snapshots.
- 154 aktuella och 154 frysta källfiler matchar manifestet.
  1 347 äldre skyddade artefakter/rapporter matchar tidigare byte/hash.
- `git diff --check`: PASS. De nya textfilerna är även kontrollerade
  separat för UTF-8, avslutande radbrytning och radslutsblanksteg.

Underlag finns i `build/playback-diagnostics-2026-10-16/`, bland annat
`python-regression-r2.log`, `test-summary.json`, `scope-verification.json`
och `package-verification.json`. Native flipfixturen skrev i den nya
byggmappen; äldre byggunderlag användes inte som utdatamapp.

## Fryst kandidat

- EXE: `dist/companion-2026-10-16-playback-diagnostics-dev/BongoDeskSpotify.exe`
- Storlek: **19 656 980 byte**.
- SHA-256: `26A0FAF078E7E1C8A35CB53F064027D5C1E2BC2799B5437A4983DC4735E167F2`.
- Källsnapshot: `build/playback-diagnostics-2026-10-16/source-frozen/`,
  154 filer.
- `source-frozen.json` SHA-256:
  `86529F867076702EFA73911063E45EF1CBA3B3EA13EA7ACDBA76CA8BCF529BCE`.
- `package-verification.json` SHA-256:
  `49C419D90F3764572D74BB4FE8AE1D96BAC08DF790BB65AB872B7EBA55476E4A`.
- `candidate.json` SHA-256:
  `0F7B215EC12F3505335C2138EDDFC8020EDEED833B154DA2763CABF6C672BD96`.
- Bevarad rollback-EXE: 0D397F89,
  `0D397F89DCBC5C6B648517268A08B1D4E9DBEF23B7BAFD9B51816EBE77850ADD`.
- Firmware oförändrad C7E594B4,
  `C7E594B462D0025B1BE00BFE70C535153326E18DCE4CA29017B4D84712AD7DFB`.

## Nästa avgränsade prov hos Lead

Efter granskning hanterar Lead eventuell installation med samma backup-,
lås- och pendingkontroll som tidigare. Befintlig firmware används.
Låt en ordinarie automatisk läsning ske och följ sedan ett enda manuellt
väntetryck genom lifecycle och HTTP/shape/workerhändelserna. Jämför
skärmen med mobilens läge utan en andra API-klient eller ändrad pacing.

204 respektive 200/null är olika observerade svar och ska redovisas som
sådana. Om ett giltigt item når workern men skärmen förblir i väntan
behöver den lokala publiceringen undersökas utifrån dessa nya bevis.
Diagnostik är inte en uppspelningsrättning. Verklig kandidatdrift,
grundorsak, återställd mobilföljning och fysiskt seekprov väntar.

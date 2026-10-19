# C3: engångsåterhämtning av kapabilitet – 2026-10-18

**Endast companion byggd, inte körd eller installerad. Ingen firmwarebuild
eller flashning.** Installerat är fortfarande **356A5EC0/C6EBAE4B vid 921600**.
C2:s [uppstartsrapport](artwork-compact80-runtime-2026-10-18.md) är nu slutställd
med musikprovet väntande, SHA-256
`66E1747AEBFAF0F4FD0F205A4F7837477C687BEAC89D976EC9E2F5F0298EC1AB`.
Den bygger enbart på den före läsning hashverifierade startsnapshoten
`C9CDC4628A5D19C929EB515C6342D08FEE241DEE94B04CA16AE29FEF5FD7BFF0`.
Inga privata backupreferenser följdes. Ett senare normalreset-/musikprov
är separat underlag i [uppföljningen](artwork-compact80-post-reset-2026-10-18.md):
bas-ART2 återkom men ingen kompaktkapabilitet loggades; två fullformatsomslag
tog 4,682/4,680 s. Det är inget giltigt kompaktfartprov. C3 är **inte bevisat**
åtgärda den saknade kompaktraden i detta senare prov.

## Källbedömning och ändring

`connect_serial` frågar före configtillämpning och läsarstart; dess egen
readline känner bara igen PONG och vidarebefordrar inte en läst SYNC_REQUEST.
Firmwareproben tolkar PING/statistik/raw-header men ignorerar CAPS-frågor.
Den aktuella startsnapshoten visar ingen kapabilitet till 22:45:01, men
bevisar inte exakt vilken fråga eller SYNC som saknades.

C3 ändrar endast produktfilen `companion/engine.py`:

- Initial sync armar ett sammanhängande conn/epoch/challenge-context.
  Läsaren fångar det före blockerande readline. Endast giltiga, rimliga
  HEAP/HEAP_TOTAL/MIN_HEAP/UPTIME-fält för aktuell generation kan utlösa
  omsändningen; gammal eller ogiltig status förbrukar inte den nya chansen.
- Efter statusuppdatering lämnas data-låset. Under serial-låset kontrolleras
  samma handle, context-identitet, epoch/challenge, öppen port och stoppflagga.
  Därefter kan högst en CAPS-fråga med **samma** challenge skrivas till det
  fångade handtaget. Ingen ny epoch, media-/cache-reset eller API-läsning görs.
- Omsändningen hoppas över endast om **både** bas-ART2 och kompaktkapabilitet
  redan är bekräftade för rätt 921600-generation. En ensam RGB56580-rad med
  saknad basrad räcker inte. Äldre peer får högst en extra ofarlig fråga.
- Kvoten konsumeras en gång och återarmas av befintlig initial-sync vid
  resync/reconnect. Delvis skrivning/fel går till befintlig handle-recovery
  efter att serial-låset släppts. Ingen ny tråd, låsordning eller periodisk
  probe-loop införs. Loggen skiljer query-resend från bekräftad kapabilitet.

Det finns **ingen generell startup-readiness-gate**. Om ett första omslag
redan hunnit börja i legacy/full fallback kan det fortsätta där. C3 avser
återhämtning från en tappad engångsfråga, inte garanterat kompaktformat för
första omslaget eller en verifierad fysisk fartfix. Inte heller första
UnicodeDecodeError vid portöppning är fastställt eller rättat här.

## Verifiering

**70/70 riktade och relevanta tester PASS**, utan fel, skip eller externa
nätverksförsök: nio nya fall samt befintliga artwork-, power-resume- och
lifecycle-prov. De nya fallen täcker en enda omsändning, ogiltig/gammal
status/conn/epoch/challenge, fullständigt och partiellt cap-tillstånd,
rearm efter resync/reconnect, status läst över generationsbyte, sändning
utanför data-låset, shutdown medan serial-låset väntas och partialwrite
utan deadlock. Cache/epoch/pending-art-id och äldre gating bevaras.

Ingen ny bred helsuite kördes; C2:s 264 PASS/två SDK-skip gäller föregående
källa. Slutpaketets bytekod/resurser är jämförda med slutkällan, inklusive den
korrigerade kommentaren om initial fråga och högst en omsändning.
Alla andra engine-metoder är jämförda som AST med C2, inklusive start/stop,
återanslutning, media-/omslagssändning och codec-val.

**180 frysta källfiler**, 68 Pythonfiler syntaxkontrollerade. Paketets
**12 moduler och fyra resurser matchar** slutkällan. **7 552 äldre filer**
är verifierat bytebevarade utan avvikelser, inklusive tidigare kandidater,
byggbevis och preview. `git diff --check` passerar utan whitespacefel;
endast de tidigare LF→CRLF-varningarna för `src/media_art_v2.h` och
`tests/test_focus_countdown.py` visas.
Samtliga nio ändrade/nya käll- och dokumentfiler är giltig UTF-8.

SHA-256 för bevisfiler under `build/capability-startup-2026-10-18/`:

| Fil | SHA-256 |
| --- | --- |
| `source-frozen.json` | `A6B738147E1886F6FE164B43B5100FEEA158DA31810E8C7A94EC52BB641D2DD7` |
| `package-verification.json` | `4D3A32DBF4690C66F02DA5B704A36FC6D0841F1172D770F4FE64EAB76103698D` |
| `scope-verification.json` | `EFE3D1F9B8B8B52B37184EB218E9FB90871C3BC2FEF0484BDA0C90B934AB440F` |
| `candidate.json` | `DEEFCFB97F7198BCB515AE1392985E83F73E5EE2638910C360EAF2FC9C1D8ECE` |

## Exakt kandidat och provgräns

- App `dist/companion-2026-10-18-capability-startup-dev/BongoDeskSpotify.exe`,
  **19 659 276 byte**, SHA-256
  **FD9D811B0356818A56AA0787AD3041820DA8D45D6083D8E0E822D3B59426DB06**.
  Standard-spec; byggd separat och inte körd/installerad.
- Samma firmware `.pio/candidates/artwork-compact80-2026-10-18-C6EBAE4B.bin`,
  **936 704 byte**, SHA-256
  **C6EBAE4B13DE934449E2F32738D2CBFAEEC2693C5ECF8EE8A3A71FDB6254D275**.
  Endast hashverifierad; ingen ny firmwarebuild eller BOOT-/flashåtgärd.

Separat källa/manifests/logg: `build/capability-startup-2026-10-18/`.
Nya källfiler är `tests/test_capability_startup.py` och
`tools/capability_startup_candidate.py`. Därtill endast aktuell toppstatus
i 00/01/02 och tre separata rapporter: C2-uppstart, C3 och senare C2-resetprov.
Den avslutade C2-uppstartsrapporten är oförändrad. GUI/config, codec, firmware, API/auth,
polling/budget, gamla helpers/rapporter/frysningar/binärer/preview bevaras.

Efter separat godkännande för apphashen återstår fysisk startup/resume med
saknad första cap, högst en resend följd av rätt bas+kompakt-cap, normal
återsynkning/omslag och Exit. Fart mäts först för det faktiskt körda paret.
Ingen körning, installation, profiländring, serialtrafik, live-HTTP, commit,
push eller release utfördes av Code i detta steg.

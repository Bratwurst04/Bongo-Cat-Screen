# Behåll omslaget till dold brytpunkt – 2026-10-18

**Byggd firmware 5556B647, inte flashad eller skärmprovad.** Installerat är
fortsatt **FD9D811B/C6EBAE4B vid 921600**. Användaren beställde att föregående
synliga framsida inte ska försvinna före flipens mitt och att flashning väntar
till i morgon. Code gör ingen runtime-/installationsåtgärd. C3:s tidigare
byggbevis bevaras; dess faktiska driftprov redovisas
[separat](capability-startup-runtime-2026-10-18.md).

## Ändringen

Produktändringar endast i `src/media_turntable.h` och minsta integration i
`src/bongo_cat_featured.inc`. DEFAULT är nu enbart preparation. Den gamla
synliga framsidan hålls kvar genom tonarm-clear, grepp, lyft och flipens första
halva. Vid **870 ms** väljs färdig korrekt nybild, annars generisk. Komplett
exchange håller gammalt under uttaget och byter först **1 070 ms**, helt ur bild.
Ordinarie faslängder är kvar: normalt 1 880 ms, komplett 2 380 ms.

Två befintliga RGB565-slotar räcker. Synlig slot är pinnad; nästa omslag tas
emot i den andra. En CRC-godkänd mottagning **ACK:as som staging direkt**,
oberoende av animationen. ACK lovar inte att bilden redan visas. En ny BEGIN
kan ersätta staging men aldrig skriva över den fortfarande visade sloten.
Descriptor och synligt slotval följs åt i frame-steget. Ingen tredje stor
pixelbuffer, bildlista, större RX-kö eller ny serialtrafik införs.

Retarget före kanten ersätter endast nästa mål inom samma rörelse. Efter
kanten bevaras den nu synliga sidan medan ordinarie rörelse avslutas. En enda
ersättbar senaste identitet väntar därefter på en ny rörelse/dold brytpunkt.
Det kan fördröja den senaste bilden vid snabba byten, men ger ingen synlig
framsidepop eller omstart mitt i rörelsen. Övergivna mål räknas inte som
stabilt avslutade byten; vart femte stabila byte är fortsatt komplett.

Vid missad frame målas en tunn 2px-kant eller helt urbilden-pose innan en hel
ny framsida tillåts. Detta håller inte RX/ACK och startar inte om klockan.
Osynlig panel/DJ/meny får senaste färdiga bild utan återspelad kö. Late art
har fortsatt 180 ms reveal. Same-context/resync, NONE och milliswrap täcks.

## Verifiering

**135 upptäckta: 133 PASS, två kända SDK-skip, inga fel eller externa
nätförsök.** Avgränsad regression omfattar native staging/slot-pixlar,
turntable/arm/tempo, äldre record-helper, artwork/compact/full/raw,
power-resume/lifecycle, Fokus-layout/åäö och C3-capability. Ingen bred helsuite.
Två Fokus-hostprov saknar komplett MSVC SDK; de nya fristående C++-proven
för parser/CRC/codec/pixelägarskap kördes faktiskt.

Nya prov exekverar verklig produktparser, CRC, slotval, state och renderer
med olika gamla/nya pixlar: tidig ACK, ny BEGIN över staging, retarget före/
efter kanten, gammal END, fel-CRC/abort, late art, NONE, full/raw, osynlighet,
milliswrap och frame-gap vid normal/komplett animation. Äldre 280ms-fixtur
använder explicit fryst tidigare integration; live staging provas separat.
Fasproven samplar nu den nya obligatoriska kanten mellan lyft/nedläggning.

Build: separat `esp32-024r-spotify-compact80`, **69,404 s**, RAM **112 416 byte**
(oförändrat), program **936 057 byte**. Bildens checksumma och validation hash
är giltiga. Första byggförsöket stoppades av cachelåsets sandboxbehörighet;
omkörning med tillåten verktygscache lyckades. Ingen port öppnades.

- Firmware `.pio/candidates/turntable-face-2026-10-18-5556B647.bin`,
  **936 800 byte**, SHA-256
  **5556B647EEEC5D41165F0F518E7FC8B0B5FAC2AA645931F278C01F9D12A182A4**.
- ELF SHA-256 **D30F396F26AD2F461B286B763CD525A714FF88B1651C8F77E467CA9FF384A4BD**.
- Companion är bytebevarad FD9D811B, ingen appbuild eller källändring.

## Preview och återstående prov

`visuals/turntable-face-2026-10-18/r1/index.html` har åtta source-driven
GIF/tidsserier: early/late art, komplett utbyte, retarget före/efter kanten,
Fokus-layout samt stora frame-gap normalt/komplett. Syntetiska tydligt olika
RGB-bilder går genom verklig kompaktparser/CRC/staging. Visad slot levererar
pixlar till verklig C++-projektion/primitiver; UI/glyphbakgrund återbrukas.
PIL-rasterisering och skriptat tempo är **simulering, inte TFT-resultat**.
Manifest SHA-256 **0160F29A7685A297319FE513BDD2DB7E42031151152D3822F0F5F622EF1B3A0B**.
Lead och UI Code har godkänt exakt r1-manifest utan blockerande fynd:
21 källhashar och 18 outputs matchar. De bekräftar rätt gammal/ny sida,
tunn kant, komplett offscreen-byte, late reveal, latest-retarget, arm och
fria textytor. Frame-gap-fallens avsiktliga frysningar/steg bevisar dold
pose, **inte jämn animation på TFT**. Review sparas med kandidatbevisen.

Efter separat godkänd flash återstår att se gammalt omslag ända till kanten,
ingen tidig generisk bild, early/late art, snabba retargets och komplett
utbyte på skärmen. Kontrollera även Fokus/DJ/meny, gester, åäö, omslags-ACK,
sleep/resume och längre drift. ACK-tid för ny firmware är ännu inte uppmätt.
Inga COM-/profil-/API-/installations-/flash-/commit-/push-/releaseåtgärder.

## Slutlig frysning och bevarande

Efter Lead/UI-review frystes **185 källfiler**, varav **72 Pythonfiler**
syntaxkontrollerades. **7 796 äldre filer** är bytebevarade utan avvikelser,
inklusive FD9D811B och gamla kandidater/rapporter/previews/frysningar.
`git diff --check` passerar; endast tidigare LF→CRLF-varningar för
`src/media_art_v2.h` och `tests/test_focus_countdown.py` återstår.

Utöver produktfilerna ändrades 00/01/02 och sex berörda test-/fixturefiler:
`compact_art_host.py`, `turntable_paw_host.py`, `record_flip_host.py`,
`test_record_flip.py`, `test_turntable_paw.py`, `test_turntable_arm_tempo.py`.
Nya källfiler är `tests/turntable_face_host.cpp`, `tests/turntable_face_host.py`,
`tests/test_turntable_face.py`, `tools/turntable_face_candidate.py` och
`tools/turntable_face_visuals.py`. Full ändringslista finns i scope-manifestet.
C3-drift och [nattöverlämningen](lead-handoff-2026-10-18-night.md) är separata
nya dokument; nattnoten tillkom efter frysen och ändrar den inte.

Bevis under `build/turntable-face-2026-10-18/`, SHA-256:

| Fil | SHA-256 |
| --- | --- |
| `source-frozen.json` | `09C57C0CC4942B30EE48E5925F9332DE7353809D849EF30EFD2EEDFB2F485320` |
| `firmware-verification.json` | `7C05FBD454A058459C3E243DB59B6F35CDA55B3DB582C0F5894DAF10B41F977C` |
| `scope-verification.json` | `92EAF411D673E8A00DCB41C4D58E332D1848CDC6AA9C37AC4FAEAB456F4022AD` |
| `candidate.json` | `EE03FAA7F5EF58698039ABECBE96D4301A77C22AA1FDB24A77B1DC563B244A9C` |

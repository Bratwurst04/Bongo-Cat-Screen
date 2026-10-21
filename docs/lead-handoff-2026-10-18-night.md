# Nattöverlämning – Bongo Cat – 2026-10-18

## Roller och arbetsyta

Arbeta endast i `D:\DEV\Ai\Github\Bongo-Cat-Screen`; använd inte OneDrive.
Lead ändrar inga projektfiler; Code äger kod och projektdokument. Lead sköter
UI-samordning, granskning och eventuellt godkänt runtimebyte/flash.
Ingen ny chatt skapas nu.

| Roll | Chatt-ID |
| --- | --- |
| Lead | `01a14061-2445-7cc0-9178-79fb0625be18` |
| Code | `01a0ec49-da6f-7b00-be86-06822053344a` |
| UI Code | `01a11581-4a2c-7e80-9742-adcd989df5ca` |
| Idébollplank | `01a14fba-80ff-7eb1-b3a0-d75492f7bdc3` |

## Faktiskt installerat

- Companion **FD9D811B**, 19 659 276 byte, SHA-256
  `FD9D811B0356818A56AA0787AD3041820DA8D45D6083D8E0E822D3B59426DB06`.
- Firmware **C6EBAE4B**, 936 704 byte, SHA-256
  `C6EBAE4B13DE934449E2F32738D2CBFAEEC2693C5ECF8EE8A3A71FDB6254D275`.
- Driftbaud **921600**. Senaste appbyte bevarade profil/inloggning/Run/genvägar;
  senare normal access-/expiryförnyelse behöll refresh-token. Ingen ny flash.

[C3-driftprovet](capability-startup-runtime-2026-10-18.md) visar tre lyckade
kompakta första försök: READY→ACK **1 164 ms** vid appstart, **374/351 ms**
vid två låtbyten, ART_SENT 12 800 byte. Användaren: ”Ja, snabbt och bilden ser
bra ut”. Första överskred en sekund. Ingen ART_CAPABILITY_RESEND loggades:
initialfrågan fungerade, **fallbackens fysiska väg är inte bevisad**.
Ingen generell garanti för mobil→skärm, alla omslag, sleep/resume eller långdrift.
Äldre C2-prov visar fullformat och får inte blandas ihop med detta resultat.

## Endast byggd nästa firmware

Användaren vill behålla gammal synlig framsida tills skivan är mitt i flippen
eller helt ur bild vid komplett exchange. Han sade uttryckligen
**”flash är imorn”**. **Ingen flash ikväll och inget exakt godkännande för
5556B647 finns ännu.** Installerad runtime lämnas igång/oförändrad.

- Kandidat [turntable-face-2026-10-18-5556B647.bin](../.pio/candidates/turntable-face-2026-10-18-5556B647.bin),
  **936 800 byte**, SHA-256
  **5556B647EEEC5D41165F0F518E7FC8B0B5FAC2AA645931F278C01F9D12A182A4**.
- Profil `esp32-024r-spotify-compact80`; companion FD9D811B bytebevarad.
- [Byggrapport](turntable-face-2026-10-18.md),
  [kandidatmanifest](../build/turntable-face-2026-10-18/candidate.json),
  [källmanifest](../build/turntable-face-2026-10-18/source-frozen.json),
  [scope](../build/turntable-face-2026-10-18/scope-verification.json),
  [firmwarebevis](../build/turntable-face-2026-10-18/firmware-verification.json).
- Kandidatmanifest SHA-256
  `EE03FAA7F5EF58698039ABECBE96D4301A77C22AA1FDB24A77B1DC563B244A9C`.
- [r1-preview](../visuals/turntable-face-2026-10-18/r1/index.html) godkänd av
  Lead/UI endast som hostsimulering, manifest
  `0160F29A7685A297319FE513BDD2DB7E42031151152D3822F0F5F622EF1B3A0B`.

Källan håller gamla sloten pinnad till 870/1 070 ms; CRC-godkänd staging
ACK:as utan animationsväntan. En ersättbar senaste identitet kan invänta nästa
dolda brytpunkt. Frame-gap ger en tunn/osynlig pose före full ny bild; det
bevisar inte jämn TFT-animation. 135 riktade tester: **133 PASS/två kända
SDK-skip**, noll fel/externa nätförsök. 185 frysta källfiler, 72 Python,
7 796 bytebevarade äldre filer. **Ny animation är inte fysiskt accepterad.**

## Nästa aktiva steg 2026-10-19

1. Invänta användarens flashbegäran/godkännande för exakt 5556B647-hash.
2. Stoppa aktuell companion säkert utan pågående omslag; BOOT enligt behov.
3. Läs och hashverifiera backup av installerad C6-app: **936 704 byte**,
   full C6-hash ovan. Skriv sedan enbart app vid **0x10000**, upload **115200**;
   bevara NVS, profil, Run-post och genvägar. Verifiera skrivningen.
4. Normal reset och återstart av samma companion. Kontrollera gammalt omslag
   till kanten, early/late art, snabba retargets och komplett exchange.
   Prova även Fokus/DJ/meny, gester/åäö, omslags-ACK, sleep/resume och långdrift.
   Skilj kvittens av staging från faktiskt synlig bild och mät separat vid behov.

Seek är borttaget. Spotify-felsökningen är pausad. Ingen release, commit,
push eller profil-/API-förändring ingår. Alla tidigare kandidater/rapporter/
previews/frysningar bevaras. Denna not skapades efter slutlig källfrysning;
frysningen ändrades inte.

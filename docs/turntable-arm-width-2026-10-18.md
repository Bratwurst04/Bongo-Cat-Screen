# Lite tjockare vit kattarm – 2026-10-18

Efter flash av 627E6B93 svarade användaren ”Ja. Armen kan bli lite tjockare”.
Den fysiska bekräftelsen och omslagsleveranserna är bevarade i
[driftrapporten](turntable-arm-tempo-runtime-2026-10-18.md).
Installerat är fortsatt **companion 68721143 / firmware 627E6B93**.

## Separat ändring och prov

Endast den vita underarmen är lite tjockare: bakre totalhöjd **12→16 px**,
vit kärna **8→12 px**; handledstaper **10→12 px**, vit kärna **6→8 px**.
Svart kontur är två pixlar. Den tjocka delens skarv hålls utanför klippkanten
när handleden fortfarande är utanför bilden, så inga vita rester uppstår.
Tassmask, nål/tonarm, tider 1880/2380 ms, grepp, lyft och sänkning är
byteidentiska i övrigt. State/projektion och transport/minne ändras inte.

**23/23 befintliga riktade raster-/stateprov PASS**, utan skip eller externa
nätverksförsök. Första körningen upptäckte små vita rester vid vänsterkanten;
skarvgränsen rättades och samma prov passerade. Båda loggarna finns kvar.
Inga nya speglingstester eller breda regressioner lades till för denna
geometriändring. Tidigare breda resultat hör till den föregående kandidaten.

Fastserialbygget passerar, med omkompilering av huvudobjektet efter
gränsrättningen och återanvänd befintlig bibliotekscache: **47,637 s**.
RAM **112 408 byte (34,3 %)**, program **935 521 byte (47,6 %)**.
Bildens checksum/validation är giltiga. UTF-8 och `git diff --check` passerar
(endast befintlig LF/CRLF-varning för Fokus-testfilen).

## Kandidat och spårbarhet

Ny app: `.pio/candidates/turntable-arm-width-2026-10-18-9961C753.bin`,
**936 256 byte**, fastserial 230400, appadress `0x10000`.
SHA-256: **9961C7537A467B53EBF84C0EC1A361A89098952B4000F3082B7EF0E36A3C069A**.
**Endast byggd, inte flashad, inte fysiskt provad eller flashgodkänd.**

Separat källa/manifests/loggar: `build/turntable-arm-width-2026-10-18/`.
167/167 aktuella/frysta källor och 1789/1789 skyddade tidigare filer matchar
vid slutverifieringen. Tidigare 627E6B93/3606F2E0, båda byggunderlagen, driftrapporten,
gamla test-/previewhjälpare och r1 har bevarats. Historiska statuskopior i
deras manifest skrivs inte om när aktuell toppstatus uppdateras.

Produktkod ändrad: fem rader i `src/media_turntable.h` (fyra armrektanglar
och skarvens klippgräns). Ny hjälpare `tools/turntable_arm_width_candidate.py`
styr befintliga tester/förhandsbilder till separat utdata och fryser källan.
Därtill endast aktuella toppstatusar i 00/01/02 och denna rapport.

[R2-förhandsvisning](../visuals/turntable-arm-tempo-2026-10-18/r2/index.html)
och [före/efter normal/Fokus](../visuals/turntable-arm-tempo-2026-10-18/r2/arm-before-after.png)
använder faktisk C++-geometri och oförändrade tidskonstanter. R1 är installerade
armens simulerade referens. Simulering bevisar ingen verklig TFT-takt eller
fysisk acceptans av den nya bredden. Ingen runtime-, companion-, protokoll-,
API-, flash-, installations- eller releaseåtgärd har gjorts i detta steg.

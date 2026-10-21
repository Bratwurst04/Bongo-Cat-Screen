# Normal viewportfirmware installerad – driftprov 2026-10-21

Installerat är nu **companion C42112AD / normal firmware 61BE3B63 vid 921600**.
Diagnos **1252EBAC är fortsatt endast byggd och oflashad**. Användaren rapporterar
en partiell förbättring av rullningen; skillnaden mot paus finns kvar.
Ingen fullständig rullnings-/UI-acceptans eller uppmätt FPS påstås.

Alla klockslag nedan är svensk tid, UTC+02. Detta dokument beskriver ett nytt
runtimeprov efter [byggunderlaget](render-viewport-2026-10-20.md) och
[handoffen](lead-handoff-2026-10-21.md). Äldre frysta rapporter, kandidater och
kvittomanifest bevaras som historik; deras föreflashstatus skrivs inte om.

## Tillstånd och exakt installerat

Användaren gav Lead 5 uttryckligt tillstånd:

> Ja kör, jag är vid skärmen nu. Flasha rullningskandidaten61BE3B63 med backup så testar vi.

Lead genomförde backup, separat enhetsverifiering och skrivning av **normal-
kandidaten**, inte mätprofilen. Code har bara läst det avsedda säkra kvittot.
Ingen ny kod, byggning, COM-/profil-/runtimeåtgärd eller flashning gjordes av Code.

| Del | Byte | SHA-256 |
| --- | --- | --- |
| Oförändrad installerad companion C42112AD | 22 856 796 | `C42112AD2C774B0814B40B688AE8FA80BD0858D1308DA9130719362492CAC135` |
| Ny installerad normal firmware 61BE3B63 | 937 600 | `61BE3B633AF700B27F0DDF55F9B26D41E1B9E0916F187848A470B50988701440` |
| Föregående firmware EBB334A9 | 937 184 | `EBB334A926709E047DA1D930684C76D02DFA162332C508E775F062AE492E2FF3` |
| Oförändrad, endast byggd diagnos 1252EBAC | 938 400 | `1252EBAC2C3CBFEC4915DADB172CC06DB5799DF7E0482B17710E474DD4274C33` |

Normalfilen är `dist/firmware-2026-10-20-render-viewport-dev/normal-compact80.bin`.
Diagnosen ligger i samma katalog som `render-diagnostics.bin`.
Normal drift är **921600**, flashningen använde **115200** vid **0x10000**.
Den kanoniska appen är fortsatt `%LOCALAPPDATA%\BongoDesk\BongoDeskSpotify.exe`.

## Backup och verifierad skrivning

- En **ny 942 080-byte appsektorbackup** lästes från `[0x10000,0xF6000)`.
  Prefixet matchade exakt EBB. Hela backupens SHA är
  `855CAF3A40715512E46D4B1EC5FA0367E75E0AFD35A8940897E48E1F233DD896`,
  byteidentisk med den äldre skyddade backupen. Ny läsning tog **87,118 s**, exit 0;
  kvittot tidsstämplades **11:16:10,770**.
- Separat `verify_flash` jämförde backupen mot enheten och gav matchande digest:
  **3,706 s**, exit 0, kvitto **11:17:19,572**. Ett nytt verifierat rollbackunderlag
  finns alltså; ingen återställning till EBB har utförts efter denna 61BE-flashning.
- Första automatiska bootförsöket misslyckades före skrivning. Användaren gjorde
  BOOT+RESET; därefter lyckades läsning, verifiering och skrivning.
- Flash: **42,937 s**, exit 0, `Hash of data verified`; kvitto **11:18:31,609**.
  Bara appsektorer skrevs. **Ingen bootloader eller NVS skrevs.**
- C421-EXE och fyra aktuella profiler säkerhetskopierades privat och var
  oförändrade vid flashningen. Run och befintliga genvägar bevarades.
  Privata backuper/journaler/loggar har inte lästs eller publicerats av Code.

## Återstart, kontakt och kvittenser

Den vanliga Startmenygenvägen med `--minimized` startades via Explorer.
Första observationen hade en Explorerförälder, som senare hade avslutats normalt.
Två normala appprocesser och korrekt C421-hash bekräftades i Leads observationer;
det är inte en ny appinstallation.

- `APP_START`: **11:18:48,991**.
- Första serieöppningen misslyckades **11:18:51,156**; andra lyckades
  **11:18:55,288**. Återanslutningen fungerade utan appbyte.
- Resync, två lyckade fulla **legacy-ACK** och bas-/kompaktkapabilitet loggades.
  De två 37 632-byte sändningarna var **4962/4976 ms** på sändarsidan.
  Uppstartsjobben var legacy; detta bevisar ingen ny kompakt-/refinementfart
  och inga uppmätta LCD- eller skärpningstider.
- Statusavläsning **11:19:46,050**: filålder **0,996 s**, ESP ansluten,
  uptime **54 s**, ESP-statusålder **1,013 s**, CPUdiagnos **false**.
  Windows Spotify var tillgänglig och aktiv källa. Apphash, config mot backup,
  Run och genvägar matchade. Händelselistan i kvittot omfattar även senare
  resync-/cap-händelser; de är inte del av just denna statusögonblicksbild.
- Slutkompletteringen **11:23:42,681** visar fortsatt kontakt, filålder
  **0,217 s**, uptime **231 s**, ESP-statusålder **1,013 s**, heap **153 976 byte**
  och CPUdiagnos **false**. Windows Spotify är fortsatt tillgänglig/aktiv;
  apphash, config mot backup, Run och genvägar matchar. Även art2-kompakt och
  efterföljande refinement med lyckade ACK finns i kompletteringen. Detta ger
  inga uppmätta LCD-/skärpningstider eller generell hastighetsgaranti.

## Fysiskt delresultat

Användaren svarade om rullningen:

> Bättre men fortfarande skillnad mot när den är pausad

Det är **kvalitativ partiell förbättring**, inte ett löst rullningsproblem,
likvärdig spelande/pausad vy, FPS-/CPU-mätning eller generell animationsacceptans.
Den syntetiska minskningen av flushyta i byggunderlaget är fortfarande ett
separat hostmått och får inte användas som fysisk prestandasiffra.

På frågan **”Efter två låtbyten, senare skärpning och ett menybesök: ser omslag,
arm och tass normala ut utan kvarlämnade bildrester?”** svarade användaren:

> Ja, allt ser normalt ut

Det är **snäv fysisk acceptans av just två låtbyten, senare skärpning,
arm/tass och återgång efter meny**, utan observerade bildrester i det provet.
Det är ingen full touch-/animationsregression eller garanti mot bildrester i
alla situationer. Exakt jämnhet, snabba följdbyten, Fokus-/DJ-avbrott,
sleep/resume och långdrift återstår. Normal **61BE behålls installerad**.

Färgkedjan har inte ändrats av denna kandidat;
[bildkvalitetsutredningen](artwork-quality-2026-10-21.md) är ett separat underlag
och ger ingen ny fysisk färgacceptans.

## Säkert underlag

Endast de två avsedda projektexemplaren har lästs under
`build/viewport-runtime-evidence-20261021-1112/`:

| Säkert kvitto | SHA-256 |
| --- | --- |
| `viewport61BE-runtime-safe.json` | `539B0AD3FEDCE40CCF542FF8D94516BED6AB96BE9A809F428881019EF7837B48` |
| `viewport61BE-final-safe.json` | `AD5CEBCEE6E87565FBDCEC08554F243835A04828C0C44C5BA1E6BFB8B3257E75` |

Kvittona innehåller begränsad numerisk status och tillåtna händelser, inga tokens,
profilfiler, låttexter eller privata backupinnehåll. Privata logg-SHA i kvittot
identifierar Leads operationer; de loggarna har inte öppnats av Code.

Sluttexten bygger på grundkvittot och Leads säkra komplettering med användarsvaret.
Nästa rendersteg behöver ett separat avgränsat underlag. Normalprovet ovan
omfattade inget godkännande för **1252EBAC**. Användaren har därefter separat
godkänt en tillfällig mätning med 1252 och återgång till 61BE. Den mätningen
är inte genomförd i detta dokumentationsögonblick och hanteras av Lead ensam.
Dokumentpubliceringen ändrar ingen produktkod eller installation; ingen release ingår.

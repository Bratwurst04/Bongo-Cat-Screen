# Bongo Cat app-v1.3

Förberedd och installationsverifierad 2026-10-07. Projektledaren hanterar publiceringen.

## Nytt

- Spelaren har större 172×172 px omslags-/vinylvy och stabil lokal tidslinje även under omslagsöverföring.
- Omslag använder förhandlat art2 med överförings-ID, längd och CRC. Snabba låtbyten avbryter gamla bilder; begränsade omförsök använder den cachelagrade bilden. Äldre råprotokoll finns kvar.
- ESP32 läser och ramar in serialdata på kärna 0, medan skärm, touch, omslagsvalidering och svar hanteras på kärna 1. Provade första omslagsöverföringar tog cirka 5,0–5,6 sekunder med jämn Spelare under laddning.
- Windows companion har Översikt, Inställningar och Diagnostik i samma visuella stil som skärmen. Avancerade val är hopfällbara, och ändringar har validering, Spara och Ångra.
- Nya companionprofiler och standardfirmware använder **230400 baud i drift**. Flashning använder **115200 baud**. Befintliga profiler ändras inte automatiskt.
- Fokus, lokala inställningar, Bongo-animationer, touchgester, media och den separata tiominutersgränsen för deep sleep finns kvar.

## Filer och kontrollsummor

| Fil | Byte | SHA-256 |
| --- | ---: | --- |
| `BongoDesk-app-v1.3-2026-10-07-app-0x10000.bin` | 926432 | `6A5366C1E56E1137AEBC08E6675CBB12E1A49AE106D2DBD03B30132C6A7D2302` |
| `BongoDesk-app-v1.3-2026-10-07-full-0x0.bin` | 991968 | `FE44F339D85084B9F9028AAE3146A12E78D3C0F87161425BB01B3989A7CAF491` |
| `BongoDeskSpotify-app-v1.3-2026-10-07.exe` | 19299418 | `5609B99DAA1321ECB78B6384F1D5271DB23DBBF1BD6A2E2BBB49D6FD7AFEFD1D` |

Appfilen är exakt den app som flashades och provades vid `0x10000`. Fullbildens segment och mellanrum är filverifierade; **den nya fullbilden har inte flashats från `0x0`**. Companionfilen är byteidentisk med den installerade releasekandidaten, som återanslöt på första försöket och fick en lyckad omslagskvittens efter 4859 ms sändning. Ingen ny visuell UI-genomgång gjordes; UI-resurserna är identiska med den redan visuellt provade versionen. Windows-EXE:n är osignerad. Personliga profiler, OAuth-token och backuper ingår inte.

## Uppgradering

1. Avsluta companionen via **Exit** och stäng serialmonitorer.
2. För en enhet med samma partitionstabell: använd appfilen vid **`0x10000`** för att bevara NVS, inklusive sparade Fokus-/temaval. Fullbilden vid **`0x0`** används för komplett installation och skriver över NVS i sitt adressintervall; säkerhetskopiera NVS om inställningarna ska återställas.
3. En befintlig profil behåller sitt gamla baudvärde. Med companionen stoppad, ändra endast `connection.baudrate` till **230400** i `%APPDATA%\BongoCat\config.json` när du använder v1.3-firmwaren. Behåll övriga inställningar och Spotify-kopplingen. Nya profiler får 230400 direkt.
4. Starta v1.3-companionen och kontrollera tid/statistik, Spelare och omslag. Båda delarna behövs för mediedata och väckning.

Se [flashinstruktionerna](https://github.com/Bratwurst04/Bongo-Cat-Screen/blob/app-v1.3/README.md#flasha-från-windows) och [verifieringsrapporten](https://github.com/Bratwurst04/Bongo-Cat-Screen/blob/app-v1.3/release/app-v1.3-verification.md). Äldre releaser finns kvar separat.

## Verifieringens gränser

Player, rätt sista omslag efter snabba byten och touch under laddning är fysiskt bekräftade på den exakta firmwareappen. Sömn/väckning på samma firmware har en kvalitativ användarbekräftelse; exakta släcknings-/väcktider, ström och en fullständig ljusblixtkontroll är inte uppmätta på v1.3-paret. Framtvingad felåterhämtning på denna firmware, återhämtning efter ny verklig Spotify-429 samt verklig DPI-/skärmläsarprovning av Windows-UI:t är inte separat provade. Syntetiska förhandsbilder är inte hårdvaruresultat.

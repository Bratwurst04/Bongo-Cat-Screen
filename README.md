# Bongo Cat för ESP32-024R

Firmware för en ESP32-024R med 240×320 ILI9341-pekskärm och en Windows
companion som skickar tid, systemvärden, mediastatus och albumomslag via serial.
ESP32 visar Bongo-animationer, en gemensam panelmeny och en mediasida med
omslag, vinyl och DJ-katt.

> [!Important]
> Vibe-coded project made by me

## Aktuell release: app-v1.2 (2026-10-03)

Ladda ned den [kompletta firmwarebilden](release/BongoDesk-app-v1.2-2026-10-03-full-0x0.bin)
och dess [SHA-256-fil](release/BongoDesk-app-v1.2-2026-10-03-full-0x0.sha256)
för flashning vid `0x0`. Bildens SHA-256 är
`B25028C1995AEFA81C99123133FA0A24898D2DA264DBBF2CDA9A2DBA3345B095`.
Den innehåller bootloader vid `0x1000`, partitionstabell vid `0x8000`,
`boot_app0` vid `0xe000` och appen vid `0x10000`. Appens SHA-256 är
`F0F7EC82E28AB30607EC59A8409B4B4876578D869403753C09DD33F3747FCFEF`:
exakt den appbinär som flashades på COM6 och provades den 2026-10-02.
Hela den sammanslagna bilden verifierades mot byggfilerna och flashades sedan
på COM6 från `0x0` den 2026-10-03. Esptool verifierade bilden i flash. Den
tidigare NVS-partitionen säkerhetskopierades, återställdes och lästes tillbaka
med identisk SHA-256. Användaren bekräftade normalt UI utan ljusblixt.
Detaljer finns i [verifieringsrapporten](release/app-v1.2-verification.md).

Ladda ned [Windows companion](release/BongoDeskSpotify-app-v1.2-2026-10-03.exe)
och dess [SHA-256-fil](release/BongoDeskSpotify-app-v1.2-2026-10-03.sha256).
EXE:ns SHA-256 är `71756E01987D8A84C76DDCF83B76E9C512A7B5B2E09439DB94D10E36109ABF9F`.
Den är byteidentisk med den installerade versionen som visade aktuell låt,
rätt omslag och fungerande play/paus och NEXT med lokal Spotify på datorn,
även efter flera snabba låtbyten. EXE:n är osignerad och innehåller inga
personliga inställningar eller Spotify-token. Båda delarna behövs för
skärmens mediedata. Se [release notes](release/app-v1.2-notes.md) för
status vid publiceringen och [verifieringsrapporten](release/app-v1.2-verification.md)
för det senare fullbildsprovet och återstående mätningar.

`app-v1.1` och panelmenyreleasen från 2026-09-24 finns kvar som historiska
filer. En fullständig flashning från `0x0` raderar enhetens tidigare NVS-värden,
bland annat sparade fokus- och pausval. Ta backup av NVS före fullbildsflash;
i provet 2026-10-03 återställdes backupen före normal start.

### Lokalt utvecklingsprov 2026-10-05

En senare artwork-v2-app med SHA-256
`636AC267AEDCC4DF1B83693F5B4DCE41DE04C7EB37B8F3D2F3DDDF2740B85AB5`
har efter särskilt godkännande flashats på COM6 vid `0x10000`; esptool
verifierade skrivningen. Den tillhör **inte** den publicerade `app-v1.2`-bilden.
Installerad companion fungerar fortsatt med normalt UI, tid/statistik,
Spotify-låtbyte och omslag. En oinstallerad v2-companion kördes tillfälligt;
användaren såg rätt sista titel och omslag efter snabba byten från skärmen.
Den tidigare installerade companionen återställdes efter det första provet.
En senare diagnostik-EXE bekräftade art2-handskakningen mot samma ESP32 och
installerades sedan efter särskilt godkännande med verifierad backup av den
föregående EXE:n. Det var ett tidigare prov; den senare tidslinjeversionen
nedan är nu installerad. Exakt latens och mörk timerväckning med denna app är
ännu inte fysiskt verifierade.
Se [aktuell status](01_CURRENT_STATE.md) för detaljer och begränsningar.

En senare korrigering av Spelarens tidslinje och en större 172×172 px omslagsvy
är nu lokalt flashad och installerad efter fysiskt prov. Firmwareappen vid
`0x10000` har SHA-256 `ACA0E8ED6575D30B8F0010F5C79F1614CB02C6CCACDC691F225B3E38CF662297`;
installerad companion har SHA-256
`57E288E1D8120AA04E00D7EC235D9C28E7DC1021E2FC3AD7F48849683AF6A877`.
Användaren bekräftade stabil låttid, rätt omslag, layout och gester. Två
snabba låtbytessekvenser gav sammanlagt fyra art2-felkvittens; senare omslag
lyckades och rätt sista omslag syntes. Den publicerade `app-v1.2`-releasen är
fortfarande äldre än dessa lokala installationer.

Den lokala driftlänken kör nu 230400 baud med den valfria firmwareprofilen och
en ny installerad companion som skickar två art2-rader per skrivning. Flashningen
gjordes fortsatt vid 115200 baud. Ett direkt test på samma ESP32 gav
9,14–9,16 sekunder för gammal rytm och 4,94–5,02 sekunder för fyra överföringar
med ny rytm; samtliga testbilder kvitterades. Tidigare firmware, konfiguration
och companion finns som verifierade backuper. Den installerade EXE:n har
SHA-256 `D9187CC406912B142CA1E5F042A6CCD875B051F1D7F62AA2B8918E5190D1CB43`
och återanslöt till COM6 med art2. Ett nytt omslag från Spotify på datorn har
ännu inte provats med denna EXE eftersom Spotify inte kunde startas under
slutprovet. Se [aktuell status](01_CURRENT_STATE.md).

Den 2026-10-06 lyckades fyra verkliga Spotify API-omslag på omkring 5,6 s,
men en senare låt blev utan omslag efter två art2-felkvittens. Samma installerade
EXE fick ett lyckat omslag efter manuell omstart. En senare kandidat med
begränsade omförsök och fasta mottagarfelkoder installerades som ett par:
firmware `CF5F4DCDD6D40091CC04C06E70DF134A3F079BF31D733BA71CDF732D5FB6CACA`
och companion `41BE575EDAD6F58346D034555D8B5430941E01E78490608A497C66FC142558B4`.
Under ett nytt fysiskt prov avvisades fyra försök på samma låt med rad- och
avkodningsfel, medan text och skiva hackade under överföringen. En ny
firmwareversion läser kompletta serialrader i begränsade grupper för att minska
köbildning utan att blockera Player och touch. Efter verifierad backup av den
föregående appen har denna version med SHA-256
`4376ED12820E4906ADA44F429B624B6F9A1C38EBB6AB084B0DA7ED7B2CCA5B67`
flashats endast vid `0x10000`. Vid det fysiska provet avvisades tre snabba
omslagsöverföringar; långsamma omförsök gav rätt omslag efter cirka 17–19
sekunder, men ett senare spår misslyckades även på långsamma omförsök.
Skiva och text frös kort under överföring.

Den nya **lokalt flashade och Player-provade versionen** läser serieporten på ESP32:s andra
kärna och skickar kompletta textrader och äldre råa omslagsblock via en ordnad
kö till skärmuppgiften. Skärm, touch, omslagskontroll och seriella svar ägs
fortfarande av samma uppgift. Binären i
`.pio/build/esp32-024r-spotify-fastserial/firmware.bin` är 926432 byte med
SHA-256 `6A5366C1E56E1137AEBC08E6675CBB12E1A49AE106D2DBD03B30132C6A7D2302`.
Projektledaren flashade den frysta kopian endast vid `0x10000` efter verifierad
backup av den tidigare appen; esptool verifierade skrivningen och NVS bevarades.
Efter normal reset och återanslutning lyckades minst fem art2-överföringar
på första försöket efter cirka 5,0–5,6 sekunder, med ACK efter 8–35 ms.
Användaren bekräftade rätt omslag efter ungefär fem sekunder vid tre låtbyten
och jämn Player-rörelse under laddningen, jämfört med tidigare 17–19 sekunder
och korta frysningar. Snabba avbrott gav rätt sista låt/omslag utan äldre
återkomst, och touch, paus, DJ, panelmeny och Fokus fungerade under laddning.
Mörk sömn/deep wake med tvåkärneversionen är ännu inte testad och återstår
före release; se [aktuell status](01_CURRENT_STATE.md).
Den publicerade releasen är oförändrad.

## Föregående app-v1.1: firmware

Den tidigare fullbilden [BongoDesk-deep-sleep-2026-09-30-full-0x0.bin](release/BongoDesk-deep-sleep-2026-09-30-full-0x0.bin)
flashas från adress `0x0`. Tillhörande kontrollsumma finns i
[.sha256-filen](release/BongoDesk-deep-sleep-2026-09-30-full-0x0.sha256):

```text
SHA-256  7908115A4FD4D25E78E7BB46189DE57D8C044C63179AB9DD9D7E5C5CAC03CD6C
```

Bilden innehåller bootloader vid `0x1000`, partitionstabell vid `0x8000`,
startdata (`boot_app0`) vid `0xe000` och appen vid `0x10000`. Appen är
byte-identisk med utvecklingsversionen som laddades till användarens ESP32
den 2026-09-29: SHA-256
`AF51B963A5A3D8240D1DAD577D4DA3A9B5A94D930EEB02EA8E5C6D0329AF9E8C`.
Den sammanslagna bilden har verifierats i fil men har ännu inte flashats från
`0x0`.
Den lokalt flashade Fokus v2-appbinären som beskrivs nedan ingår inte i denna
nedladdningsbara `app-v1.1`-release.
Den äldre `release/BongoDesk-spotify-v6-stable.bin` är **inte** aktuell
firmware. Den äldre `release/BongoDeskSpotify.exe` är **inte** byggd från
nuvarande companion-kod. Båda äldre filerna ligger kvar lokalt men ignoreras
av Git.

## Föregående app-v1.1: Windows companion

Den tidigare companionen finns som
[BongoDeskSpotify-deep-sleep-2026-09-30.exe](release/BongoDeskSpotify-deep-sleep-2026-09-30.exe)
med tillhörande [.sha256-fil](release/BongoDeskSpotify-deep-sleep-2026-09-30.sha256).
EXE:ns SHA-256 är `65D3DAEAFAA4E1CE87A5F9FE52F66923B832E46D8DFBC56917F60EBD6A25128C`.
Den byggdes från dåvarande companion-kod med projektets ordinarie
`BongoDeskSpotify.spec`; inga personliga inställningar eller Spotify-token
ingår. EXE:n är inte kodsignerad, så kontrollera hashen före start. Både denna
companion och ESP32-firmwaren behövs för mediedata och albumomslag.

Källkoden för companion har därefter fått en separat diagnostikkandidat med
roterande händelseloggar, manuell ZIP-export i systemfältet och begränsad
återhämtning för uteblivet albumomslag. Den installerades separat 2026-10-01;
användaren såg normalt UI och en ny exporterad ZIP. Den fanns inte i
`app-v1.1`, men diagnostiken ingår i `app-v1.2`. Framtida omslagsfel har ännu
inte provocerats fysiskt. Se [companion/README.md](companion/README.md) för mer information.

Den 2026-10-02 uppstod en lång Spotify-429-väntan medan uppspelningen skedde
på telefonen. Windows hade då ingen lokal Spotify-session som kunde ge
låtinformation till Spelaren. En ny companion-kandidat visar väntstatus och
tid för nästa försök via de befintliga mediefälten, begränsar automatiska
API-läsningar utan lokal Spotify-session till minst 15 sekunders mellanrum
och loggar nästa verkliga 429 med säker, begränsad orsaks- och
anropsstatistik. Kandidaten `dist/companion-2026-10-02-429-dev/BongoDeskSpotify.exe`
har SHA-256 `2F5CA6524307985405751577C2E83FD47D366CFD3E79AA55B7A6978FF328B38E`.
Efter 28 godkända companion-tester installerades den separat 2026-10-02 med
säkerhetskopia av tidigare EXE. Två processer, COM6 och sparad 429-väntan
bekräftades efter start. Användaren såg väntstatus på Spelaren och normalt
Bongo-UI med tid/statistik. Låt- och omslagsåterhämtning när Spotify-spärren
löper ut återstår att prova. Vid detta prov var `app-v1.1` oförändrad;
väntstatus och pollbegränsning ingår nu i `app-v1.2`.

Ett senare prov med Spotify på datorn visade gamla låtar, uteblivet omslag
och touchkommandon som inte påverkade Spotify. Källan har därför en ny,
separat companion-kandidat som håller lokal Spotify-status sammanhängande
under omslagsöverföring och loggar om touch når appen och accepteras av
Windows. Vid ett tillfälligt källprov fungerade paus/återuppta och låtbyte
med rätt titel och omslag på skärmen. Efter separat godkännande installerades
den ombyggda EXE:n med extra återanslutningsskydd och säkerhetskopia av den
förra. Användaren bekräftade aktuell titel och omslag samt play/paus och
nästa låt på den installerade versionen. Se [companion/README.md](companion/README.md).

Stäng först en redan körande Bongo Desk-app med **Exit** i systemfältet så att
endast en companion använder serialporten. Starta sedan den nedladdade EXE:n
med dubbelklick och välj rätt COM-port i inställningarna om `AUTO` inte hittar
enheten. Appen använder samma instanslås och användarprofil som tidigare
versioner. När den startas normalt kan den befintliga autostartposten peka om
till den körda EXE:n om autostart är aktiverad i användarens inställningar.
Se [companion/README.md](companion/README.md) för hur ett eget Spotify-konto
kopplas till profilen.

### Historisk verifieringsstatus för app-v1.1

- Firmware byggdes från den dåvarande deep sleep-källkoden med `esp32-024r-spotify`: RAM 33,9 %, flash
  38,8 %. Appbinärens hash matchar exakt den som flashades till `0x10000` via
  COM6 den 2026-09-29; esptool verifierade då skrivningen.
- Den dåvarande fullbildens fyra delar och adresser har kontrollerats mot byggfilerna,
  och appens checksummor är giltiga. Fullbilden har ännu inte flashats från `0x0`.
- Alla 14 companion-tester passerade. EXE:n har provats på COM6, installerats
  lokalt och visat aktuell statistik, albumomslag, meny och panelbyte.
- Användaren rapporterade fungerande Windows sleep/resume och ett senare
  shutdown/power-on-prov. Vid shutdown-provet var uppgiften att låta datorn
  vara avstängd minst elva minuter och kontrollera mörk skärm före start och
  UI inom ungefär en minut efter inloggning; svaret var ”Det funkar”. Det är en
  kvalitativ observation utan uppmätt släcktid, väcktid eller deep sleep-ström.

## UI-firmware i app-v1.2: Fokus, inställningar och Spelare

Källkoden har nu ett fjärde val, **INSTALLNINGAR**, i den gemensamma menyn.
Där väljs grön, cyan eller amber accent, automatisk visning av Fokus vid
fokusslut och pausslut samt LED-signal vid fasslut. Standard är grön, automatisk
visning av och LED på. Dessa val lagras i en separat, validerad NVS-nyckel och
påverkar inte sparade fokus- och paustider. TILLBAKA återgår till panelen som
var öppen före inställningsvyn. Den nya vyn använder ASCII-etiketter eftersom
firmwarens inbyggda font saknar svenska Ä.

Fokus visar en båge för förfluten andel av den pågående fokus- eller pausfasen.
En pågående fas behåller sin ursprungliga längd och återstående tid när ett
framtida tidsval ändras. TIDER-vyn har nu två tydliga kort med plus ovanför
minus och 44 pixlar höga tryckytor. Tryckta meny- och Fokusknappar får visuell
återkoppling; ett tryck avbryts om fingret glider ut eller en automatisk
panelväxling sker under trycket. Befintliga Bongo- och Spelargester, media,
omslag, companion-närvaro och deep sleep ska bete sig som tidigare.

I denna UI-version är Spelarens omslags-/vinyl-/DJ-cirkel centrerad
och 148×148 pixlar. Själva omslagspaketet är fortfarande 112×112 och DJ-duken
64×64; bara visningszoomen ändras. En högre informationsyta ger titel, artist,
förlopp och tidsmarkörer egna rader, med separat status och gesthjälp under.
Långa texter behåller LVGL:s enradiga cirkulära rullning. Menyn har nu en
heltäckande mörk bakgrund så att underliggande TIDER-knapp inte syns över
menykortet. Inga media- eller seriekommandon ändras.

Den första UI-appbinären, SHA-256
`21E7FADA09689CD87F1194BE1A0DE453D0FAC28EE53A9165385368C40F699514`,
flashades på COM6 vid `0x10000` natten till 2026-10-02 efter uttryckligt
godkännande; esptool verifierade skrivningen. Användaren såg normalt UI,
omslag, fyrvalsmeny och Spelare med cyan accent, gester och DJ utan ljusblixt.
Ett touchfel upptäcktes: TIDER ritades uppe till höger men öppnades med tryck
uppe till vänster. START och NOLLA fungerade. Kortets horisontella råaxel är
spegelvänd, så källans knappmappning har rättats.

Den rättade kandidaten byggdes med `esp32-024r-spotify`: RAM 34,0 %, flash
46,8 %. Appbinärens SHA-256 är
`1177E1F583B9C560B593FF8E0EEE9AC5864A6D332A3D860C615D8C79BBBFCBA2`.
Kompilerade Fokus-gränstester, 23 companion-tester och export av 32
[simulerade 240×320-vyer](visuals/contact_sheet_composed.png) passerade.
Efter ett nytt, hashbundet godkännande flashades den rättade appen på COM6
vid `0x10000` den 2026-10-02; esptool rapporterade `Hash of data verified`.
Installerad diagnostik-companion startades om från samma sökväg och återfick
seriell kontakt. Användaren bekräftade att TIDER nu öppnas på den ritade
knappen uppe till höger. Plus/minus och SPARA/TILLBAKA fungerade; även
fyrvalsmenyn och INSTALLNINGAR fungerade från Bongo och Spelare. Fokusets
nedräkning och förloppsbåge började fungera i ett 5/1-prov. Någon release
skapades inte. Mediegester efter touchfixen väntar på ett prov med aktiv
media på datorn. Under 5/1-provet fortsatte Fokus på Bongo. Användaren
bekräftade automatisk växling till FOKUS, FOKUS KLART och LED vid fokusslut,
och PAUS KLAR, kort LED-signal och väntan på START vid pausslut. Exakta tider
och antal pulser mättes inte. LED AV, NVS-sparning av de nya UI-valen, lång
textrullning och fortsatt deep sleep behöver riktade fysiska prov.

Efter 5/1-provet rapporterade användaren ett litet, inaktivt `START`-märke
överst på Bongo och Spelare som skymde innehåll efter pausslut. Källan visar nu
`PAUS KLAR` i sex sekunder och döljer sedan märket; den kompakta
`PAUS`-påminnelsen under en pågående paus finns kvar. Rättningen byggdes för
`esp32-024r-spotify` (RAM 34,0 %, flash 46,8 %) med appbinär SHA-256
`F0F7EC82E28AB30607EC59A8409B4B4876578D869403753C09DD33F3747FCFEF`.
Kompilerat synlighetstest, 23 companion-tester och 32 simulerade vyer
passerade. Efter uttryckligt godkännande för just denna hash flashades appen
på COM6 vid `0x10000` den 2026-10-02; esptool verifierade datan. Installerad
diagnostik-companion återstartades och loggade seriell kontakt samt
återsynkning. Efter en ny hel 5/1-cykel bekräftade användaren att det lilla
START-märket var borta från Bongo/Spelare efter pausslut; exakt
sexsekundersgräns mättes inte. Normalt UI, meny och panelbyte fungerade och
ingen ljusblixt sågs vid omstart. Den då nedladdningsbara `app-v1.1`-releasen
ändrades inte; rättningen ingår nu i `app-v1.2`.

Fortsatt fysiskt prov: öppna menyn från
Bongo och Spelare, välj INSTALLNINGAR och växla tema samt återgå till rätt
panel. Kontrollera tryckfeedback och att svep ut ur en knapp inte aktiverar
den. Ställ TIDER på 5/1, starta Fokus och kontrollera att bågen följer
nedräkningen, även över panelbyte och ändring av framtida tidsval. Prova
automatisk Fokus-visning och LED av/på vid fasslut, omstart för NVS-sparning
och ett companion-bortfall för mörk deep sleep och väckning. På Spelaren:
kontrollera verkligt omslag, vinylrotation, DJ, paus, lång rullande titel,
tidsrad, temaaccent, kompakt Fokusmärke samt enkel-/dubbel-/trippeltap och svep.

## Tidigare lokal flash: Fokus v1

Den tidigare flashade Fokus v1-versionen har en tredje panel, **FOKUS**, med en fast lokal
25:00-nedräkning. Långtryck öppnar samma panelmeny från Bongo, Spelare och Fokus.
Menyn visar tre stora val med aktiv markering och stängs efter sex sekunder.
Fokus har breda knappar för **START/PAUS** och **NOLLA**. NOLLA ger pausad 25:00;
efter 00:00 står **KLART** kvar tills NOLLA trycks eller **STARTA OM** börjar
en ny 25-minutersomgång. Timern fortsätter när en annan panel visas. Vid avslut
visade den då flashade appkoden en tydlig grön toppremsa i tio sekunder
på valfri panel. Därefter ligger ett litet `KLART`-märke mitt i den fria ytan
mellan de övre statusfälten på Bongo/Spelare tills Fokus öppnas eller ett nytt
pass startas. Kortets gröna RGB-LED blinkar tre gånger kort vid avslut. Signalen
är lokal och använder varken nytt serialkommando, ljud eller bakbelysningsblink.

Fokus v1 finns **inte** i den nedladdningsbara `app-v1.1`-firmwaren ovan. Den
första Fokus-appbinären (SHA-256 `8441A215ED765C594918FAC6C037A41EBF8FC6146740BE56D1269AF87E85CE0F`)
flashades separat vid `0x10000` på COM6 den 2026-09-30. Därefter flashades
den reviderade v1-signalen (SHA-256
`0E77C418E6762D882356D738B6C9F0625737ED6107BD1CB8F476BADB52713E66`)
på samma adress efter särskilt godkännande; esptool rapporterade
`Hash of data verified`. Användaren såg normalt Bongo-gränssnitt och senare
en kort grön LED-blinkning vid fokusslut som hen är nöjd med. Exakt
pulssekvens och skärmavisering är ännu inte fullständigt dokumenterade fysiskt.
Fokus v1 kräver ingen ny Windows companion eller serialtrafik.
Om companion försvinner gäller fortfarande den separata
10-minutersgränsen för deep sleep; en ESP32-omstart återställer Fokus till 25:00.
Kompileringstester täcker timergränser, paus/återupptagning, `millis()`-wrap,
tre menyval, Fokus-touchrouting samt LED-pulsernas gränser och avbrott.
De nuvarande [simulerade vyerna](visuals/contact_sheet_composed.png) visar v2
och kan inte användas som foton av den flashade v1-skärmen.

Vid ett första fysiskt prov såg användaren normalt Bongo-UI med aktuell tid och
statistik, Fokus med stora 25:00-siffror, fungerande START, PAUS och NOLLA vid
kort tryck samt trevalsmenyn via långtryck med växling mellan Bongo, Spelare
och Fokus. Timern fortsatte över panelbyte; Fokus visade mindre återstående tid
vid återkomst. Bongo-bonk, Spelarens enkel-/dubbel-/trippeltryck och svep,
DJ-läge och albumomslag fungerade också enligt användaren. Efter omkring 25
minuter visade Fokus `00:00` och `KLART`. Den tidigare Fokus-binärens lilla
2,5-sekundersremsa märktes inte som en tydlig slutsignal. Den reviderade v1-LED:n
blinkade enligt användaren, men Fokus efter deep sleep återstår att prova.

### Tidigare fysisk testplan för Fokus v1

Punkterna nedan gäller den äldre v1-binären; aktuell lokal firmware är v2.

1. Öppna panelmenyn med långtryck på Bongo, Spelare och Fokus. Välj alla tre
   paneler, kontrollera aktiv markering, timeout och att samma val stänger menyn.
2. Prova kort tryck, svep och långtryck på START/PAUS och NOLLA. Bara kort tryck
   inom samma knapp ska ändra timern; ingen Fokus-touch får ge bonk eller
   mediakommando.
3. Kör ett helt pass med den reviderade v1-binären på
   Bongo/Spelare och kontrollera stor toppsignal, tre gröna LED-pulser och
   ett kvarstående litet `KLART`-märke utan att tid/statistik eller mediastatus
   skyms. Öppna Fokus och kontrollera att påminnelsen kvitteras; prova NOLLA,
   STARTA OM och att inga gamla LED-pulser fortsätter.
4. Kontrollera Bongo-bonk, mediasidans enkel-/dubbel-/trippeltryck och svep,
   DJ-animation och albumomslag. Prova därefter companion-bortfall och väckning:
   deep sleep ska ha företräde och Fokus ska börja om på 25:00 efter reset.
   Observera att den gröna LED:n är släckt under mörka timerväckningar och att
   reset inte ger oavsiktliga LED-pulser eller bakbelysningsblixtar.

## Tidigare lokal Fokus v2-flashning (nu vidareutvecklad i app-v1.2)

Den då lokalt flashade v2-källkoden låter användaren välja **fokustid** och **paustid** separat på
ESP32. Den centrerade knappen **TIDER** på Fokus öppnar en vy med fyra breda,
vertikalt staplade minus/plus-knappar och **SPARA / TILLBAKA**. Standard är
25 minuter fokus och 5 minuter paus. Fokus kan väljas mellan 5 och 120 minuter
i steg om 5; paus mellan 1 och 30 minuter i steg om 1. Valen lagras tillsammans
i ESP32:s Preferences/NVS när de ändras och sparas. Ogiltiga lagrade värden
ersätts var för sig med standardvärden vid start. Ett osparat utkast kasseras
om panelmenyn används för att lämna TIDER-vyn; menyvalet FOKUS återgår till
huvudtimern. Fyra vertikala knappar och en centrerad TIDER-knapp minskar
beroendet av touchens ännu oprövade horisontella riktning.

START kör fokus. Vid fokusslut startar vald paus automatiskt. Både fokus och
paus kan pausas och återupptas och fortsätter när en annan panel visas. När
pausen tar slut stannar timern på `00:00` med **PAUS KLAR** tills START trycks
för nästa fokuspass. **NOLLA** förbereder vald fokustid utan att starta den och
avbryter signaler. Sparas en ny fokustid efter NOLLA visas den nya hela tiden
direkt och används vid nästa START. En nedräkning som redan har startats,
även om den sedan pausats, behåller sin återstående tid. Ny paustid gäller när
nästa paus börjar och ny fokustid för ett redan startat pass gäller vid nästa
fokuspass. TIDER-vyn anger därför att en startad timer behålls. Vid reset eller
deep sleep återgår timern till vald fokustid, men sparade val finns kvar.

Vid fokusslut visas en central grön **FOKUS KLART**-avisering med betydligt
större text och raden **PAUSEN HAR STARTAT** i tio sekunder även på Bongo och
Spelare. Tre korta gröna LED-pulser används som i v1. Pausslut ger en stillsam
sexsekunders **PAUS KLAR**-remsa och en kort LED-puls. Små `PAUS`/`START`-märken
kan ligga kvar på Bongo/Spelare utan att täcka statistik eller mediakälla.
Menyn visas över aviseringen. Ingen Windows-ändring eller ny serialtrafik ingår.
[Simulerade 240×320-vyer](visuals/contact_sheet_composed.png) visar v2-layouten;
de bekräftar inte verklig skärm eller touch.

Firmware v2 byggdes då för `esp32-024r-spotify` med RAM 34,0 % och flash 47,1 %.
Den då lokala appbinären hade SHA-256
`3EA958DA3E7C03A50C04F92B4B3C9484DEE5C5F2AD434877E0639C382B133E6D`.
Efter uttryckligt godkännande flashades just denna appbinär via COM6 vid
`0x10000` den 2026-10-01; esptool rapporterade `Hash of data verified`.
Ingen fullbild vid `0x0` flashades då. Vidareutvecklad Fokus v2 ingår nu i
`app-v1.2`; den nya fullbilden provades senare vid `0x0` den 2026-10-03.
Kompilerade gränstester för tidsval, NVS-packning, cykeln, signaler och touch
samt companionens 14 regressionstester passerade.

Användaren har på v2-skärmen bekräftat TIDER-vyns separata fokus- och
pausknappar och sparat 5/1 minuter. Efter ett 5+1-pass svarade hen ”Japp det
ser ut som det” om stor **FOKUS KLART**-ruta, automatiskt startad enminutspaus
och **PAUS KLAR** som väntar på START. Det är en kvalitativ bekräftelse utan
exakt tidtagning eller uppmätt LED-sekvens. Före en fysisk RESET/EN med BOOT
släppt visade Fokus-raden och TIDER 5/1. Efter reset återkom UI, Fokus stod på
**05:00** och väntade på START, och TIDER visade fortfarande 5/1. Därmed är
sparning över fysisk reset provad på enheten. Bongo-meny
och panelbyte, Spelarens touch/DJ och aktuellt albumomslag fungerade efter
reset.

I ett senare bortfallsprov stoppades den installerade companionen kl. 20:36
svensk tid med 5/1 sparat. Skärmen rapporterades slockna omkring 20:47, cirka
elva minuter senare, utan synlig ljusblixt. Samma installerade EXE startades
igen utanför sandboxen kl. 20:47:40 med två normala processer. Användaren såg
skärmen vakna och bekräftade Fokus **05:00** väntande på START, TIDER **5/1**,
aktuell tid/statistik och albumomslag. Ingen ljusblixt sågs under den
observerade mörka perioden eller precis innan normal bild återkom. Exakt
väcktid från första statistikpaketet och faktisk deep sleep-ström har inte
mätts; observationen garanterar inte varje timerväckning.

Skärmen var först mörk efter flashningen när start av den installerade
companionen inifrån sandboxen bara gav en liten launcher. ESP32:s bootlogg
visade normal flashstart, och två manuella giltiga STATS-paket tände skärmen.
Normal start av samma installerade EXE utanför sandboxen gav två processer och
återställde UI. Den installerade filen och autostarten ändrades inte. Det
startproblemet ska inte förväxlas med ett firmwarefel.

### Kvarvarande fysisk kontroll av Fokus v2

1. Upprepa vid behov det observerade 5/1-bortfallsprovet med exakt tidtagning
   från sista/första giltiga statistikpaket till släckning/väckning. Mät
   strömförbrukning för elektrisk bekräftelse av deep sleep och observera flera
   mörka timerväckningar för eventuella ljusblixtar.
2. Mät fokusslut och pausslut med klocka samt observera central ruta,
   påminnelse på Bongo/Spelare och exakt antal gröna LED-pulser. Det tidigare
   5+1-provet bekräftade beteendet kvalitativt men inte tider eller varje puls.
3. Prova övre och nedre träffytor i TIDER, gränserna 5/120 och 1/30,
   NOLLA följt av nytt sparat val samt ändring medan ett startat pass är pausat.
   Kontrollera att Fokus-touch inte ger bonk eller mediakommandon. Bekräfta
   efter deep sleep att Bongo-/Spelar-gester, DJ och omslag fortfarande fungerar.

## Skärmsläckning och deep sleep

Källkoden från 2026-09-29 innehåller en ny, separat 10-minutersgräns för
companionens närvaro. En aktiv companion skickar redan statistik ungefär varannan
sekund. Om giltig statistik uteblir i tio minuter släcker ESP32 bakbelysningen
på GPIO 27, sätter ILI9341 i vila och går i deep sleep. ESP32 gör sedan en
mörk kontrollvakning var 25:e sekund och tänder skärmen först efter två nya,
giltiga statistikpaket. Companion återansluter vid serialfel och skickar om tid,
statistik, mediedata och cachat omslag efter skärmens omstart. Kattens befintliga
`SLEEP_TIMEOUT` är oförändrad.

Funktionen finns i det nya versionsmärkta firmware- och companion-paketet ovan.
Båda delarna behövs; den äldre panelmenyreleasen från 2026-09-24 saknar
skärmsläckning och återanslutning. Appbinären har flashats på `0x10000` och ett
kort prov med källkörd companion visade normalt UI, meny, panelbyte och
albumomslag. I ett bortfallsprov höll aktiv companion skärmen tänd
cirka 1,5 timme; efter att källprocessen stoppades sågs panelen senare släckt.
Vid återstart loggades första giltiga statistikpaketet kl. 15:47:40.588 den
2026-09-29 och normalt UI rapporterades senast 15:48:23. Det ger högst cirka
43 sekunder till användarsvaret, men ingen exakt visuell tidtagning gjordes.
Tid, statistik, samma låts omslag och meny/panelbyte fungerade efter väckning.
Användaren såg ingen ljusblixt under mörk period eller vid väckning. Vid ett
separat Windows sleep/resume-prov var skärmen släckt före väckning och normalt
UI återkom inom ungefär en minut enligt användaren, utan exakt tidtagning.
Ett senare shutdown/power-on-prov rapporterades också fungera, men utan
detaljerad logg eller exakt tidtagning. Faktisk deep sleep-ström är inte mätt.

En separat lokal companion-kandidat byggdes från `companion/BongoDeskSpotify.spec`.
Vid isolerad körning på COM6 bekräftade användaren UI, statistik, samma omslag,
meny och panelbyte; tray Exit stängde appen. Efter användarens godkännande
installerades samma kandidat lokalt 2026-09-30 som
`%LOCALAPPDATA%\BongoDesk\BongoDeskSpotify.exe` med SHA-256
`65D3DAEAFAA4E1CE87A5F9FE52F66923B832E46D8DFBC56917F60EBD6A25128C`.
Den tidigare installerade filen finns som
`BongoDeskSpotify.backup-20260930-185311-3c46b403.exe` i samma mapp.
Autostarten pekar på den nya installerade filen. Användaren bekräftade normalt
UI med aktuell tid/statistik och albumomslag samt fungerande långtrycksmeny och
panelbyte även med den installerade versionen.
Den nya versionsmärkta EXE:n i `release/` är byteidentisk med denna installerade
och provade kandidat.

### Föregående release från 2026-09-24

Den äldre [fullständiga panelmenybilden](release/BongoDesk-panel-menu-hit-2026-09-24-full-0x0.bin)
har SHA-256 `9472424046566406A486509294CAF2995DEA9FA2A73E3AF0C3FBBFCD1961FDCC`.
Dess [Windows companion](release/BongoDeskSpotify-panel-menu-2026-09-24.exe)
har SHA-256 `3257ABB16B11A4E569AC22CEF59B2E3BAD00F073FC7138EC2118378C56F43459`.
Filerna finns kvar för den tidigare panelmenyversionen; den releasen innehåller
inte den nya strömstyrningen eller `SYNC_REQUEST`.

### Fysisk kontroll när skärmen är ansluten

1. Kör den nya companion och firmwaren tillsammans. Låt datorn vara oanvänd
   minst elva minuter och kontrollera att skärmen fortsätter visa Bongo.
2. Stäng av datorn med USB-strömmen kvar. Mät tiden från sista statistikpaketet:
   efter omkring tio minuter ska bakbelysning och LCD vara släckta och ESP32
   ha gått i deep sleep. Observera särskilt om de korta timerväckningarna ger
   någon ljusblixt; en sådan måste rapporteras som ett kvarvarande hårdvarufel.
3. Starta datorn och den nya installerade companion. Mät från att companion
   börjar skicka data tills skärmen visar UI. Målet är högst 60
   sekunder. Kontrollera tid, CPU/RAM/WPM,
   låttitel, progress och samma låts albumomslag utan låtbyte.
4. Upprepa med Windows sleep/resume. Kontrollera därefter Bongo-bonk,
   långtrycksmenyn, medietap, dubbel-/trippeltryck, sidsvep och svep ned till DJ.

## Flasha från Windows

1. Ladda ned den aktuella `.bin`-filen och `.sha256`-filen till samma mapp.
   Installera Python och esptool om de saknas: `py -m pip install esptool`.
2. Stäng Bongo Cat companion via **Exit** i systemfältet och stäng eventuell
   serialmonitor, så att porten är ledig. Hitta enhetens COM-port i
   Enhetshanteraren; ersätt `COM6` nedan med dess faktiska port.
3. Öppna PowerShell i nedladdningsmappen och kontrollera filen:

   ```powershell
   Get-FileHash .\BongoDesk-app-v1.2-2026-10-03-full-0x0.bin -Algorithm SHA256
   ```

   Hashen ska vara `B25028C1995AEFA81C99123133FA0A24898D2DA264DBBF2CDA9A2DBA3345B095`.
4. Flasha **hela bilden från `0x0`**:

   ```powershell
   py -m esptool --chip esp32 --port COM6 --baud 460800 write-flash 0x0 .\BongoDesk-app-v1.2-2026-10-03-full-0x0.bin
   ```

   Om anslutningen fastnar vid `Connecting`, håll **BOOT** nedtryckt och tryck
   kort på **RESET/EN** vid behov. Släpp BOOT när chippet har identifierats och
   skrivningen börjat. Vänta på verktygets skrivverifiering och omstart.
5. Starta Windows companion igen. Den behövs för mediainformation,
   Spotify-data, albumomslag och systemvärden; firmwaren hämtar inte dessa
   uppgifter själv. Se [companion/README.md](companion/README.md) för
   nedladdning, Spotify-koppling och körning från aktuell källkod.

En fullständig flashning skriver även över området för enhetens NVS-data i
bildens adressintervall. Kontrollera COM-porten och filens hash före körning.

## Bygg från källkod

```powershell
pio run -e esp32-024r-spotify
```

Detta bygger appfilen `.pio/build/esp32-024r-spotify/firmware.bin`, som hör
hemma vid `0x10000`. Den är inte samma fil som den sammanslagna
`release/*-full-0x0.bin`, som flashas vid `0x0`. Bygginställningarna finns i
`platformio.ini`. Visuella, simulerade förhandsbilder finns i `visuals/`.

Personliga inställningar och Spotify-token ligger i `%APPDATA%\BongoCat`,
utanför projektet, och ska inte läggas till i Git.

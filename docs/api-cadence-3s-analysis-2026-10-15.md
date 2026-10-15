# 3 s eller 5 s för aktiv API-uppspelning – isolerad analys 2026-10-15

## Rekommendation

**Behåll 5 s som generell takt.** 3 s stöds redan av konfigurationen, men
ger sämre marginal för lång uppspelning. I den lätta blandtracen förbättras
dagens p95 för upptäckt av låtbyte med cirka 1,8 s, till priset av 44–48 %
fler anrop. I den kontinuerliga tracen kommer budgettrycket tidigare och
p95 blir sämre med 3 s, både med aktuell återhämtning och full historik.

Detta är analys med syntetiska svar och virtuell klocka, inte ett prov av
Spotifys verkliga gränser. Inga produktionsfiler, standardvärden, verkliga
profilfiler, installerade program eller firmware ändras. Ingen ny policy,
release, installation eller flashning ingår. Separata korta aktivitetslägen
har inte modellerats eller införts i detta uppdrag.

## Underlag och avgränsning

- Exakt klient och budgetkod från fryst **17466**, via dess sparade källor:
  `build/active-api-recovery-2026-10-15/source-frozen/companion/`.
- Befintlig EXE: SHA-256
  `17466EBFC95B14FDFB93D717BB9700F5937087AC27933CCDF82DF98E8C77C1C0`.
- `api_budget.py`: SHA-256
  `ACD23D364B8A5393E43C52F1EE9B1E6F84410C5CD9422256F33384F5F2BD977F`.
- `spotify_api.py`: SHA-256
  `E17615BA8181D3CC77BF46680B57125F74C98A901D1CA67316464495B4322353`.
- Enda jämförda instansinställning:
  `api_budget_day_playing_seconds=5` respektive `3`. Standardvärdet i källan
  är fortsatt **5**. `settings()` accepterar redan **0,5–300 s**.
- Klientens verkliga GET-/admission-/väntelogik körs med `MemoryBudgetStore`.
  Alla HTTP-anrop ersätts med syntetiska GET-svar på 120 ms. Det är inget nytt
  prov av filsystemslås, fsync, Windows-worker eller Spotify-tjänsten.
- Befintliga natt-/idle-profiler, korta och långa total-/autotak,
  tryckmultiplikatorer, utjämning av återstående budget, grants och
  sparade återhämtningsregler används utan kodändring. Inga nya manuella
  anrop, fallback-läsningar, tokenförnyelser eller aktivitetsburstar tillförs.
- Två redan använda traceformer, samma slumpfrö **421**, låtbyte var
  **151–229 s** under uppspelning, vardera **72 h** och åtta körningar totalt.
  Starten uppdateras till det senaste verifierade headroom-underlaget.

### Start och historikfall

Start: **2026-10-15 17:52:04 Europe/Stockholm**, efter Projektledarens senaste
stickprov. Ledger **299 totalt / 276 auto**, alltså 23 tidigare explicita
kostnader. Senaste autoanrop läggs 0,36 s före start. Alla andra 298 kostnader
läggs i föregående minut: detta är ett uttryckligt syntetiskt antagande,
eftersom verklig fördelning mellan minutbucketar inte ingår i underlaget.
Det är inte en exakt återspelning av användarens ledger.

| Fall | Sparat tillstånd och gränser |
| --- | --- |
| Återhämtning | Warm till **16 oktober 11:39:30**, strong till **15 oktober 15:32:48** (redan utgången), soft till **17 oktober 15:32:48**. Inledningsvis totalt/auto **4000/3600**, sedan **6000/5400**, till sist **8000/7200** |
| Full historik | Hypotetiskt komplett historikdygn utan warm/QUOTA, men samma **299/276** startkostnader; **8000/7200** hela tiden. Ingen verklig historik nollställs |

Initialt återstår därmed **3701 totalt / 3324 auto** under återhämtning,
respektive **7701 / 6924** med full historik. Korta tak är **24 totalt / 18
auto per 30 s** i båda fallen.

### Traceformer

| Trace | Lokal dygnsrytm |
| --- | --- |
| Blandad | API spelar **06–08 och 12–14**: 2 nattimmar + 2 dagtimmar. API idle **02–06**: 4 h. Windows-källa övriga **16 h**, utan API-pollning |
| Kontinuerlig | API spelar hela **72 h**, med ordinarie nattprofil **00–08** |

Blandtracen startar i en **antagen Windows-period**, trots att det verkliga
17:52-stickprovet hade API som källa. Den visar ett användningsscenario,
inte vad användaren faktiskt gjorde. Båda takterna får samma antagande.

## Anrop och budgettryck

Alla **nya** anrop i modellen är automatiska; nya total- och autotal är därför
lika. De 23 tidigare explicita kostnaderna ingår däremot i ledgerns total.
24 h-blocken räknas från start 17:52:04, inte från midnatt. Ledgermax är
budgetens konservativa rullande 24 h, inklusive startkostnaderna; ett
separat faktiskt rullande 24 h-max av nya HTTP-starter visas också.

| Historik / trace | Takt | Nya HTTP, 72 h | Nya total=auto, block 1 / 2 / 3 | Ledgermax totalt / auto | Max nya HTTP/24 h | Tryck ≥50 %, h |
| --- | --- | ---: | --- | --- | ---: | ---: |
| Återhämtning / blandad | 5 s | 5658 | 1886 / 1886 / 1886 | 2185 / 2162 | 1887 | 0 |
| Återhämtning / blandad | 3 s | 8155 | 2669 / 2699 / 2787 | 2968 / 2945 | 2788 | 4,5515 |
| Återhämtning / kontinuerlig | 5 s | 16183 | 5028 / 5404 / 5751 | 5795 / 5795 | 5791 | 69,8326 |
| Återhämtning / kontinuerlig | 3 s | 17965 | 5070 / 6054 / 6841 | 7127 / 7127 | 7127 | 70,6793 |
| Full / blandad | 5 s | 5658 | 1886 / 1886 / 1886 | 2185 / 2162 | 1887 | 0 |
| Full / blandad | 3 s | 8361 | 2787 / 2787 / 2787 | 3086 / 3063 | 2788 | 0 |
| Full / kontinuerlig | 5 s | 18792 | 6852 / 6180 / 5760 | 7150 / 7127 | 6852 | 67,2726 |
| Full / kontinuerlig | 3 s | 21103 | 6852 / 7126 / 7125 | 7150 / 7127 | 7127 | 69,1193 |

Alla åtta fall höll aktuella korta/långa total- och autogränser vid varje
observerad admission. Inga fulla budgetstopp, reservationer eller fast-lägen
uppstod. Största korta användning blev **6 med 5 s**, **10 med 3 s**.
Minsta återstående autoutrymme var **55** i kontinuerlig återhämtning och
**73** vid kontinuerlig full historik. Skyddet bromsar alltså innan det tar
slut; detta är inte ett löfte om fortsatt kort pollintervall.

### Lokala kalenderdagar, nya total=auto

För kontinuerliga fall är första och sista kalenderdagen partiella:

| Historik / takt | 15 oktober från 17:52 | 16 oktober | 17 oktober | 18 oktober till 17:52 |
| --- | ---: | ---: | ---: | ---: |
| Återhämtning / 5 s | 2662 | 4590 | 5759 | 3172 |
| Återhämtning / 3 s | 2713 | 5345 | 5913 | 3994 |
| Full / 5 s | 3987 | 5207 | 5751 | 3847 |
| Full / 3 s | 5519 | 5551 | 5745 | 4288 |

Blandtracens första kalenderdag har inga nya API-anrop. 16/17/18 oktober
har respektive **1886/1886/1886** med 5 s i båda historikfallen,
**2669/2699/2787** med 3 s under återhämtning och **2787/2787/2787** med
3 s och full historik.

### När trycket börjar

Timmar nedan är sedan start. Aktiv dagtid betyder faktisk tid i spelande
API-läge under **08–24**; natt och idle räknas separat. Första trycket beror
här på autodelen: 50/80 % är **1800/2880** med halvbudget och **3600/5760**
med full budget. I blandfallet med 3 s nås 50 % efter att gränsen gått till
75 % av normal budget: **2700 auto av 5400**.

| Fall / takt | 50 %: väggtid / aktiv dagtid | 80 %: väggtid / aktiv dagtid | Natt / idle före respektive tröskel |
| --- | --- | --- | --- |
| Återhämtning, kontinuerlig 5 s | 2,1674 / 2,1674 h | 4,4534 / 4,4534 h | 0 / 0 h vid båda |
| Återhämtning, kontinuerlig 3 s | 1,3207 / 1,3207 h | 2,7067 / 2,7067 h | 0 / 0 h vid båda |
| Full, kontinuerlig 5 s | 4,7274 / 4,7274 h | 15,9556 / 7,9556 h | 0 / 0 h vid 50 %; **8 / 0 h** vid 80 % |
| Full, kontinuerlig 3 s | 2,8807 / 2,8807 h | 5,6527 / 5,6527 h | 0 / 0 h vid båda |
| Återhämtning, blandad 3 s | 19,8171 / 1,6848 h | Nås inte på 72 h | **2 / 4 h** vid 50 %; övrig tid Windows |
| Övriga blandfall | Nås inte på 72 h | Nås inte på 72 h | Schemalagd natt/idle kvar |

I kontinuerliga fall ligger trycket kvar från första 50 %-passagen till
72 h. Blandad återhämtning med 3 s har huvudperiod **19,8171–24,1322 h**
och flera korta återpassager **43,8647–44,1322 h**. Exakta delintervall finns
i resultatfilen. Trycktid inkluderar även perioder utan API-pollning när
Windows visas. Tillståndet observeras vid HTTP/väntetillfällen och minst vid
timgränser; tryckslut i en Windows-period har upp till en timmes upplösning.

## Upptäckt av låtbyte och största automatiska lucka

Upptäckt mäts från ett syntetiskt låtbyte till att den första senare
GET-läsningen är klar, inklusive dess **120 ms**. Det är metadataupptäckt,
utan seriell kö, teckning eller omslagsöverföring. p95 är det sorterade
95 %-indexet i modellens stickprov. Inga låtbyten behövde uteslutas för att
de korsade planerad Windows-/idle-period.

| Historik / trace / takt | Dag: median / p95 / max, s | Natt: median / p95 / max, s | Max HTTP-lucka dag / natt, s |
| --- | --- | --- | --- |
| Återhämtning / blandad / 5 s | 2,293 / 4,962 / 5,239 | 15,144 / 28,023 / 30,141 | 5,120 / 30,120 |
| Återhämtning / blandad / 3 s | 1,939 / 3,178 / 4,685 | 15,144 / 28,023 / 30,141 | 4,620 / 30,120 |
| Återhämtning / kontinuerlig / 5 s | 5,556 / 57,323 / 116,151 | 47,829 / 89,674 / 102,787 | 120,000 / 102,981 |
| Återhämtning / kontinuerlig / 3 s | 5,703 / 88,088 / 119,638 | 53,164 / 107,608 / 119,778 | 120,000 / 120,000 |
| Full / blandad / 5 s | 2,293 / 4,962 / 5,239 | 15,144 / 28,023 / 30,141 | 5,120 / 30,120 |
| Full / blandad / 3 s | 1,815 / 3,108 / 3,236 | 15,144 / 28,023 / 30,141 | 3,120 / 30,120 |
| Full / kontinuerlig / 5 s | 5,480 / 16,279 / 21,174 | 22,107 / 43,847 / 45,113 | 45,120 / 45,120 |
| Full / kontinuerlig / 3 s | 4,951 / 31,694 / 59,783 | 33,164 / 82,973 / 90,002 | 90,120 / 90,120 |

HTTP-luckor mäts mellan faktiska HTTP-starter under obruten uppspelning;
dag/natt för luckan bestäms av den senare starten. En lucka kan därmed
korsa 08-gränsen. Upptäcktslatensens dag/natt bestäms av själva låtbytet.

## Tolkning för användningen

Utan bromsning motsvarar 3/5 s nominellt **1200/720 anrop per aktiv timme**,
alltså +66,7 %. Med modellens svarstid blir obruten faktisk takt cirka
**1154/703** per timme. Natt, idle, Windows-källa och budgettryck gör att
hela tracens ökning blir mindre:

- Blandad användning: **+44,1 %** under återhämtning, **+47,8 %** med full
  historik. Dagens p95 förbättras **1,784/1,854 s**. Natten är oförändrad.
- Kontinuerligt: **+11,0/+12,3 %** över 72 h, eftersom budgeten bromsar.
  Dagens p95 försämras **57,323 → 88,088 s** under återhämtning och
  **16,279 → 31,694 s** med full historik. Tidigt snabbare läsningar använder
  utrymme som annars hade räckt senare.
- Med aktuellt startutrymme kommer 50 %-trycket efter cirka **1 h 19 min**
  aktiv daguppspelning med 3 s, mot **2 h 10 min** med 5 s; 80 %-tryck efter
  **2 h 42 min**, mot **4 h 27 min**. Detta inkluderar faktisk startkostnad,
  inte bara division med en nominell dygnskvot.
- De observerade omslagsöverföringarna på cirka **5,2 s** i
  [driftrapporten](api-budget-runtime-2026-10-15.md) förkortas inte av ett
  tätare metadataanrop. Modellen visar därför ingen total omslagslatens.

Lokala budgetar är produktens skydd. Spotify beskriver begränsning för hela
appen över rullande 30 s och separata kvotrestriktioner; ett godkänt lokalt
dygnstal garanterar därför ingen viss Spotify-kapacitet eller 429-frihet.
Se [Spotifys dokumentation om rate limits](https://developer.spotify.com/documentation/web-api/concepts/rate-limits),
läst 2026-10-15. Modellens friska GET-svar mäter inte den verkliga tjänstens
quota, övrig trafik med samma klient-ID, nätfel eller återförsök.

## Verifiering och spårbarhet

- **8/8** jämförelser färdiga med inbyggda kontroller av verklig admission,
  korta/långa total- och autotak, minsta 0,5 s startavstånd, noll reservationer,
  inget fast-läge och oförändrat standardvärde 5 s.
- Modell och maskinläsbara resultat:
  `build/api-cadence-3s-analysis-2026-10-15/compare_cadence.py` och
  `results.json`; fulla tryckintervall och kalenderdagstal finns där.
- Bevarandekontrollen verifierar **840/840** käll-/artefaktfiler oförändrade
  i storlek och SHA-256 efter analysen. Nuvarande **75/75** frysta källor
  matchar fortsatt manifestet. Äldre frysta kandidater, deras manifester
  och tidigare funktions-/policyrapporter ingår också; resultatet finns i
  `build/api-cadence-3s-analysis-2026-10-15/preservation-after.json`.
- Endast denna nya analysrapport och den separata löpande driftrapporten
  dokumenterar uppdraget. Frysta rapporter och releases bevaras.
- Ingen ny testsuite eller byggning behövdes för denna rena analys.
  Modellresultat ersätter inte ett fysiskt långtidsprov eller ett verkligt
  Spotify-prov. Den installerade versionen fortsätter med befintliga **5 s**.

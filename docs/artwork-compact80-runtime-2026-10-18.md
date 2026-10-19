# C2 installerad: endast uppstart observerad – 2026-10-18

**Installerat är companion 356A5EC0 / firmware C6EBAE4B vid 921600.
Ingen omslagsöverföring eller fartmätning finns i detta underlag.**
Rapporten avslutas med musikprovet uttryckligen väntande enligt Lead;
ett senare prov dokumenteras separat för det par som då faktiskt körs.
Tiderna nedan är svensk sommartid, UTC+02.

## Installation enligt fryst startsnapshot

Användaren gav exakt godkännande för C2-paret, BOOT med ”yes” och normal
reset med ”japp”. Lead installerade samma kanoniska appplats och behöll
faktisk baud 921600, konfiguration/auth, Run-post och genvägar byteidentiska
vid installationen. Inga nya profilval eller API-inställningar ingick.

Gamla 860896DB-firmwareappen lästes tillbaka: **936 384 byte**, 88,453 s,
korrekt hash. C6EBAE4B skrevs app-only vid `0x10000`: **936 704 byte**,
42,969 s, exit 0 och ”Hash of data verified”. NVS-området skrevs inte.
Binärernas SHA-256 enligt journalen är:

- Companion: `356A5EC0BC224EB92C7A9748E68F7445BAE9C01149C5E739B7B9C146063B1813`.
- Firmware: `C6EBAE4B13DE934449E2F32738D2CBFAEEC2693C5ECF8EE8A3A71FDB6254D275`.

## Observerad uppstart

Explorer-start gav APP_START **22:43:53.606**. Första anslutningsförsöket fick
UnicodeDecodeError 22:43:55.780; andra försöket anslöt 22:43:59.935. Orsaken
till det första felet är inte fastställd.

Status 22:44:19.734 visade ansluten ESP32, uptime 19 s och heap
154 356/min 153 472 av 261 112 byte. Vid 22:45:01.250 var kontakten fortsatt
ansluten, heap 154 356/min 153 444 och ESP-statusåldern cirka 2,244 s.
CPU-mätaren var av, API gav 204/idle med 15 s effektivt intervall och
Windows Spotify var false. Snapshoten bekräftar installerad apphash och
förväntad konfiguration.

Fram till denna sista observation finns **varken DEVICE_RESYNC,
ART_CAPABILITY eller ART_COMPACT_CAPABILITY**, och inga ART_READY/SENT/ACK
eller omslagsmätningar. Kontakt med ESP32 innebär alltså inte i sig att
kompaktformatet hade aktiverats. Ingen ny fysisk färg-, bild-, gest-,
animations-, sleep-/resume- eller fartacceptans påstås. UI:s tidigare
stillbildsgranskning och hostmodeller är fortsatt separat underlag.

## Provgräns och bevarande

Lead har bett användaren göra normal RESET med companion igång och därefter
starta musik. Svaret/fartprovet väntar. Den lästa uppstarten bevisar inte
varför engångshandskakningen saknas. Källan visar att den mörka proben
ignorerar CAPS-frågor; en avgränsad C3-app kan därför pröva en enda ny fråga
när aktuell ESP32-status visar normalt körläge. Det är ännu inte ett
hårdvaruverifierat orsakssamband eller en fartfix.

Enda runtimefilkälla: `%LOCALAPPDATA%/BongoDesk/deployment-artwork-compact80-20261018-222444-812590-startup-baseline.json`,
hash verifierad före läsning:
**C9CDC4628A5D19C929EB515C6342D08FEE241DEE94B04CA16AE29FEF5FD7BFF0**.
Inga privata backupreferenser följdes. C2:s [byggrapport](artwork-compact80-2026-10-18.md),
frysta källa/manifests, binärer och preview förblir oförändrade.

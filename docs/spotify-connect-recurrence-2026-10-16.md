# Spotify Connect – återkommande bakgrundsfel 2026-10-16

Tider: Europe/Stockholm. Cutoff: 16:29:37. Oförändrat par **3EDD2187/55669C87**.
Underlag: [innehållsfri journal](C:/Users/gusta/AppData/Local/BongoDesk/runtime-playback-background-recurrence-20261016-1625.json)
(SHA-256 `8AEC58D1E807014B37E85A3B453FAE9336995B64600F03C4CBDC30BE9A756E4F`)
och Leads användarbesked. Kompletterar [fryst incidentrapport](spotify-background-incident-2026-10-16.md)
(`0D56194C`): dess längre bakgrundsprov är **underkänt**.

## Återfall

Användaren: ”Waiting återkom medan musiken spelade” efter foreground→bakgrund
med Spotifybakgrundsuppdatering PÅ och återställt Wi-Fi. Cirka tio minuter
bakgrund; telefonhandlingarnas tider är inte mätta.

Läsning 16:26:33: fönstret 16:16:15–16:26:33 gav 71 A200/2 A204.
A (`playback_state`): senast 200 16:25:34.750; första 204 16:25:42.603;
nästa 204 16:26:12.889. Ingen ny B-probe; sessionsmöjligheten var redan förbrukad.

Samma processpar 14588/4004, frisk ESP32-kontakt, API ready/idle 30 s.
Inga nya 429, Retry-/klockspärrar, reserver eller configändringar. Budget inom gränser.

## Oberoende kontroll och avgränsning

Lead bad om datorSpotify på samma konto utan spelstart/enhetsbyte,
mobilSpotify kvar i bakgrunden. Användaren såg rätt låt först, men pausad;
datorappen följde inte mobilens nästa låt. Detta stärker rapporterings-/synkfel
i Spotify/Connect före Bongo; iPhone-app kontra tjänst är obevisat.

Datorstarten bevisar **ingen återhämtning**: 16:29:37 användes `windows_spotify`;
sista API-A204 16:27:43.778, Windowsmetadata från 16:28:05.311. Inaktuell
Windowsmetadata kan förklara låten på Bongo. Ingen Bongo-omstart/ändring;
frisk kontakt/oförändrade skydd.

Nästa begärda prov: avsluta datorSpotify, starta om iPhonen, starta musik,
återgå till bakgrunden när rätt låt syns. Resultat väntar; inget senare
besked ingår. Ingen permanent rättning fastställs.

Endast denna rapport tillkommer; tidigare filer bevaras.

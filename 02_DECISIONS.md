# Bongo Cat – Architecture Decisions

## 2026-10-05 – Physically test and install the Player timeline pair

- After explicit approval, read back the previous 923184-byte app at `0x10000` and verify SHA-256 `636AC267AEDCC4DF1B83693F5B4DCE41DE04C7EB37B8F3D2F3DDDF2740B85AB5` before writing. Flash only the new app with SHA-256 `ACA0E8ED6575D30B8F0010F5C79F1614CB02C6CCACDC691F225B3E38CF662297`; esptool verified the write. Keep NVS and the published full-image release untouched.
- Run the new companion EXE (SHA-256 `57E288E1D8120AA04E00D7EC235D9C28E7DC1021E2FC3AD7F48849683AF6A877`) temporarily before installation. The user observed monotonic playback time during artwork loading, the requested Player layout, correct last track and cover after quick changes, and working pause, seek, touch, DJ and Focus. Four art2 device-error ACKs occurred in two quick-change bursts; later transfers succeeded and the visible final cover was correct. Preserve this as an open reliability observation.
- Back up the prior installed EXE as `BongoDeskSpotify.backup-20261005-timeline-layout-0F5B8DE8.exe` and verify its SHA-256 `0F5B8DE8722D9ADB0CD0E92226488D59988916C6ADE7FF0A5AF0A86A7867956E`. Install the tested candidate at the unchanged path and verify its hash. Two normal processes, COM6, art2 capability and a successful art2 cover ACK returned; the user confirmed the display after installation. Keep runtime serial at 115200 for this commit. A later runtime transfer-speed experiment may use a paired baud change; the flashing-tool baud need not change. No new release, push or commit was part of the physical test itself.

## 2026-10-05 – Keep Player progress monotonic between fresh media samples

- The ESP32 already advances elapsed playback time locally. During a long artwork-v2 upload, the sender flushes the latest cached snapshot between chunks. The old three-second full sync resent its unchanged `MEDIA_TIME:0`, so a zero-position Spotify sample repeatedly reset the visible clock. A regression test simulated a transfer longer than three seconds and observed three zero-time packets before the fix. Keep periodic metadata and PLAYING/PAUSED recovery, but send `MEDIA_TIME` only when the sampled position or track changes, or after device resync clears the last sent value. A fresh backward seek and repeat still send their real lower position. This is source agnostic, so local Windows media uses the same rule; no additional API read or serial command is needed.
- A repeated, unchanged `MEDIA_STATE:PLAYING` must also leave the firmware's fractional progress anchor intact. Reanchor only on an actual playback-state transition; an authoritative `MEDIA_TIME` reanchors separately. The source-level regression tests cover Spotify API, local Windows media, backward seek, repeat, pause and new track; actual TFT timing remains a physical check.
- Reclaim the old gesture-help area for a 172×172 centered Player circle and a lower information card, with readable playback status at the bottom. Keep the 112×112 RGB cover and 64×64 DJ canvas and scale only their display zoom. Remove only visible gesture text; raw touch routing, DJ, source, marquee text and Focus reminder remain. The 32 simulated 240×320 views passed overlap checks and were inspected; hardware layout and touch still need confirmation. This candidate is built but not flashed or installed.

## 2026-10-05 – Install the diagnosed artwork-v2 companion

- After a temporary run proved `ART_CAPABILITY result=success protocol=art2` on the flashed ESP32, the user explicitly approved installing the exact diagnostic EXE with SHA-256 `0F5B8DE8722D9ADB0CD0E92226488D59988916C6ADE7FF0A5AF0A86A7867956E`. Back up the previous installed EXE first; `BongoDeskSpotify.backup-20261005-170029-106B2A4D.exe` matches its prior SHA-256 `106B2A4D58B51400DBCC98B3B2E706A9C1C563885B18336790E0D40AB29BA858`. The installed file matches the approved candidate. Two normal processes, successful COM6 connection, a new art2 capability event, unchanged HKCU Run entry and a fresh connected device status were observed. The device had no active Spotify playback during this check, so explicit `ART_SENT/ACK protocol=art2` and visible artwork with the installed EXE remain to be tested. No firmware, baud, release or Git publication changed with this installation.

## 2026-10-04 – Interleave artwork with current media metadata

- The legacy `MEDIA_ART_RGB` frame holds the outbound serial lock for all 37,632 raw bytes, so a new title can wait for the full upload despite the later pre-ACK metadata flush. Keep that byte-for-byte path for the installed firmware. A companion only selects artwork v2 after the device echoes a fresh 16-hex-character `CAPS?` challenge as `CAPS:MEDIA_ART2:<challenge>`; reconnect and `SYNC_REQUEST` clear the capability. An older device cannot accidentally receive v2 frames from a new companion.
- V2 uses bounded ASCII `BEGIN`, 128-byte base64 `CHUNK`, `END` and `ABORT` lines with transfer ID and sequential offsets. The ESP32 checks fixed dimensions/length, decodes each chunk into the inactive LVGL buffer, checks a final CRC-32, and switches the visible image only on a complete matching `END`. Wrong offsets, corrupt data, stalled chunks and an old track are discarded; `MEDIA_ART_DEFAULT` aborts staging before replacing the cover. ACK/ERROR includes the transfer ID so a late reply cannot complete a newer upload. The dark timer probe ignores v2 lines as proof of presence and returns on its normal deadline without waiting for an incomplete image.
- Release the serial lock after each complete line. The sender checks the latest track and flushes deferred metadata between chunks; touch commands use the existing independent inbound reader. A 202-byte maximum chunk line takes about 17.5 ms of 115200 8N1 wire time, and the retained 15 ms pause gives a nominal ~33 ms opportunity for a new metadata packet, plus scheduling, serial and LVGL work. For 294 chunks, base64 lines total at most 59,299 bytes: at least ~5.15 s wire time at 115200 or ~2.57 s at 230400, plus 4.41 s of pauses. `flush()` only drains the host side and does not prove that the ESP32 has processed its UART buffer, so shortening the pause needs hardware evidence. The protocol improves track-update latency, not necessarily total cover time.
- After separate approval on 2026-10-05, the standard 115200 firmware app with SHA-256 `636AC267AEDCC4DF1B83693F5B4DCE41DE04C7EB37B8F3D2F3DDDF2740B85AB5` was flashed at `0x10000`; esptool verified the written data. The installed companion retained normal Bongo UI, serial resync, Spotify touch and cover upload. A temporary run of the uninstalled v2 companion also reached COM6, received cover acknowledgements and showed the user's correct final title and cover after quick track changes. That first test EXE did not log the capability echo or protocol choice, so its image transfer cannot be distinguished from legacy or used to measure metadata latency. A second, still uninstalled diagnostic EXE logged `ART_CAPABILITY result=success protocol=art2` after `SERIAL_CONNECT`, proving a fresh physical nonce handshake. Spotify was idle during that run, so `ART_SENT/ACK protocol=art2` remains physically unobserved. The installed companion was restored with two processes and COM6 after both trials. Keep it while abort, dark wake, exact latency and UART reliability are checked separately. The 230400 profile remains unflashed.

## 2026-10-04 – Make Spotify Connect cadence and 429 history explicit

- Treat the configured fastest API interval as an adaptive lower bound, not a promised request rate. Keep local Windows Spotify authoritative. Give remote Connect playback a separate 10–120-second regular poll setting with conservative 15-second default; 10 seconds is about 8,640 regular reads per continuous day, 15 seconds about 5,760, before touch and natural-end checks. The display extrapolates progress locally. A single earlier read near a predicted natural track end replaces the next regular poll for that track, respects learned API spacing, and is disabled during quota recovery. Touch controls use the guarded urgent path and a prompt confirming read; queued actions wait out the guard instead of being lost.
- Show the selected bound, effective normal interval, and real 30-second/15-minute call counts separately. Count actual Spotify Web API HTTP 429 responses in a persistent monotonic total. Seed all still-present events from the old bounded list on upgrade, including entries older than 24 hours that were never trimmed by a newer 429; use a known last-limit timestamp as a minimum of one if the list is gone. Identify the baseline and incomplete earlier history. Cached cooldowns, restart and manual safety reset do not increase or clear the total. Include a privacy-limited total snapshot in status and diagnostic ZIP.
- Spotify documents a [rolling 30-second rate limit](https://developer.spotify.com/documentation/web-api/concepts/rate-limits) and a [separate development-mode quota](https://developer.spotify.com/documentation/web-api/concepts/quota-modes); neither supplies a fixed safe daily limit. Preserve `Retry-After`. On structured `QUOTA_EXCEEDED`, retain a 60-second automatic Connect floor and suppress adaptive speed-up until 24 hours after the retry deadline, including across restart and manual adaptive reset.
- Keep 115200 baud as the installed/default serial speed. A separate 230400 build and companion configuration option are only for a paired physical experiment. The 37,632-byte RGB cover takes at least ~3.27 seconds on a 115200 8N1 wire, plus ~4.4 seconds of existing interchunk pauses; 230400 can save at most ~1.63 seconds of wire time without further protocol changes. Flush deferred metadata immediately after the raw frame, before waiting for ACK, and log transfer and metadata delay without content. Physical testing must check UART integrity, ACK, touch, and deep-sleep resync before any baud change is deployed.

## 2026-10-03 – Prepare app-v1.2 as a versioned pair

- Keep `app-v1.1` and the 2026-09-24 release files intact. Package the current firmware source as a full raw ESP32 image at `0x0`: bootloader `0x1000`, partition table `0x8000`, `boot_app0` `0xe000`, app `0x10000`, with erased `0xff` gaps. Verify each segment byte for byte, image checksums and the app hash against the firmware app already flashed and physically tested at `0x10000`.
- Copy the exact installed and physically tested companion EXE into a new versioned release file. Verify it against the installed file and its development candidate. Use separate SHA-256 sidecars and brief release notes. Do not commit, tag or publish until Project Lead review.
- The full image is a verified file, not a physically tested `0x0` flash. A full flash overwrites NVS settings. Deep sleep current, precise wake/släck timings and API-only recovery after a real 429 remain unmeasured; describe the existing physical observations as qualitative.

## 2026-10-02 – Keep local Spotify authoritative during artwork uploads

- When a Windows Spotify session exists, use its metadata and controls without publishing a separate urgent Web API snapshot after touch. The API snapshot used a different track key and could briefly replace the local song and queue a second cover.
- Keep the latest media snapshot while the serial lock is occupied by an RGB cover. Send its metadata and default cover before starting the next cover, tag queued covers by track key, and discard a cover if the current track changed. Give the ESP32 a full reply interval after an otherwise successful cover upload; the old reply watchdog closed COM6 before the artwork ACK. This preserves the existing wire protocol and the API-only 15-second poll floor.
- Log only allowlisted touch action and WinRT result to distinguish missing serial touch input from rejected Windows controls. In a temporary source run, the user confirmed PLAY_PAUSE, NEXT and PREVIOUS affecting Spotify on the PC and correct title/artwork on the display; the log recorded incoming actions and successful Windows controls. After explicit approval, the rebuilt candidate `dist/companion-2026-10-02-local-media-dev/BongoDeskSpotify.exe` with SHA-256 `71756E01987D8A84C76DDCF83B76E9C512A7B5B2E09439DB94D10E36109ABF9F` was installed at the existing path. The prior installed EXE was backed up and verified as `BongoDeskSpotify.backup-20261002-170933-2F5CA652.exe`. Two processes, COM6, successful cover ACK and no subsequent `SERIAL_LOST` were observed. With the installed build, the user confirmed current title/artwork and PLAY_PAUSE/NEXT affecting Spotify and the display; PREVIOUS was not retested. All 34 companion tests and archive inspection passed. Firmware and release are unchanged.

## 2026-10-02 – Explain Spotify 429 and slow API-only polling

- The phone's Spotify playback is not a Windows media session. When the Web API has a persisted 429 cooldown, do not show stale track metadata or pretend that the Windows fallback can see the phone. Send a short waiting title and local retry date/time through the existing `MEDIA_*` fields; keep `MEDIA_STATE:NONE` and generic vinyl until fresh playback data arrives. Drop touch commands during the cooldown so they cannot execute hours later. Re-upload artwork if the same track returns.
- The diagnostic ZIP records a real 429 at 05:24 with 34,696 seconds of `Retry-After`, while later startup messages reuse that saved deadline. The user's Spotify dashboard shows `/v1/me/player` dominating at roughly 17–27 thousand calls per day. The original 429 body was not retained, so a development quota exhaustion is plausible but unproven; the later manual reset to 0.5 seconds did not cause the first 429. Keep Spotify's saved retry deadline. Add a 15-second floor for automatic API-only playback reads, reducing the maximum to about 5,760 per continuous day while ESP32 extrapolates progress locally. This does not guarantee that Spotify will not apply another quota.
- For the next real HTTP 429, whitelist only a structured reason such as `QUOTA_EXCEEDED`, request category, retry duration and aggregate counts. Label errors from a persisted deadline as `saved_cooldown`; never export tokens, raw response bodies, URLs, song text or cover bytes. PyInstaller candidate SHA-256 `2F5CA6524307985405751577C2E83FD47D366CFD3E79AA55B7A6978FF328B38E` passed 28 companion tests and archive inspection. After explicit approval for this hash, the previous installed EXE was backed up as `BongoDeskSpotify.backup-20261002-140605-876B3C15.exe` and the candidate installed at the unchanged path. Serial connection and two processes returned, and the saved cooldown was logged without a new HTTP request. The user confirmed the waiting status on Player and normal Bongo UI with time/statistics. Post-deadline track and artwork recovery remain pending. Firmware and versioned release are unchanged.

## 2026-10-02 – Remove the lingering START cue after a break

- A physical 5/1 run exposed a small START badge over Bongo and Player after break completion. It resembled a control, did not respond to touch and obscured content. Keep the six-second PAUS KLAR completion cue, then hide it on every panel. Keep the compact PAUS cue while a break is running.
- The source fix has a compile-time visibility boundary test and a build with SHA-256 `F0F7EC82E28AB30607EC59A8409B4B4876578D869403753C09DD33F3747FCFEF`. After separate approval for this exact hash, the app was flashed at `0x10000` on COM6 and esptool verified the write. The installed diagnostic companion restarted and logged serial contact and resync. After a complete new 5/1 cycle, the user confirmed that the small START badge was gone from Bongo and Player after the break. This was a qualitative check, not a timed six-second measurement. No release artifact changed.

## 2026-10-02 – UI app flash and horizontal raw-touch correction

- The approved UI app with SHA-256 `21E7FADA09689CD87F1194BE1A0DE453D0FAC28EE53A9165385368C40F699514` was written only at `0x10000` on COM6; esptool verified the data. The installed diagnostic companion was restarted from its unchanged path with `--startup`, and its two-process startup, serial reconnection and artwork acknowledgement were observed. The user saw normal Bongo UI with no reset flash and reported the menu, settings and Player largely working.
- Physical touch exposed a horizontal axis reversal that broad symmetric controls had hidden: the drawn upper-right TIDER did nothing, but an upper-left touch opened TIDER. Reverse only the X coordinate derived from raw touch Y in the common hit-test helper. Keep raw touch Y for vertical routing and the existing media-swipe deltas. Recheck that symmetric menu, settings and Focus controls remain reachable at both horizontal edges through compile-time assertions.
- The corrected app with SHA-256 `1177E1F583B9C560B593FF8E0EEE9AC5864A6D332A3D860C615D8C79BBBFCBA2` built and passed tests. After a second exact-hash approval, it was written at `0x10000` on COM6; esptool verified the data. The installed companion restarted and resynchronized. The user confirmed that TIDER now responds at its drawn upper-right position, its plus/minus and save controls work, and the broad menu/settings controls still respond. The versioned release and autostart path remain unchanged.
- In a qualitative 5/1 physical run, the user saw the arc advance, Focus continue while Bongo was shown, automatic return to Focus with FOKUS KLART and LED at the focus boundary, and PAUS KLAR with a short LED signal and waiting for START at the break boundary. Exact timing, LED pulse count, LED-off mode and persistence of the new UI settings still need measurement.

## 2026-10-01 – Player layout in the local firmware candidate

- Keep the 112×112 album-art transfer and the 64×64 DJ canvas, but display each inside a centered 148×148 circle with reduced LVGL zoom. Vinyl rotation and the clipping boundary remain local to the Player screen; no serial or companion behavior changes.
- Give the song and artist separate one-line scrolling labels, then a progress bar and elapsed/duration labels within a taller information panel. Place playback status and gesture help below it with distinct vertical space. Accent theme colors the Player brand, progress and status, while cover and DJ pixels keep their source colors. Leave a gap between the compact Focus reminder and the artwork circle.
- Put a full-screen opaque, non-clickable background behind the centered panel menu. It hides exposed controls at the screen edge while raw menu-button hit testing and six-second menu timeout remain unchanged.
- Source-driven 240×320 previews check circle/zoom fit, text spacing and the two-line gesture hint. Actual LVGL scrolling, touch and TFT rendering still require a physical check. This candidate has not been flashed or released.

## 2026-10-01 – Local Focus UI and panel settings candidate

- Keep Focus and its UI preferences on ESP32. Add INSTALLNINGAR as a fourth choice in the shared long-press menu; return to the previous panel on TILLBAKA. The default remains Bongo. No companion command or new recurring serial traffic is needed.
- Show a progress arc for the current focus or break phase. Record that phase's full duration when it starts and keep it while paused or when future duration choices change. Display elapsed progress from that denominator so changing TIDER cannot make a running arc jump. The next phase uses the newly selected duration.
- Store accent theme (green, cyan, amber), automatic Focus view at phase end (default off), and phase-end LED (default on) together under the independent `ui` key in the existing `bongofocus` NVS namespace. Validate a magic marker and reserved bits when loading; invalid data gets safe defaults. Save only after a changed setting. Theme styling affects controls and selected Player accents; sprites and album art retain their source colors.
- Keep every touch control at least 44 px high. Show pressed feedback from the raw touch path, cancel a button if the finger leaves it, and cancel a pending tap if an automatic panel change happens under the finger. Four menu choices and two TIDER cards fit the 240×320 display. The built-in LVGL fonts in this build lack Swedish Ä, so the on-device labels use ASCII `INSTALLNINGAR` and `PA`.
- Automatic phase-end navigation preserves the completion cue; manual navigation to Focus acknowledges it. It does not start the next focus phase or change the existing ten-minute companion deep-sleep rule. Build and static tests verify the candidate; new layout, touch, colors, LED option and menu return remain pending on the physical screen. No flash or release was authorized for this candidate.

## 2026-10-01 – Bounded companion diagnostics and same-track cover recovery

- Log only allowlisted event fields, sizes, retry counts and exception class names. Rotate four 256 KiB files in the user's local app data; export a ZIP only from the tray. Keep titles, artists, URLs, tokens, image payloads, settings and raw exception messages out of the log.
- Keep Windows media metadata authoritative while its Spotify session is active. If its thumbnail is absent or retries are exhausted, ask a linked Spotify API for artwork no more than once per 60 seconds, accept it only for the same title and artist, and retain the existing cover wire protocol.
- A conversion failure must not mark API artwork complete. After the configured 1–5 failed short attempts, allow another same-track attempt after 90 seconds. This permits recovery within a long song without continuous network or serial traffic.
- The diagnostic EXE is a separate development candidate and does not replace the versioned release. It was installed separately on 2026-10-01; the user saw normal UI and confirmed a new tray-exported ZIP. Future cover failures and recovery still need physical observation.

## 2026-10-01 – Local Focus v2 flash and physical checks

- The Focus v2 app binary with SHA-256
  `3EA958DA3E7C03A50C04F92B4B3C9484DEE5C5F2AD434877E0639C382B133E6D`
  was flashed locally on COM6 at `0x10000`; esptool verified the write. No
  full image at `0x0` or Focus v2 release was produced. The downloadable
  `app-v1.1` deep sleep release still contains no Focus version.
- The first dark screen after this flash was tied to starting the installed
  companion inside the sandbox: only a small launcher process ran. Two manual,
  valid STATS packets lit the screen, and a normal start of the same installed
  EXE outside the sandbox restored two processes and the UI. The existing
  autostart entry was unchanged; this was not evidence of a firmware boot fault.
- On the flashed v2 app, the user confirmed separate focus/break controls and
  saving 5/1 minutes. After one 5+1 pass, the user qualitatively confirmed the
  large FOKUS KLART cue, automatic one-minute break, and PAUS KLAR waiting for
  START; no exact durations were measured. The Focus footer and TIDER showed
  5/1 before a physical RESET/EN with BOOT released. Afterward the UI returned,
  Focus showed 05:00 waiting for START, and TIDER still showed 5/1. Bongo menu
  and panel change, Player touch/DJ, and current album art worked after reset.
  This confirms the saved duration across reset on this device.
- In a later companion-absence test with 5/1 still selected, the installed
  companion stopped at 20:36 local time. The user reported the screen dark at
  about 20:47 and saw no flash. The same installed EXE was started outside the
  sandbox at 20:47:40 with two processes; the user then reported that the screen
  woke and confirmed Focus 05:00 waiting for START, TIDER 5/1, current time and
  statistics, and album art. No flash was seen during the observed dark period
  or just before the normal image returned. The shutdown and wake observations
  are qualitative: exact visual wake latency and deep sleep current were not
  measured, and this does not prove every timer probe is flash-free. Exact cue
  timings and LED pulses also remain open.

## 2026-09-30 – Focus v2 durations and automatic break

- Keep Focus local to ESP32. Default focus/break is 25/5 minutes. The TIDER
  screen adjusts focus from 5 to 120 minutes in steps of 5 and break from 1 to
  30 minutes in steps of 1. Four wide vertically stacked plus/minus controls
  avoid depending on the unverified horizontal raw-touch direction. A centered
  TIDER entry and SPARA / TILLBAKA button use the same strict short-tap test;
  long press still opens the shared three-panel menu. Choosing FOKUS from that
  menu closes TIDER and returns to the timer, discarding unsaved draft values.
- Store both chosen durations in one packed `uint32_t` under a separate
  `bongofocus` NVS namespace. Validate each value on load and fall back to its
  default independently if corrupted. Write only when SPARA changes a value;
  a save failure leaves the settings view open. The active phase never writes
  NVS. A countdown that has started keeps its remainder when settings change,
  including when paused. Idle and NOLLA-prepared focus have separate states and
  take a newly saved full focus duration immediately, before START. The new
  break value is read at the next focus boundary. NOLLA prepares the chosen
  focus value without starting it.
- At the focus boundary, start the selected break automatically and emit one
  completion cue. The break can pause/resume and runs across panel switches.
  At its boundary, stop at PAUS KLAR until START begins the next focus pass.
  Reset/deep sleep discards the active phase but reloads saved durations.
  Unsigned `millis()` deltas handle wrap for both phases.
- Focus completion shows a central green `FOKUS KLART` message in 28 px type
  with `PAUSEN HAR STARTAT` below it for ten seconds on any panel. The existing
  three green LED pulses remain. Break completion shows a smaller six-second
  `PAUS KLAR` top banner and one short LED pulse. Small PAUS/START badges can
  persist on Bongo/Player without covering status; entering Focus or starting
  a new cycle dismisses them. The menu remains above cues. No companion,
  serial-protocol, backlight or release change belongs to v2.
- The revised v1 LED flash was observed by the user and considered satisfactory.
  That v1 observation is separate from the later v2 physical checks above.

## 2026-09-30 – Focus completion cue revision

- A physical 25-minute run reached `00:00` and `KLART`, but the former 2.5 s
  top strip was not noticed as a completion cue. Keep timer behavior and replace
  only the cue in the revised source build. This app build was subsequently
  flashed at `0x10000`; the revised cue still needs physical verification.
- Show a 46 px green banner for ten seconds on any panel. Afterward a small
  70 × 22 px `KLART` badge sits at the top center on Bongo/Player, between their
  existing left and right status labels, until Focus is opened or a new session
  begins. The badge and banner do not take touch input; the menu stays above
  the banner when open. Focus itself continues to show `KLART` at `00:00`.
- The [ESP32-2432S024R board definition](https://github.com/rzeldent/platformio-espressif32-sunton/blob/main/esp32-2432S024R.json)
  maps RGB green to GPIO16, and its [LED instructions](https://github.com/rzeldent/platformio-espressif32-sunton#controlling-the-rgb-led)
  document active-low drive. The project uses GPIO27 for the active-high TFT backlight; GPIO16 is
  otherwise unused here. Three 180 ms green pulses start 400 ms apart, driven
  by the existing loop without delay or serial traffic. Preload GPIO16 HIGH
  before enabling output at boot; set it HIGH before deep sleep and after
  completion is acknowledged, reset or restarted. Real LED polarity, brightness
  and reset behavior require a physical test.

## 2026-09-30 – Local Focus v1 panel

- Use a three-value panel state for Bongo, Player and Focus. The former
  `spotify_screen_active` boolean cannot distinguish Focus from Bongo.
  Startup still loads Bongo. The top-layer menu has three large, centered
  choices; secondary menu stats/media/bonk rows give way to readable targets.
- Focus is a fixed 25-minute ESP32 timer with idle, running, paused and
  completed states. Unsigned `millis()` differences account for wrap and are
  applied independently of which panel is visible. Labels change only when
  their displayed second or mode changes. Reset leaves a paused 25:00;
  Start after completion begins a fresh 25-minute session.
- Only short taps that start and finish inside the same broad, vertically
  stacked Focus button can change the timer. Long presses keep the shared
  menu behavior, and Focus touches cannot route to bonk or media commands.
  The vertical buttons avoid relying on the uncalibrated horizontal raw axis.
- The first flashed Focus version used one brief, non-clickable top strip.
  The revised source cue is described above. Neither version sends a serial
  packet or toggles the backlight. Companion absence still has priority:
  deep sleep resets the volatile Focus state to 25:00. No Windows companion
  or persistent setting changes are part of v1.
- The published `app-v1.1` binaries predate Focus. The source build, compile
  tests and simulated previews do not establish actual touch accuracy,
  display glyphs or 25-minute timing on the device; these need physical tests.

## 2026-09-30 – Versioned deep sleep release package

- Keep the 2026-09-24 panel menu release files intact. Prepare a new full `0x0`
  firmware image and a matching Windows companion under separate versioned
  names, each with its own SHA-256 sidecar.
- Use the app binary rebuilt from the current source only after its SHA-256
  matches the app already flashed and tested at `0x10000`. Include the matching
  bootloader, partition table, `boot_app0` and app at their established offsets;
  verify every segment in the resulting image. The full image has not itself
  been flashed from `0x0`.
- Package the previously tested companion candidate byte for byte. Its
  installed copy was confirmed on the physical display, while exact shutdown
  and resume timings and deep sleep current remain unmeasured. The user's
  shutdown/power-on report is a qualitative pass, not a timed measurement.

## 2026-09-29 – Companion presence and deep sleep

- The display power timeout is fixed at ten minutes since the last fully valid
  `STATS:CPU:...,RAM:...,WPM:...` line. It is independent of `SLEEP_TIMEOUT`,
  which continues to control the cat's idle animation. One partial line does
  not count. CPU may contain the decimal sent by the existing companion; it is
  range-checked before conversion to the display's integer value. A dark
  startup requires two valid statistics lines at least one second apart.
- The active-high backlight on RTC GPIO27 is driven low and held low across
  ESP32 deep sleep. An initialized ILI9341 receives Display OFF and Sleep IN
  before timer sleep. `tft.init()` runs only after the dark probe has proved
  current companion traffic; its automatic backlight write remains held off
  until the initial LVGL frame is drawn.
- A timer wakes the chip every 25 seconds for a normally eight-second, unlit
  serial probe. The probe waits up to four extra seconds after its first valid
  stats line or the end of an artwork transfer so the next stats line can arrive.
  A cover already in flight can extend that probe until complete.
  A failed probe returns to deep sleep. No UART wake capability is assumed.
  A stalled cover transfer times out after 15 seconds of no bytes so it cannot
  indefinitely defer power-down.
- The companion uses its existing statistics stream for presence. Its existing
  update thread retries failed or unresponsive serial handles; the one reader
  and one cover sender remain running. A single device-to-companion
  `SYNC_REQUEST` after ESP32 initialization restores time, statistics, media
  metadata/state/progress and a cached cover for the unchanged track. Existing
  media and album-art framing remain intact.
- GPIO hold and reset behavior, the lack of a visible wake flash, and the
  under-60-second target require measurement on the actual screen. The release
  binaries available on 2026-09-29 predated this source change.

## 2026-09-24 – Shared panel menu

- One `feature_overlay` lives on LVGL's top layer so long press can open or
  close it above either Bongo or media without changing the active screen.
- Two wide vertical choices select BONGO or SPELARE. The active choice is
  highlighted; choosing it just closes the menu. Other touches are consumed
  while the menu is visible, and its six-second timeout remains.
- Menu hit testing maps raw X to display Y and raw Y to display X using
  nominal 200–3900 endpoints, then requires both press and release inside the
  same LVGL button rectangle. Axis endpoints and horizontal direction remain
  a hardware calibration check. Media swipes keep their raw-delta handling.
- Opening the menu clears queued media taps, and queued taps wait while a
  finger is down so a long press cannot dispatch a delayed command. No serial
  command or companion change is introduced.
- Existing system stats, media status, title and bonk count remain secondary
  menu content and retain the current visibility settings.

## 2026-09-22 – Local DJ media-cat

- The media screen replaces the ASCII `DJ CAT` placeholder with a 64×64 LVGL
  canvas composed on the ESP32.
- Existing body, stock face and raised paws remain the base; the user-made
  mixer, glasses, notes and effect sprites are sparse overlay layers.
- DJ layers change locally about every 450 ms only while media is playing.
  The original two-frame behavior was later refined to independent note and
  effect choices; a paused track holds its most recent frame.
- Existing `MEDIA_STATE` is the only input. No Windows companion command,
  continuous state stream or album-art transfer behaviour is added or changed.
- The normal Bongo sprite manager stays separate, so DJ mode cannot alter
  typing, idle, blink, ear-twitch or touch-gesture behaviour.

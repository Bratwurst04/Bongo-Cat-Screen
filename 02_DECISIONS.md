# Bongo Cat – Architecture Decisions

## 2026-10-07 – Package app-v1.3 with matching runtime defaults

- The user requested a Git commit and a new release after approving the installed native UI. Prepare app-v1.3 from the exact physically tested `6A5366C1…` firmware app and frozen UI, without rebuilding firmware or changing the art2 protocol/pacing. Lead handles the companion installation check and external release publication.
- New companion profiles and engine fallback paths default to 230400, matching the fastserial release firmware. Existing explicit 115200 profiles are preserved without silent migration; upgrade instructions require changing only `connection.baudrate` when installing the new pair. Keep the named 115200 firmware environment available, select fastserial by default and use 115200 for flashing.
- Supply both an app-only image at `0x10000` and a full raw image at `0x0`, with separate SHA-256 sidecars. App-only preserves NVS with a compatible partition layout; the full image overwrites NVS. Verify startup segments, FF gaps, partition MD5/app size and image checksums. File/segment verification of the new full image is distinct from physical testing of the reused app.
- Rebuild companion separately for the changed defaults; verify embedded code/resources and isolated fresh/legacy profiles before Lead's installation test. Lead subsequently approved installation of `5609B99D…`, with unchanged config/Run entry, first-attempt serial connection and a natural 4859 ms art2 upload followed by a successful ACK 34 ms later. The release EXE is byte-identical to that candidate; no firmware flash or new visual walkthrough was required. Freeze the final EXE release copy only after that result. Preserve older release files and exclude personal config, credentials and backups. Keep qualitative sleep/wake and synthetic UI evidence distinct from exact timing/current, forced error recovery and real DPI/accessibility measurements.

## 2026-10-07 – Companion UI follows the display's visual identity

- The user explicitly requested a UI overhaul, superseding earlier restrictions on Windows settings. Keep the active native WinForms entry point launched by `tray.py`; the old Tkinter path is not the installed settings view. Split everyday status, editable settings and advanced diagnostics into Overview, Settings and Diagnostics using dark Player/Focus surfaces, green accent, the existing pixel cat and Swedish copy.
- Preserve the five numeric settings, Windows startup setting and the two diagnostic actions. Add dirty/save/undo feedback, per-field validation and save/discard/cancel on closing. Read the current config before writing only owned keys. Validate the initial API interval against its existing configured maximum so engine validation accepts saved values. Diagnostic actions are explicitly immediate; CPU changes await telemetry and learned-limit reset is confirmed without bypassing Retry-After.
- Read existing status only. Fresh serial contact is not proof of sleep/wake; stale host status and delayed device telemetry are labeled rather than represented as healthy. Local Windows Spotify remains the shown source during a Connect API cooldown. UI source changes preserve firmware, protocol, Spotify requests, engine, tokens and tray lifecycle. Native fixture previews and limitations are documented in `visuals/companion-ui/README.md`.
- A joint UI/Lead review keeps these three pages and the visual direction, while moving artwork retries and all three adaptive intervals behind a closed-by-default advanced section. Validation opens hidden invalid fields and preserves entered values. Overview uses plain source text and compact PC statistics; BongoDesk resources stay in Diagnostics. Save/Undo appears on Settings or when other pages have unsaved edits. Diagnostic action results remain visible beside their controls. Decimal display uses Swedish formatting without altering config values or number parsing.
- After the user approved the refined preview, Lead installed the frozen 19,299,592-byte EXE with verified SHA-256 `18465D92AA67E23F09FF0B3B1636D6CD7840A8B1B3B7C90D35D185B7A50D445E` at the usual per-user path, preserving verified EXE and config backups. Config, credentials and the Windows Run entry were unchanged at installation. Startup, serial connection and art2 handshaking succeeded. Firmware remains `6A5366C1…`; no engine source change or flash was part of the UI work.
- Separate isolated fixture evidence from real Windows use. The user opened the packaged view through the tray, changed pages, expanded/collapsed Advanced and approved its appearance. Saving Connect at 20 seconds changed both saved config and the live engine interval without restart; restoring 15 was user-reported and then confirmed in saved config and live status. All five UI-owned Spotify values are semantically restored and Windows startup is preserved; a save can materialize previously implicit defaults, so do not claim byte-identical config after this trial. Real monitor/DPI changes, screen-reader use, a human keyboard walkthrough and diagnostic hardware feedback were not separately tested and do not automatically become release gates.
- A natural log result on installed `18465D92…` records `ART_READY` for 37,632 bytes on attempt 1 at 11:25:42, `ART_SENT duration_ms=5000 protocol=art2 frames_per_write=2` at 11:25:47.956 and successful ACK 7 ms later. Record this as send/acknowledgement evidence; no separate visual cover judgment was requested in the UI trial.
- On 2026-10-07 the user reported “Sömn och väckning verkar funka” for the installed `6A5366C1…` / `41BE575E…` pair. Record this as a qualitative observation. No exact timing, current measurement, light-flash audit or complete regression result is inferred.

## 2026-10-06 – Keep UART framing on core 0 and display state on core 1

- The installed Arduino core runs `loopTask` on core 1 in a dual-core FreeRTOS build. Its UART driver already buffers bytes, but the loop previously paid for each read and each newline decision while also rendering Player. Add one priority-1 task pinned to core 0 that reads up to 256 bytes at once and frames complete lines or 192-byte legacy RGB blocks. A 96-event FreeRTOS queue keeps their original order. A full queue blocks the producer with bounded memory rather than dropping a frame silently; CRC/length checks on core 1 still reject incomplete art2 images. If queue/task creation fails, the prior synchronous block reader remains available.
- Core 1 remains the sole owner of command interpretation, transfer ID/CRC/base64 decode, staging buffers, active artwork swap, LVGL/TFT/touch and serial TX. This keeps new-track, abort, resync, raw RGB and dark-sleep behavior in one order. The worker recognizes only the exact valid legacy header after the same whitespace trimming used by the main parser; binary NUL/newline bytes stay raw until all 37,632 bytes have been received. Overlong/partial lines and stalled raw transfer get bounded error events.
- Before runtime deep sleep, core 1 requests a generation-acknowledged pause from the RX task, then checks its queue, partial line/raw state and UART. It checks again after LCD Sleep IN; if bytes arrived, it restores the controller with the backlight dark and waits for a complete valid STATS before lighting it. The initial dark probe never lets pending bytes bypass the two-valid-STATS presence rule. A 20-second art2 absolute duration limit remains in force, even when queued bytes delay the normal stall check.
- Build evidence: `.pio/build/esp32-024r-spotify-fastserial/firmware.bin`, 926432 bytes, SHA-256 `6A5366C1E56E1137AEBC08E6675CBB12E1A49AE106D2DBD03B30132C6A7D2302`, also copied to `.pio/candidates/art2-core0-rx-6A5366C1.bin`. PlatformIO fastserial succeeded at 34.2% RAM and 47.1% flash. All 58 Python tests passed; the C++ receiver tests compile with Xtensa but cannot run on this host. The 924576-byte block-only candidate `5DA16800…` is separately preserved in `.pio/candidates/art2-blockread-5DA16800.bin`. Physical results are recorded below; they do not replace the outstanding sleep/wake check.
- The project lead subsequently read back the installed 923408-byte `4376ED12…` app at `0x10000` to `.pio/device-backups/art2-dualcore-20261006-preflash-app-0x10000.bin`; local SHA-256 verification matches `4376ED12820E4906ADA44F429B624B6F9A1C38EBB6AB084B0DA7ED7B2CCA5B67`. Esptool then wrote the frozen 926432-byte `6A5366C1…` candidate only at `0x10000`, using 115200 baud and `no_reset/no_reset`, in 37.9 seconds with `Hash of data verified`. NVS was preserved and the unchanged `41BE575E…` companion was stopped for flashing.
- After normal reset, COM6 connected at 11:52:09 and device resync ran at 11:52:12. Two startup legacy uploads succeeded; art2 handshaking followed at 11:52:22. At least five art2 first attempts succeeded in the session, taking 4968–5563 ms with ACKs 8–35 ms after `ART_SENT`, without art2 rejection or retry. The user confirmed correct covers after roughly five seconds for three normal changes and smooth text/vinyl during upload, compared with the previous 17–19-second result and brief freezes. Two quick NEXT actions during transfer left the correct final track/cover and no stale cover reappeared; older seq5/6 aborted as `track_mismatch` and final seq7 succeeded. Pause/resume, DJ swipe, long press/menu/Focus and touch during upload were confirmed. Fresh telemetry showed connection, 182324-byte free heap and 178536-byte minimum, consistent with task/queue allocation but without independent runtime core telemetry. No new Spotify 429 occurred.
- On 2026-10-07 the user qualitatively reported that sleep and wake seem to work on this installed pair. Exact timings, deep-sleep current and a complete regression remain unmeasured. The earlier failing version established the bounded retry/backoff behavior; no new forced failure/recovery was exercised on `6A5366C1…`. The successful Player session does not establish fault-free behavior under every load.

## 2026-10-06 – Read UART in bounded blocks after live art2 failures

- The flashed `4376ED12…` line assembler preserved fragments, but three live fast artwork sends still failed with `art2_line` or `art2_decode` and needed slow retries before their covers appeared after roughly 17–19 seconds. A later track also failed on two slow retries. Player text and vinyl briefly froze during transfers. First-attempt success and smooth rendering are still open hardware criteria.
- Arduino `HardwareSerial::read()` takes the UART lock for each byte. Keep the existing per-loop 5 ms/2048-byte/10-line budget, but prefetch up to 256 bytes per `HardwareSerial::read(buffer, size)` call. Pass any prefetched bytes after a legacy RGB header to its raw receiver before reading more UART bytes; do not parse binary artwork as lines. Defer a partial-line timeout while bytes remain buffered, and retain art2's 20-second absolute limit. Use the existing allowlisted `art2_stall` reason for an incomplete line timeout. The companion EXE, serial frame format, retry policy, CRC and deep-sleep presence rules remain unchanged.
- That block-only candidate was **built but never flashed** and is preserved as `.pio/candidates/art2-blockread-5DA16800.bin`, 924576 bytes, SHA-256 `5DA16800A2A2E7F1CBD4624711498B72EF25B4FE9083A6A771C6BF7BF3861AA0`. The fastserial build passed at RAM 34.2% and flash 47.0%; all 58 Python tests passed. Xtensa syntax compilation passed for the serial receiver tests, including a legacy raw boundary crossing a prefetched block with binary newline/NUL and subsequent `PING`, but the C++ tests could not execute on the host. Physical ACK, cover, metadata, rendering, touch and dark wake remain unverified for that candidate.

## 2026-10-06 – Bound serial line draining during Player artwork

- On the installed `CF5F4DCD…`/`41BE575E…` pair, a single current Spotify API track produced `art2_line` on the fast upload and `art2_decode` on all three single-frame retries; the fourth was exhausted and the cover stayed absent. Text and vinyl stuttered during those transfers, then became smooth again. Later tracks alternated between fast rejection and successful slow retry; a rapid NEXT sequence correctly aborted older transfers and eventually acknowledged its last cover. These are live observations of a receiver/framing/load fault, not proof that the new parser solves it.
- The existing firmware reads one line per main loop, while a 230400 first attempt sends two newline-delimited frames per write. Heavy Player rendering can therefore let its 8192-byte UART queue grow; the 10 ms `readStringUntil()` timeout can also dispatch a partial line. Replace that blocking read with a fixed 256-byte assembler that waits for newline and preserves fragments across loop turns. Drain at most 10 lines, 2048 bytes or 5 ms per turn, then return to LVGL/touch. An incomplete line expires after 250 ms, and overflow is dropped through the next newline. Keep the legacy RGB receiver separate and stop line draining immediately after its header. The existing CRC, staging, transfer ID and bounded cached retries remain unchanged.
- Compile the split/burst/budget/legacy-boundary C++ test with the ESP32 toolchain and keep hardware acceptance open until the real Player shows correct cover ACK and image, prompt title/artist/time during transfer, responsive touch and smooth animation. Check dark timer wake and the content-free reason log too. The host cannot execute the Xtensa test binary in this workspace.
- After a failed first connection with no write, the project lead entered BOOT again and read back the installed `CF5F4DCD…` app at `0x10000` to `.pio/device-backups/art2-rx-20261006-preflash-app-0x10000.bin`; the 923216-byte read matched the prior app hash. Esptool then verified the 923408-byte `4376ED12…` app written only at `0x10000` using 115200 for flashing. The installed `41BE575E…` companion was stopped and unchanged. Reset and COM6 later worked, while the live Player results and remaining risk are recorded above.

## 2026-10-06 – Recover a cached cover after repeated art2 rejections

- Real Spotify API covers succeeded four times near 5.6 seconds on the installed 230400 pair, then one current track received two `device_error` replies and no further cover attempt. The installed sender only retried once. Restarting that same EXE caused a new cover upload to succeed, showing that the cache and current track could recover; the old id-only errors do not reveal why the receiver rejected those frames.
- Keep art2 frame bytes, handshake, transfer IDs, CRC, staging and metadata/touch slots unchanged. After an art2 rejection or ACK timeout, schedule at most three further sends of the cached frame with 2, 12 and 30 second delays. The first attempt may batch two frames at 230400; every retry uses one frame per write. The existing sender thread services due retries without another Spotify poll or a new thread. Track changes, resync, disconnect and shutdown invalidate pending retries; current connection, epoch and track are checked again before sending. Log exhaustion instead of retrying without bound.
- Add a separate `MEDIA_ART2_REASON:<id>:<fixed code>` line before the unchanged `MEDIA_ART2_ERROR:<id>` line. Old companions still receive their expected error and ignore the reason line. New companions accept only allowlisted codes for the current transfer ID and log them without media content. Existing generic `device_error` remains valid for older firmware. The first physical repro with this paired candidate must establish whether rejection is from decode, offset, CRC, incomplete frame, stall or another receiver check; no cause is inferred from the older log.

## 2026-10-05 – Batch art2 frames on the local 230400 baud runtime pair

- Keep the default firmware profile at 115200 baud and keep esptool flashing at 115200. The optional 230400 firmware app was written only at `0x10000` after reading back the previous app; NVS was preserved. The companion config backup was verified before changing only `connection.baudrate` to 230400. The baud increase alone left a real cover at 9156 ms, close to the 115200 observations around 9200 ms.
- At 230400 on the first art2 attempt, send two unchanged, newline-delimited 128-byte chunks in one serial write/flush, with the existing 15 ms pause between pairs. Keep metadata and old-track checks between pairs; a rejected or timed-out attempt retries with one chunk per write. The 115200 and legacy paths retain their old pacing. Diagnostics record `frames_per_write` without media content.
- A direct ESP32 COM6 probe with the same 37,632-byte test image measured 9140–9156 ms for one frame per write and 4938–5016 ms for four two-frame runs; all six transfers received matching `MEDIA_ART2_OK` replies. The first probe opened the port with different DTR/RTS states and got no reply; using the companion's normal serial-open state restored the art2 capability response and successful transfers. These measurements isolate the serial transfer, not Spotify image acquisition or display time.
- Install the candidate EXE with SHA-256 `D9187CC406912B142CA1E5F042A6CCD875B051F1D7F62AA2B8918E5190D1CB43` at the existing path after backing up the previous installed EXE as `BongoDeskSpotify.backup-20261005-runtime-speed-57E288E1.exe` and verifying SHA-256 `57E288E1D8120AA04E00D7EC235D9C28E7DC1021E2FC3AD7F48849683AF6A877`. Two normal processes, COM6 connection and a fresh art2 capability handshake returned. Spotify was not running on the PC during the installation check, so an end-to-end cover, rapid track changes, touch and dark wake remain live checks. No release or push was made.

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

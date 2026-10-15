# Windows companion

## Current development state (2026-10-15)

The installed development companion is **17466EBF**, paired with firmware
**F406C485** on the display. Known active API playback during the day uses a
**5 s base cadence**, before budget pressure, higher learned pacing and
Retry-After. Night/idle can be slower; the separate 0.5 s request minimum
does not describe current automatic day polling. The user qualitatively
accepted automatic mobile track text, correct covers and smoothness; phone
action timestamps and end-to-end latency were not measured separately.
Long runtime and sleep/resume with this pair remain pending.

**Seek firmware 57894EE0 is built, not flashed and not yet screen-tested or
physically accepted.** Current source includes seek support; installed F406
does not have the timeline gesture. The isolated 3/5 s comparison leaves
the real setting at **5 s**. See [runtime evidence](../docs/api-budget-runtime-2026-10-15.md),
[cadence analysis](../docs/api-cadence-3s-analysis-2026-10-15.md) and the
[handoff with exact hashes](../docs/lead-handoff-2026-10-15.md).

The sections below retain dated release/installation history. App-v1.3
remains the latest published release; this source update creates no release.

`BongoDeskSpotify` runs on Windows and sends system, typing, and media state to the ESP32 over serial. The engine runs on the main thread; the tray and settings UI run alongside it. App-v1.3 pairs **230400 runtime baud** with the [app-only firmware](../release/BongoDesk-app-v1.3-2026-10-07-app-0x10000.bin) or [full image](../release/BongoDesk-app-v1.3-2026-10-07-full-0x0.bin). Flashing stays at **115200 baud**. App-only preserves NVS with the same partition layout; the full image overwrites NVS and is segment-verified but has not been flashed from `0x0`. Earlier releases, including app-v1.2, remain separate. See [v1.3 notes](../release/app-v1.3-notes.md) and [verification](../release/app-v1.3-verification.md).

New profiles default to 230400. Existing explicit baud settings are preserved. To upgrade an existing 115200 profile to the v1.3 firmware, exit the companion and change only `connection.baudrate` to `230400` in `%APPDATA%\BongoCat\config.json`. Keep the other settings and Spotify authorization. The named firmware environment `esp32-024r-spotify` remains available for an explicit 115200 runtime pairing.

The following dated installation/development sections describe earlier candidates. The v1.3 candidate changes only baud defaults and reuses the frozen UI and physically tested firmware; its installation result is recorded in the v1.3 verification report.

## Earlier native companion UI installation (2026-10-07)

The native settings window now has **Översikt**, **Inställningar** and **Diagnostik**, with dark Player/Focus surfaces, the existing pixel cat and Swedish text. It preserves the existing five numeric settings, Windows startup option and diagnostic actions. The active tray opening path still launches `settings.ps1`; presentation is dot-sourced from `settings-view.ps1`. Both scripts and `ui/bongo.png` are included in the ordinary PyInstaller spec. See [native fixture previews and UI notes](../visuals/companion-ui/README.md).

After the user approved the refined preview, Lead installed the frozen `dist/companion-2026-10-07-ui-refined-dev/BongoDeskSpotify.exe` at `%LOCALAPPDATA%/BongoDesk/BongoDeskSpotify.exe`: 19,299,592 bytes, verified SHA-256 `18465D92AA67E23F09FF0B3B1636D6CD7840A8B1B3B7C90D35D185B7A50D445E`. The previous `41BE575E…` EXE was backed up and hash-verified as `BongoDeskSpotify.backup-20261007-ui-refined-41BE575E.exe`; config was backed up to `%APPDATA%/BongoCat/config.pre-ui-refined-20261007.json`. Config, credentials and the Windows Run entry were unchanged at installation. Starting with `--startup` produced two normal processes at 11:19:02/04 Stockholm time, successful serial connection at 11:19:06 and art2 handshaking at 11:19:10. Fresh status showed the ESP32 connected at 230400 baud, Spotify ready with source `spotify_api` and an effective Connect interval of 15 seconds. Engine source and the installed `6A5366C1…` firmware are unchanged.

The user opened the packaged view from the cat tray icon, changed pages, opened/closed Advanced and said “Japp ser bra ut”. Saving Connect at 20 seconds changed both `spotify.api_only_poll_interval_seconds` in config and `media.effective_poll_interval_seconds` in the running engine to 20, without restart and with fresh device contact. The user restored 15, saved and reported “15s nu” after being asked to reopen; Lead then confirmed saved 15 and effective 15.0. The five UI-owned Spotify values are semantically restored, Windows startup is preserved and all other config is identical as JSON. A save can add previously implicit defaults, so this does not establish byte-identical config after saving or a separate measured reopening/keyboard result.

A natural runtime log on the installed EXE recorded `MEDIA_TRACK seq1` and `ART_READY` for 37,632 bytes on attempt 1 at 11:25:42, followed by `ART_SENT duration_ms=5000 protocol=art2 frames_per_write=2` at 11:25:47.956 and a successful `ART_ACK` 7 ms later. This is a first-attempt transfer/acknowledgement result; no separate visual cover assessment was made in this UI trial.

Embedded settings scripts, cat asset and default config match source byte for byte. The 58 companion Python tests, existing PowerShell diagnostics test and 546 isolated UI assertions passed during UI development. Previews use synthetic fixture data; 150% images stress layout rather than real monitor/DPI switching. Actual DPI changes, screen-reader use, a human keyboard walkthrough and diagnostic actions' hardware feedback were not separately tested. These limitations are recorded without adding automatic release gates. Published release files have not changed.

## Diagnostic development build (2026-10-01)

The current source adds bounded event logs for serial reconnection, media source changes, cover retrieval/conversion, upload and ESP32 acknowledgement. The tray item **Export diagnostics ZIP...** writes a ZIP to Desktop (or Downloads/Documents/home when Desktop is unavailable) and opens that folder. Logs live in `%LOCALAPPDATA%\BongoDesk\logs`, rotate at 256 KiB with three backups, and do not include song/artist text, artwork, URLs, credentials, tokens, configuration files, or raw exception messages. Review a ZIP before sharing it; timestamps and event sequence remain visible. The ZIP is created only when the user chooses the tray item.

For a Spotify Windows session with a missing or repeatedly failing thumbnail, a linked Spotify Web API account can supply artwork if the current title and artist match. The API check is at most once per 60 seconds while needed; it does not replace Windows metadata or add serial polling. Each cover source uses the configured limit of 1–5 short attempts, then can try the same track again after 90 seconds. A successful image conversion is required before marking the cover complete. The diagnostic development build was installed separately on 2026-10-01. The user saw the normal Bongo UI and confirmed that **Export diagnostics ZIP...** opened a folder containing a new ZIP. Future cover failures and recovery have not been provoked on the physical display; the diagnostic features are now included in `app-v1.2`.

## Earlier Spotify cooldown candidate (2026-10-02)

Phone playback cannot be read from a local Windows media session. A diagnostic ZIP recorded a Spotify 429 with a 34,696-second `Retry-After` at 05:24, valid until about 15:02:49 local time; later startup messages reflected the saved cooldown, not new HTTP 429s. The response body was not saved, so quota exhaustion is a plausible but unproven cause. The user's Spotify dashboard showed `/v1/me/player` dominating at roughly 17–27 thousand requests per day; media controls were near baseline. A manual reset to a 0.5-second adaptive interval came after the first 429.

The new source uses existing `MEDIA_*` messages to show `Spotify API paused` and the local retry date/time on the ESP32, with no current track or stale cover. Touch commands during the wait are discarded and the same track's cover can be fetched again after recovery. With no local Spotify session, automatic API playback reads have a 15-second minimum interval; the ESP32 advances displayed progress locally between updates. The next real HTTP 429 logs only a whitelisted structured reason (`quota_exceeded` or `unspecified_429`), request category, `Retry-After`, and bounded 15-minute request counts. Restarts log `saved_cooldown` separately. No tokens, URLs, song text, raw HTTP responses or cover bytes enter the diagnostic ZIP.

All 28 then-current companion tests passed, including long cooldown, restart, recovery, waiting display, request pacing and same-track cover restoration. The separate build `../dist/companion-2026-10-02-429-dev/BongoDeskSpotify.exe` has SHA-256 `2F5CA6524307985405751577C2E83FD47D366CFD3E79AA55B7A6978FF328B38E`. After explicit approval for this exact hash it was installed on the existing path with backup `BongoDeskSpotify.backup-20261002-140605-876B3C15.exe`. Two normal processes, serial contact and the saved cooldown were observed. The user confirmed the waiting status on Player and normal Bongo UI with time/statistics. Actual track and artwork recovery after Spotify's deadline remain pending. This work is included in the newer `app-v1.2` EXE.

## Local Spotify fix (installed 2026-10-02)

The source now keeps a local Windows Spotify session as the only metadata and touch-control source. During a long serial cover upload it retains the latest song state, sends that state and its default cover before the next track's tagged artwork, and discards queued artwork for older tracks. The reply watchdog gives a successful cover upload a full reply interval before treating COM6 as stale; a failed serial write still triggers reconnection. The diagnostic log records only a fixed touch action (`PLAY_PAUSE`, `NEXT`, `PREVIOUS`) and whether the Windows media session accepted it; it does not include song metadata. Spotify's API-only poll floor and the serial protocol are unchanged.

In a temporary source run, the user confirmed that play/pause, double-tap NEXT and triple-tap PREVIOUS changed Spotify on the PC while the display showed the correct title and cover. The log recorded incoming actions and successful Windows controls. After explicit approval, the rebuilt candidate `../dist/companion-2026-10-02-local-media-dev/BongoDeskSpotify.exe`, SHA-256 `71756E01987D8A84C76DDCF83B76E9C512A7B5B2E09439DB94D10E36109ABF9F`, was installed at the normal path. The previous EXE was saved and verified as `BongoDeskSpotify.backup-20261002-170933-2F5CA652.exe`. Two processes, COM6, cover ACKs and no later `SERIAL_LOST` were observed. On the installed build the user confirmed current title and cover, play/pause, and double-tap NEXT in Spotify and on the display. After several rapid track changes the user still saw the current song and correct cover; the log showed a successful cover ACK and no `SERIAL_LOST`. PREVIOUS was not separately retested after installation. All 34 companion tests, syntax compilation, whitespace check, and archive inspection passed. The same EXE is now packaged in `app-v1.2`.

## Download app-v1.3 companion

Download [BongoDeskSpotify-app-v1.3-2026-10-07.exe](../release/BongoDeskSpotify-app-v1.3-2026-10-07.exe) and its [SHA-256 file](../release/BongoDeskSpotify-app-v1.3-2026-10-07.sha256). The EXE is 19,299,418 bytes with SHA-256 `5609B99DAA1321ECB78B6384F1D5271DB23DBBF1BD6A2E2BBB49D6FD7AFEFD1D`. It is byte-identical to the release candidate installed and hash-verified by Lead. Connection succeeded on attempt 1; a natural art2 cover upload took 4859 ms with a successful ACK 34 ms later. Config and the Windows Run entry stayed unchanged. No new visual UI walkthrough was performed; UI resources match the already visually tested build. This build is unsigned; check the hash before running it. Personal config, backups and OAuth tokens are excluded from the package.

Exit any running Bongo Desk companion through its tray icon before double-clicking the new EXE. Only one instance can run at a time. The serial port defaults to `AUTO`; choose the ESP32's COM port in settings if needed. The older `release/BongoDeskSpotify.exe` is a legacy build and is not the current download.

The app keeps settings and OAuth tokens in the current user's `%APPDATA%\BongoCat` folder. To connect your own Spotify account, create a Spotify developer app with redirect URI `http://127.0.0.1:43821/callback`, then run the downloaded EXE from PowerShell in its folder:

```powershell
.\BongoDeskSpotify-app-v1.3-2026-10-07.exe --spotify-client-id YOUR_CLIENT_ID --link-spotify
```

Complete authorization in the browser, then start the EXE normally. This uses Spotify's browser authorization flow and stores the token in your Windows profile; no token is included in the release. If Windows exposes a Spotify media session, the companion uses it; otherwise it can use the linked Spotify API account. A normal launch follows the user's autostart setting and may update the per-user Run entry to this EXE's location.

## Run from source

From the repository root, with Python 3.10 or later:

```powershell
python -m pip install -r companion/requirements_app.txt
python companion/main.py
```

The ESP32 should be connected before starting the app. The serial port defaults to `AUTO`; set `connection.com_port` in the config if automatic detection does not find it. Settings and Spotify OAuth tokens live in `%APPDATA%/BongoCat`, outside the repository.

Supported command-line options:

```text
--minimized          Start with the tray icon in the background
--startup            Mark a Windows autostart launch
--spotify-client-id  Save a Spotify developer Client ID
--link-spotify       Authorize Spotify using the saved Client ID
```

For example, after creating a Spotify app and adding its redirect URI, run `python companion/main.py --spotify-client-id YOUR_ID --link-spotify`. You can also configure Spotify through the app's settings.

### Preventive API budget development candidate, 2026-10-14

The current source adds a shared, persistent local API budget. Automatic
playback and artwork fallback reads may use at most 18 attempts per rolling
30 seconds and 7200 per rolling 24 hours; all attempts together are bounded
by 24 and 8000. Explicit controls/seek can use the remaining total capacity
through short operation grants. A free urgent flag cannot bypass the budget.
Failed HTTP attempts and genuine 401 retries also count. OAuth and CDN image
downloads are outside the `/v1` ledger.

The selected playing defaults are 5 seconds by day and 30 seconds at night
(00–08, `Europe/Stockholm`). Idle floors are 15/60 seconds. Higher saved idle,
adaptive backoff, server deadlines and budget pressure win. At 50/80 percent
usage the profile slows, with further spreading of remaining capacity from
80 percent. These are base intervals: HTTP duration and durable writes add
time, and sustained heavy use can produce substantially longer discovery.
Only real key activity or an explicit control can arm a bounded five-second
fast period. Automatic track changes cannot keep fast polling active.

New `spotify.api_budget_*` JSON fields configure limits/profiles; existing
values are preserved. No settings layout was changed. Numeric status under
`local_budget` distinguishes local waits from a real Spotify 429, and media
status includes the age of the last API snapshot. Local budget waits retain
last metadata while Windows sessions continue to be checked.

History is stored in `spotify_api_budget.json` beside the token file, with
bounded numeric entries and no media, credentials or raw input. Pending cost
is durable before HTTP; final costs use conservative completion timestamps.
File errors/corruption fail closed. Known `Retry-After` remains authoritative,
including if the final write fails. QUOTA recovery uses a 60-second floor and
half 24-hour budget for 24 hours after retry, followed by a 30-second floor
and 75 percent of the 24-hour budget for 48 hours. Short-window limits remain
24/18. Unknown initial history also gets a guarded day.

An abrupt process stop during HTTP can leave an unresolved pending claim.
On recovery this causes a **24-hour local quarantine**, distinct from
Spotify's `Retry-After` and the ordinary ten-minute clock continuity guard.
The lost server response cannot prove its exact deadline. Before a later
candidate swap/rollback, Lead should stop traffic and confirm no request is
in flight and no pending claim remains, under the shared profile lock. No
new shutdown feature or live installation is part of this development step.

The frozen EXE is `dist/companion-2026-10-14-api-budget-dev/BongoDeskSpotify.exe`, 19,654,754 bytes, SHA-256 `B8C7BB2859F86737686899C86C2FA48CDE3702BD5CCBF28A86B13D45C7CC417E`.
The separate candidate and exact tests/simulations are documented in
[`docs/api-budget-2026-10-14.md`](../docs/api-budget-2026-10-14.md).
It has not been started or installed; F406/68CC runtime observations apply
to that installed pair. Frozen seek artifacts and published releases remain
unchanged. Local limits reduce this app's usage and cannot guarantee freedom
from Spotify limits shared with other apps under the developer account.

### Spotify Connect pacing and diagnostics, 2026-10-11 version

The current source and separate **2026-10-11 adaptive Connect candidate** use the API's adaptive request-start interval for active playback. Without a recorded restriction, startup uses `api_min_interval_seconds` (new default **0.5 s**). A repeated unchanged track never adds the old 15-second wait. Polls, touch controls, confirmation reads and artwork fallback share one locked start-time gate; urgent calls cannot bypass that spacing or an active persisted `Retry-After`.

`api_only_poll_interval_seconds` is deprecated. A saved value such as 15 remains in the profile for compatibility but is ignored, is no longer validated and is not edited by the active native UI. No profile/token migration is needed. Existing explicit adaptive values are preserved. New defaults are minimum 0.5 s, `api_initial_interval_seconds` 1 s as the least backoff **after a 429**, and idle 3 s. Paused/empty playback uses the idle bound; local Windows Spotify stays authoritative and needs no continuous Connect polling. The currently installed user profile was subsequently changed by Lead to **idle 15 s / active minimum 0.5 s**, after the user requested slower polling when nothing plays. Only `spotify.api_idle_interval_seconds` changed, with `config.pre-idle15-20261011.json` saved first. This is a profile preference supported by the existing implementation; the candidate's fresh-profile idle default remains 3 s, and explicit older values are preserved. Live reload and the pause trial were confirmed: the user reported paused playback, and fresh status at 13:44:51.110 Stockholm showed `api_only_idle=true`, effective interval 15.0 s and adaptive interval 0.5 s, with Spotify ready and the ESP32 connected. Total 429 remained 1, with zero in the last 15 minutes. The 32-call/30 s counter was a transition window, not a steady idle-rate measurement. Mobile playback starting during idle may take up to 15 s to be detected; active polling then follows the adaptive bound again. Resume was also confirmed in fresh status at 13:46:09.849: `spotify_api`, idle false, effective interval 0.5 s, Spotify ready, ESP32 connected and zero 429s in the last 15 minutes. Both 15 s paused and 0.5 s active intervals are observed; exact transition latency was not separately measured.

On 429, the adaptive interval doubles within configured bounds and a 25% learned margin is recorded. The saved deadline blocks all API work across restarts. Starting with the first successful post-cooldown response, a clean 30-second window allows both interval and learned margin to decrease by 10%; later clean windows continue toward minimum. Quota recovery pauses this speed-up. The old learned margin is no longer permanently sticky.

Waiting uses the **remaining request-start deadline**, including idle and quota floors, rather than adding another whole interval after HTTP or artwork work. HTTP latency, image work and scheduling may still make actual reads slower than the bound. The native UI shows the minimum in the Connect card and current adaptive/idle/quota-bound interval plus real 30-second/15-minute call counts in Diagnostics. `retry_remaining_seconds` separately describes an active Spotify wait. There is no extra track-end polling path.

This source change is **not included in the published app-v1.3 EXE**, which retains its earlier fixed Connect floor. The isolated candidate is `dist/companion-2026-10-11-adaptive-connect-dev/BongoDeskSpotify.exe`, 19,300,127 bytes, SHA-256 `68CC5BC1D90E0AB734D0997D03980653858C717F88AB4B97E42648E6DC93FE97`. The packaged code, settings scripts, defaults and cat asset match the source; personal profiles/tokens are excluded. The 65 Python tests, diagnostic formatting test, source compilation and 538 native UI assertions passed. Fake HTTP lasting 120 ms produced starts 0.5 s apart through the actual media loop with a legacy saved 15 s field. Mocked 429/restart/urgent guards, gradual recovery, idle/quota bounds, config/token preservation and single-worker startup were verified. Native renders in ignored `build/adaptive-connect-ui/` use synthetic data; the tracked UI previews describe the earlier v1.3 view. Lead installed the exact candidate on 2026-10-11 with verified rollback and config/token backups. Config, token file and Windows Run entry were byte-identical during copying; runtime pacing metadata can subsequently change the token file. Fresh status at 13:38:51 Stockholm showed active `spotify_api`, adaptive mode and effective/current/safe intervals of 0.5 s, no cooldown/quota floor, unchanged config with the deprecated 15 s value still present, and connected ESP32 at 230400. Total 429 stayed 1, with zero in the last 15 minutes. The 24-call rolling counter came from a startup session shorter than 30 seconds, not a steady-state rate measurement. Two natural first-attempt covers took 5625/5593 ms, with successful ACKs 26/62 ms later. The user reported after a couple of mobile changes: “Nu byter den instantly, och skivan kommer snabbt och ser ut att vara smooth”. This qualitatively confirms prompt track changes, fast artwork and smooth vinyl; no stopwatch latency was measured. Later live status at 13:40:00.400 showed 56 requests over the preceding 30 seconds and the same 0.5 s active bound. Rapid mobile changes seq3–8 cancelled older covers as `track_mismatch`; final seq8 succeeded on attempt 1 in 5515 ms with ACK 19 ms later. No new 429, device error or serial disconnect was observed in this short trial. No firmware build/flash, real 429 test or new release was done.

Spotify's [playback response](https://developer.spotify.com/documentation/web-api/reference/get-information-about-the-users-current-playback) includes track progress, duration and album image URLs together. The companion publishes new text before fetching or sending the image; it does not make a second Spotify Web API metadata request just to discover the cover URL.

The local Windows Spotify session remains authoritative when it exists. An actual HTTP 429 obeys Spotify's `Retry-After` across restarts. A structured `QUOTA_EXCEEDED` additionally keeps automatic Connect polling at least 60 seconds apart for 24 hours after the retry deadline and pauses automatic speed-up during that period. A manual adaptive reset does not remove this quota recovery period. Spotify's [development quota](https://developer.spotify.com/documentation/web-api/concepts/quota-modes) and [rolling rate limit](https://developer.spotify.com/documentation/web-api/concepts/rate-limits) are separate; no fixed safe request count is promised.

The stored `adaptive_total_429` counts actual Spotify Web API HTTP 429 responses and persists across restarts, including after they leave the rolling 24-hour display. On first upgrade it seeds from all surviving entries in the bounded legacy event list, including older entries that were not trimmed by a newer 429, or one known last response if that list is missing. Earlier history beyond those saved records may still be missing. Cached cooldown checks and manual resets do not increment it. Settings, local status, and the privacy-limited ZIP export show the registered total without credentials or song data.

The pacing experiment initially kept the default profile at 115200 and used `esp32-024r-spotify-fastserial` for 230400. App-v1.3 makes fastserial the default and keeps flashing at 115200. Every 112×112 RGB888 cover is 37,632 bytes. The companion logs `ART_SENT duration_ms` and delayed metadata delivery, and flushes the latest text as soon as a raw frame finishes, before waiting for its acknowledgement.

### Previous installed development candidate (2026-10-04)

After explicit approval, `../dist/companion-2026-10-04-pacing-dev/BongoDeskSpotify.exe` was installed at `%LOCALAPPDATA%\BongoDesk\BongoDeskSpotify.exe`. The installed EXE has SHA-256 `106B2A4D58B51400DBCC98B3B2E706A9C1C563885B18336790E0D40AB29BA858`. The previous EXE was saved and hash-verified as `BongoDeskSpotify.backup-20261004-201706-71756E01.exe` (SHA-256 `71756E01987D8A84C76DDCF83B76E9C512A7B5B2E09439DB94D10E36109ABF9F`). The first launch inside the tool's restricted environment stopped in the PyInstaller loader before application code; the same EXE started normally outside that environment with two processes. Its log recorded `APP_START` at 20:24:37 and successful serial connection to COM6 at 20:24:40. Local status continued to update with the ESP32 connected and `spotify_api` as the source. At 20:30:50 it showed 25 registered API calls in the observed portion of the rolling 15-minute window, a persistent total of one 429 migrated from a saved legacy event, and zero new 429s in the past 15 minutes. No new track or artwork events had been logged since this installation, so track-change and cover latency cannot yet be compared. The visual Settings view, Spotify track/artwork and touch behavior on this candidate, and tray ZIP export still need a live check. The optional 230400-baud firmware remains unflashed and untested; this installation did not change serial speed, user settings, tokens, autostart or `release/`.

### Artwork v2 local development and installation

The newer source can interleave media text with an artwork upload. At connection or `SYNC_REQUEST`, the companion sends one `CAPS?:<16-hex challenge>` query. Only an exact echo from new firmware enables v2; otherwise it keeps the installed firmware's raw `MEDIA_ART_RGB` transfer. V2 sends `BEGIN`, sequential 128-byte RGB chunks encoded as base64 lines, then `END`, with a transfer ID, frame length and CRC-32. On a new track it sends `ABORT`; the device also discards staging when `MEDIA_ART_DEFAULT` arrives. A full matching frame alone replaces the visible cover. The device rejects corrupt, out-of-order or stalled frames and never treats an incomplete v2 image as companion presence during a dark timer probe. The separate inbound reader continues to accept touch while the sender writes one line at a time.

At 115200 baud the longest chunk line is 202 bytes, about 17.5 ms on an 8N1 wire. The existing 15 ms pause is retained for UART safety, so new metadata normally has a slot within about 33 ms plus scheduling and rendering. A whole 294-chunk cover has at least about 5.15 s of wire time plus 4.41 s of pauses at 115200; it can finish later than the raw protocol even though the title can update sooner. Host `flush()` does not prove that the ESP32 has drained its receive buffer, so the pause has not been shortened. After separate approval on 2026-10-05, the standard v2 firmware app (SHA-256 `636AC267AEDCC4DF1B83693F5B4DCE41DE04C7EB37B8F3D2F3DDDF2740B85AB5`) was flashed to COM6 at `0x10000`, and esptool verified the data. The 230400 build remains unflashed; neither build is in `release/`.

The then-installed companion (SHA-256 `106B2A4D58B51400DBCC98B3B2E706A9C1C563885B18336790E0D40AB29BA858`) reconnected after that flash and the user confirmed normal Bongo UI, current time/statistics, Spotify touch and artwork. The earlier uninstalled v2 EXE (SHA-256 `40A464CE3ECF99F489DD4A145CEB327DDDC0F85E1F1FED15567E8501C5538C45`) then ran temporarily, connected to COM6, received artwork ACKs, and showed the correct last title and cover after two quick screen-initiated track changes. That test EXE did not log the nonce echo or protocol selection, so its transfer does not prove that art2 was selected or quantify the title latency. The source now emits only allowlisted `ART_CAPABILITY result=success protocol=art2` and `protocol=art2|legacy` on artwork send/ACK. A later physical check must interrupt a transfer and check reconnect, deep sleep and dark timer probes without partial images or light flashes. Measure title and cover times before considering 230400 baud.

A separate EXE with that content-free protocol logging was built at `../dist/companion-2026-10-05-artv2-diagnostics-dev/BongoDeskSpotify.exe` (19,293,446 bytes, SHA-256 `0F5B8DE8722D9ADB0CD0E92226488D59988916C6ADE7FF0A5AF0A86A7867956E`). Its archive includes `engine`, `diagnostics`, `media_bridge`, settings and default configuration. All 50 companion tests, `compileall` and `git diff --check` pass. It first ran temporarily on 2026-10-05: `SERIAL_CONNECT` and `ART_CAPABILITY result=success protocol=art2` proved the fresh nonce handshake on the physical device. After explicit approval, the exact EXE was installed at `%LOCALAPPDATA%\BongoDesk\BongoDeskSpotify.exe`; the prior installed file was saved as `BongoDeskSpotify.backup-20261005-170029-106B2A4D.exe` and verified with SHA-256 `106B2A4D58B51400DBCC98B3B2E706A9C1C563885B18336790E0D40AB29BA858`. The installed file's SHA-256 matches the candidate. Its normal start produced two processes, `SERIAL_CONNECT` and `ART_CAPABILITY result=success protocol=art2`; live status shows the ESP32 connected. Spotify was idle, so no `ART_SENT/ART_ACK protocol=art2` has yet been observed with this installed EXE. User settings, tokens and the Run entry were preserved; `release/` is unchanged.

### Player timeline pair tested and installed locally (2026-10-05)

During a long art2 upload, the sender flushes cached media state between artwork chunks. A periodic full sync previously resent a cached elapsed time even though the ESP32 advances playback locally, so the displayed time could jump back to zero. The source now sends `MEDIA_TIME` for a fresh position sample, new track, or resync, while the periodic full sync still sends metadata and play state. A fresh seek backwards, replay and pause still update the device. A regression test simulates an artwork upload lasting more than three seconds; the 53 companion tests and source compilation pass. The matching firmware source also avoids reanchoring its local clock for an unchanged play state.

The separate PyInstaller build `../dist/companion-2026-10-05-timeline-layout-dev/BongoDeskSpotify.exe` is 19,292,590 bytes with SHA-256 `57E288E1D8120AA04E00D7EC235D9C28E7DC1021E2FC3AD7F48849683AF6A877`. Its archive includes `engine`, `diagnostics`, `media_bridge`, settings and default configuration. After explicit approval, the matching firmware app was flashed only at `0x10000` and verified by esptool, then this EXE ran temporarily and was installed after the user confirmed stable playback time, the requested layout, correct artwork and working gestures. The former installed EXE is preserved as `BongoDeskSpotify.backup-20261005-timeline-layout-0F5B8DE8.exe` with SHA-256 `0F5B8DE8722D9ADB0CD0E92226488D59988916C6ADE7FF0A5AF0A86A7867956E`. The installed candidate reconnected to COM6 and received an art2 cover ACK. Four device-error ACKs occurred in two rapid-track-change bursts during the temporary run, but later covers succeeded and the user saw the correct final cover. Runtime baud was 115200 for this test; the later paired speed experiment is below.

### Local runtime artwork speed pair (2026-10-05)

The optional ESP32 profile now runs at 230400 baud while the default build and the flashing tool remain at 115200. The earlier firmware app and companion config were backed up and hash-verified before the change. A real screen-initiated NEXT with the former companion took 9156 ms for art2 and showed the correct cover; baud alone made no clear speed difference. The new companion batches two unchanged newline-framed 128-byte chunks into each host write/flush at 230400, leaving the 15 ms pause between pairs. It still flushes metadata and checks for a changed track between pairs. A failed first attempt retries with the original one-frame rhythm; 115200 and legacy transfers retain their previous pacing.

A direct COM6 test sent the same 37,632-byte image with one frame per write in 9140–9156 ms and with two frames per write in 4938–5016 ms over four runs. Every run received a matching art2 success ACK. The candidate `../dist/companion-2026-10-05-fast-batch-dev/BongoDeskSpotify.exe` has SHA-256 `D9187CC406912B142CA1E5F042A6CCD875B051F1D7F62AA2B8918E5190D1CB43`. It is installed at the normal path after a hash-verified backup of the previous EXE as `BongoDeskSpotify.backup-20261005-runtime-speed-57E288E1.exe`. Two normal processes, COM6 connection and the art2 capability handshake returned. All 54 companion tests and Python compilation passed. Spotify was not running on the PC during this check, so actual Spotify cover timing, quick changes, touch and dark wake remain to be verified. The release files are unchanged.

### Cached art2 recovery candidate (2026-10-06)

The installed 230400 pair has now completed four real Spotify API covers in about 5.6 seconds each. A later track received two `device_error` replies and remained without a cover even though its 37,632-byte RGB image was cached and COM6 stayed connected. Restarting the same EXE restored a successful cover; another fast failure recovered on its slow retry, while a later fast/slow pair failed again. The existing id-only error response cannot identify whether a line, offset, CRC, timeout or another receiver check rejected these transfers.

The source candidate keeps a failed current-track cover in memory and schedules up to three delayed serial retries after 2, 12 and 30 seconds, without a Spotify read or another worker thread. Every retry uses one art2 frame per write; new track, device resync, disconnect and shutdown cancel the pending retry. The paired firmware emits an allowlisted, content-free `MEDIA_ART2_REASON` line before the unchanged `MEDIA_ART2_ERROR` line; older companions still receive their original error response, and the new companion continues to accept older firmware's generic error. The initially separate EXE, before installation, was `../dist/companion-2026-10-06-art2-retry-dev/BongoDeskSpotify.exe` (19,295,321 bytes, SHA-256 `41BE575EDAD6F58346D034555D8B5430941E01E78490608A497C66FC142558B4`). The firmware app built for that installation was `.pio/build/esp32-024r-spotify-fastserial/firmware.bin` (923,216 bytes, SHA-256 `CF5F4DCDD6D40091CC04C06E70DF134A3F079BF31D733BA71CDF732D5FB6CACA`). All 58 companion tests, source compilation and firmware build pass. The pair was later installed and physically tested; the results are below.

### Receiver load investigation (2026-10-06)

The `CF5F4DCD…` firmware and `41BE575E…` companion were installed together after saving verified backups of the prior app and EXE. On a screen-initiated NEXT, the current Spotify API track received `art2_line` on the batched upload and `art2_decode` on all three slower retries. The cover stayed absent and the cached retry limit was reached. Text and vinyl stuttered during transfers and became smooth again afterward; a later track could still succeed. These failures show that bounded retries alone do not fix reception.

The firmware read only one serial line per main loop while the fast sender writes two art2 lines per batch. Under Player rendering, its 8192-byte UART buffer can accumulate a backlog; a 10 ms `readStringUntil()` can also return an incomplete line. The then-new `4376ED12…` firmware retained partial lines in a fixed buffer until newline, dropped overlong lines, and drained at most 10 lines, 2048 bytes or 5 ms per loop before returning to UI and touch. The legacy raw image path stayed separate. This mitigation did not achieve reliable first-attempt reception in the subsequent physical test. That app was flashed only at `0x10000` after a verified backup: 923,408 bytes, SHA-256 `4376ED12820E4906ADA44F429B624B6F9A1C38EBB6AB084B0DA7ED7B2CCA5B67`. The installed companion EXE is unchanged.

The previous 923,216-byte firmware app was read back to `.pio/device-backups/art2-rx-20261006-preflash-app-0x10000.bin` and its SHA-256 matched `CF5F4DCDD6D40091CC04C06E70DF134A3F079BF31D733BA71CDF732D5FB6CACA`. Esptool verified writing the new 923,408-byte app at `0x10000` with a 115200-baud flashing connection. The installed companion was stopped for the read and flash and has not been replaced. Reset, COM6 and art2 handshaking worked, but three fast artwork transfers failed with `art2_line` or `art2_decode`. Slow retries succeeded for those tracks after roughly 17–19 seconds total; another track also failed on two slow retries. Text and vinyl briefly froze during transfer. The receiving failure was not fixed on that earlier installed pair.

### Two-core receiver (Player tested, sleep/wake user-reported)

The current firmware source uses the dual-core Arduino setup: the application loop stays on core 1, and a priority-1 task on core 0 reads UART in blocks of at most 256 bytes. It frames complete text lines and exact 37,632-byte legacy RGB frames into an ordered, 96-event queue. The queue blocks its producer when full without dropping an event; malformed, partial and stalled data still fail closed. Core 1 alone owns art2 ID/CRC/base64 decoding, image staging and activation, LVGL/TFT/touch and all serial replies. A failed queue/task creation falls back to the prior block reader. Before runtime deep sleep, the task acknowledges a pause and the main loop checks queue, partial data and UART; bytes arriving during LCD Sleep IN keep the backlight dark until valid STATS is processed. The companion EXE and art2 wire format are unchanged.

The fastserial app `.pio/build/esp32-024r-spotify-fastserial/firmware.bin` is 926,432 bytes, SHA-256 `6A5366C1E56E1137AEBC08E6675CBB12E1A49AE106D2DBD03B30132C6A7D2302`, with an identical frozen copy in `.pio/candidates/art2-core0-rx-6A5366C1.bin`. The project lead read back the preceding 923,408-byte app to `.pio/device-backups/art2-dualcore-20261006-preflash-app-0x10000.bin`; its SHA-256 matched `4376ED12820E4906ADA44F429B624B6F9A1C38EBB6AB084B0DA7ED7B2CCA5B67`. The frozen two-core app was then flashed only at `0x10000`, using esptool at 115200 baud with `no_reset/no_reset`; the 37.9-second write reported `Hash of data verified`. NVS was preserved. The unchanged `41BE575E…` companion was stopped for flashing, then restarted after normal reset.

The earlier unflashed block-only app remains in `.pio/candidates/art2-blockread-5DA16800.bin` (924,576 bytes, SHA-256 `5DA16800A2A2E7F1CBD4624711498B72EF25B4FE9083A6A771C6BF7BF3861AA0`). PlatformIO fastserial, all 58 Python tests and Xtensa C++ syntax checks passed; C++ tests were not executed on this host.

COM6 reconnected at 11:52:09 and device resync ran at 11:52:12. Both startup legacy frames succeeded, followed by art2 handshaking at 11:52:22. At least five art2 first attempts succeeded, taking 4968–5563 ms with ACKs 8–35 ms after `ART_SENT`, without art2 rejection or retry. The user confirmed correct covers after roughly five seconds for three normal track changes and smooth text/vinyl during upload, compared with 17–19 seconds and brief freezes on the previous app. Two quick NEXT actions during an upload left the correct last track/cover without an older cover returning; older seq5/6 aborted as `track_mismatch` and final seq7 succeeded. Pause/resume, DJ swipe, long press/menu/Focus and touch during upload were confirmed. Fresh telemetry showed the device connected, 182324-byte free heap and 178536-byte minimum, consistent with task/queue allocation but without independent runtime core telemetry. No new Spotify 429 occurred.

On 2026-10-07 the user reported “Sömn och väckning verkar funka” on this two-core firmware with the preceding `41BE575E…` companion, before the UI installation. This is a qualitative observation; exact sleep/wake timings, deep-sleep current and a complete regression remain unmeasured. The UI installation kept this firmware unchanged. The earlier failing version verified bounded retry/backoff; no new forced failure/recovery was exercised on this version. The successful Player session does not guarantee every future transfer.

## Package

The maintained PyInstaller definition is `companion/BongoDeskSpotify.spec`. Run it from the `companion` directory:

```powershell
cd companion
python -m PyInstaller BongoDeskSpotify.spec
```

The bundled application uses a per-user Windows Run entry when autostart is enabled and a named mutex to avoid duplicate instances. The current versioned binary is in `release/`; the 2026-09-24 panel menu binary remains available there, and the unversioned EXE is older and excluded from Git.

## Main modules

| File | Purpose |
| --- | --- |
| `main.py` | Startup and shutdown |
| `engine.py` | Serial link, typing events, system metrics, and media commands |
| `media_bridge.py` | Spotify and Windows media state coordination |
| `diagnostics.py` | Rotating privacy-limited event log and manual ZIP export |
| `spotify_api.py` | Spotify authorization and API requests |
| `config.py` | JSON settings and validation |
| `tray.py`, `gui.py`, `settings.ps1` | Tray and settings UI |
| `windows_integration.py` | Autostart, single-instance lock, foreground app |

The firmware protocol and visual behavior are described in the project root's `00_PROJECT_CONTEXT.md` and `01_CURRENT_STATE.md`. Keep the serial traffic event driven, especially during album-art transfer.

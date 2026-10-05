# Windows companion

`BongoDeskSpotify` runs on Windows and sends system, typing, and media state to the ESP32 over serial. The engine runs on the main thread; the tray and settings UI run alongside it. The current `app-v1.2` [full flash image](../release/BongoDesk-app-v1.2-2026-10-03-full-0x0.bin) matches the [companion EXE](../release/BongoDeskSpotify-app-v1.2-2026-10-03.exe) below. Both are needed for media state and artwork. The complete image was also flashed from `0x0` on 2026-10-03 and verified; the saved NVS partition was restored and read back byte-for-byte before normal startup. The 2026-09-30 deep sleep release and 2026-09-24 panel menu release remain available separately.

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

## Download the published app-v1.2 companion

Download [BongoDeskSpotify-app-v1.2-2026-10-03.exe](../release/BongoDeskSpotify-app-v1.2-2026-10-03.exe) and its [SHA-256 file](../release/BongoDeskSpotify-app-v1.2-2026-10-03.sha256). The EXE hash is `71756E01987D8A84C76DDCF83B76E9C512A7B5B2E09439DB94D10E36109ABF9F`. It matched the locally installed and physically tested companion when `app-v1.2` was published. A newer development candidate is now installed locally; the published release files have not changed. This build is unsigned; check the hash before running it.

Exit any running Bongo Desk companion through its tray icon before double-clicking the new EXE. Only one instance can run at a time. The serial port defaults to `AUTO`; choose the ESP32's COM port in settings if needed. The older `release/BongoDeskSpotify.exe` is a legacy build and is not the current download.

The app keeps settings and OAuth tokens in the current user's `%APPDATA%\BongoCat` folder. To connect your own Spotify account, create a Spotify developer app with redirect URI `http://127.0.0.1:43821/callback`, then run the downloaded EXE from PowerShell in its folder:

```powershell
.\BongoDeskSpotify-app-v1.2-2026-10-03.exe --spotify-client-id YOUR_CLIENT_ID --link-spotify
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

### Spotify Connect pacing and diagnostics

When Spotify plays on another device, **Connect-uppdatering** controls the normal `/me/player` poll interval. It defaults to 15 seconds and accepts 10–120 seconds. Continuous polling at 15 seconds is about 5,760 base reads per day; 10 seconds is about 8,640. Touch actions and at most one earlier check near a predicted natural track end add requests. The Player extrapolates progress locally between reads. The "fastest" API setting is only a lower bound for adaptive spacing, not the observed request rate. The settings window shows the selected bound, current effective normal Connect interval, and actual calls over rolling 30-second and 15-minute windows. A zero count in a five-second interval would be normal at the default pace.

Spotify's [playback response](https://developer.spotify.com/documentation/web-api/reference/get-information-about-the-users-current-playback) includes track progress, duration and album image URLs together. The companion publishes new text before fetching or sending the image; it does not make a second Spotify Web API metadata request just to discover the cover URL.

The local Windows Spotify session remains authoritative when it exists. An actual HTTP 429 obeys Spotify's `Retry-After` across restarts. A structured `QUOTA_EXCEEDED` additionally keeps automatic Connect polling at least 60 seconds apart for 24 hours after the retry deadline and pauses automatic speed-up during that period. A manual adaptive reset does not remove this quota recovery period. Spotify's [development quota](https://developer.spotify.com/documentation/web-api/concepts/quota-modes) and [rolling rate limit](https://developer.spotify.com/documentation/web-api/concepts/rate-limits) are separate; no fixed safe request count is promised.

The stored `adaptive_total_429` counts actual Spotify Web API HTTP 429 responses and persists across restarts, including after they leave the rolling 24-hour display. On first upgrade it seeds from all surviving entries in the bounded legacy event list, including older entries that were not trimmed by a newer 429, or one known last response if that list is missing. Earlier history beyond those saved records may still be missing. Cached cooldown checks and manual resets do not increment it. Settings, local status, and the privacy-limited ZIP export show the registered total without credentials or song data.

The default firmware profile stays at 115200 baud. The optional `esp32-024r-spotify-fastserial` profile and local companion config now run at 230400 for the paired runtime experiment described below; esptool flashing remains at 115200. Every 112×112 RGB888 cover is 37,632 bytes. The companion logs `ART_SENT duration_ms` and delayed metadata delivery, and flushes the latest text as soon as a raw frame finishes, before waiting for its acknowledgement.

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

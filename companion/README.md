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

## Download and start the current companion

Download [BongoDeskSpotify-app-v1.2-2026-10-03.exe](../release/BongoDeskSpotify-app-v1.2-2026-10-03.exe) and its [SHA-256 file](../release/BongoDeskSpotify-app-v1.2-2026-10-03.sha256). The EXE hash is `71756E01987D8A84C76DDCF83B76E9C512A7B5B2E09439DB94D10E36109ABF9F`. It is byte-identical to the installed and physically tested companion. This build is unsigned; check the hash before running it.

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

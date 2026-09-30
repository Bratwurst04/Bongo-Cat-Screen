# Windows companion

`BongoDeskSpotify` runs on Windows and sends system, typing, and media state to the ESP32 over serial. The engine runs on the main thread; the tray and settings UI run alongside it. The current [full flash image](../release/BongoDesk-deep-sleep-2026-09-30-full-0x0.bin) matches the companion below. The version from 2026-09-30 adds automatic serial reconnection and resends the current cover on an ESP32 `SYNC_REQUEST`; using that feature requires both the new companion and firmware. A source-run companion restored the UI, time, statistics, same-track artwork, menu, and panel switching after a companion-loss wake test. In a separate Windows sleep/resume test, the screen was dark before resume and the UI returned within roughly one minute according to the user. A later shutdown/power-on test was reported to work, without precise timing or a deep sleep current measurement. The development EXE from the same source was installed locally and confirmed to show the UI, current statistics, artwork, menu, and panel switching. The 2026-09-24 panel menu release remains available separately.

## Download and start the current companion

Download [BongoDeskSpotify-deep-sleep-2026-09-30.exe](../release/BongoDeskSpotify-deep-sleep-2026-09-30.exe) and its [SHA-256 file](../release/BongoDeskSpotify-deep-sleep-2026-09-30.sha256). The EXE hash is `65D3DAEAFAA4E1CE87A5F9FE52F66923B832E46D8DFBC56917F60EBD6A25128C`. This build is unsigned; check the hash before running it.

Exit any running Bongo Desk companion through its tray icon before double-clicking the new EXE. Only one instance can run at a time. The serial port defaults to `AUTO`; choose the ESP32's COM port in settings if needed. The older `release/BongoDeskSpotify.exe` is a legacy build and is not the current download.

The app keeps settings and OAuth tokens in the current user's `%APPDATA%\BongoCat` folder. To connect your own Spotify account, create a Spotify developer app with redirect URI `http://127.0.0.1:43821/callback`, then run the downloaded EXE from PowerShell in its folder:

```powershell
.\BongoDeskSpotify-deep-sleep-2026-09-30.exe --spotify-client-id YOUR_CLIENT_ID --link-spotify
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
| `spotify_api.py` | Spotify authorization and API requests |
| `config.py` | JSON settings and validation |
| `tray.py`, `gui.py`, `settings.ps1` | Tray and settings UI |
| `windows_integration.py` | Autostart, single-instance lock, foreground app |

The firmware protocol and visual behavior are described in the project root's `00_PROJECT_CONTEXT.md` and `01_CURRENT_STATE.md`. Keep the serial traffic event driven, especially during album-art transfer.

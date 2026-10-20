# Privacy and local data

This describes the development source reviewed on **2026-10-20**. Older released
binaries may differ. Bongo Cat has no project-operated account server, analytics
endpoint or automatic diagnostic upload.

## What the companion processes

| Data | Purpose and destination |
| --- | --- |
| Global keyboard events | Calculate typing speed. Pressed character identifiers stay briefly in memory until release to suppress repeats; the recent typing buffer stores timestamps. The app does not write a text/password log or upload typed contents. WPM is sent to the USB display. |
| Time, CPU/RAM and app/device statistics | Display system information over USB; selected numeric status is also written locally for Settings. |
| Windows media metadata and thumbnails | Show the current track/artist, playback state and cover on the USB display; cache the current artwork in memory. Media controls use Windows or the linked Spotify account. |
| Foreground process/window title, if app animations are enabled | Match local animation rules in memory. This feature is off by default. |
| Spotify credentials and playback data, if linked | Exchange/refresh OAuth tokens with Spotify, read playback/devices/artwork and send play/pause/next/previous actions. The requested scopes are `user-read-playback-state`, `user-read-currently-playing` and `user-modify-playback-state`. |

The browser talks to Spotify during authorization. The companion temporarily
listens on `127.0.0.1:43821/callback`; Spotify API/token requests use HTTPS and
artwork is fetched separately without a Bearer header. Spotify/CDN operators
receive normal connection information and the requested API actions. Their
[privacy policy](https://www.spotify.com/legal/privacy-policy/) governs their
services. Tokens are not sent to the ESP32; display data is sent through USB.

## Files on this PC

The profile is normally `%USERPROFILE%\AppData\Roaming\BongoCat`:

- `config.json` and `config_backup.json`: preferences, port/baud, animation rules
  and the public Spotify Client ID. Unknown existing settings are preserved.
- `spotify_tokens.json`: plaintext access/refresh tokens, expiry and pacing
  metadata. Atomic writes prevent partial replacement; they do **not** encrypt
  credentials. Encrypted Windows storage is pending.
- `spotify_api_budget.json`: local request counts, reservations and retry limits.
- `desktop_status.json`: a local status snapshot used by Settings.

Bounded rotating event logs are stored in `%LOCALAPPDATA%\BongoDesk\logs`.
They record approved event names, counts, timing, state and error classes, rather
than raw HTTP bodies, tokens or track text. The export action creates a local
archive; you decide whether to share it. Review any file before sharing. Copies
and backups you create are retained until you remove them; there is no automatic
cloud deletion or secure erasure.

The separate render-measurement firmware profile keeps anonymous timing counters
and histograms in RAM and sends sparse numeric `DIAG_RENDER` summaries over USB
at 15-second intervals. They describe render gaps/durations and playing/transfer
flags, without text, URLs or credentials. The firmware does not persist or upload
these measurements; a receiving tool on the PC may save its input. Measurement
hooks are disabled in ordinary firmware profiles. The candidate is built only,
and requires separate approval before flashing.

## Stop access and remove local data

1. Disable **Start with Windows** if the app should stay stopped, then choose
   **Exit** from the tray so it stops processing events and cannot rewrite its
   cached credentials.
2. Remove this app's access in your [Spotify account's Apps page](https://www.spotify.com/account/apps/).
3. Remove `spotify_tokens.json` and any private copies/backups if you want to
   remove local authorization. Remove the whole BongoCat profile and local logs
   to reset the remaining local data. Doing so also removes saved settings.

An in-app Spotify disconnect control and encrypted token storage are still
pending. This manual workflow and document do not establish readiness for broad
Spotify distribution; see the [review](docs/product-committee-2026-10-20.md).

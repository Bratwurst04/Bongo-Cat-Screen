# Bongo Cat – Architecture Decisions

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

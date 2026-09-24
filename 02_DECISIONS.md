# Bongo Cat – Architecture Decisions

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

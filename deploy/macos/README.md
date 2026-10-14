# Run on the Mac, share over Tailscale

Spec: [13-share-with-group.md](../../docs/program/backlog/13-share-with-group.md)

## Service
- `deploy/macos/install.sh`: builds the UI, stops `dev.sh` backend, loads 3 launchd agents. Re-run after pulling changes.
  - `com.oscout.backend`: uvicorn on `0.0.0.0:8000`, starts at login, restarts on crash. Log `.run/service.log`.
  - `com.oscout.awake`: `caffeinate` 08:55 to ~15:35, Mon–Fri.
  - `com.oscout.backup`: 16:00 Mon–Fri, live DB → `backups/`, keeps 30 days. Log `.run/backup.log`.
- `install.sh status` · `install.sh uninstall` (then `./dev.sh` works again; same port).
- On the Mac use `http://127.0.0.1:8000` (admin: CONNECT, scan, config). Any other address = view only.

## Mac, once
- Battery → Options: "Prevent automatic sleeping on power adapter when the display is off" on. Keep it plugged in, lid open.
- `sudo pmset repeat wakeorpoweron MTWRF 08:55:00`
- First service start: macOS asks to allow incoming connections for Python → Allow.

## Tailscale, once
- Mac: install Tailscale (tailscale.com/download), sign in.
- Admin console → Machines → the Mac: rename to `oscout`, Disable key expiry.
- Same row → Share → friend's email.
- Friend: install Tailscale, accept the invite, open `http://oscout:8000` (or the Mac's `100.x` IP).

## Don't
- Put Tailscale Serve/Funnel or any proxy in front: every request would look like loopback = admin.

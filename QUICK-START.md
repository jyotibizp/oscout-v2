# Quick start

## Daily
- Open `http://127.0.0.1:8000` (or `localhost:5173`) on the Mac → **CONNECT** to Kite.
- Friends: `http://100.84.60.114:8000` (Tailscale, view only).

## Backend: always-on service (default)
- Runs via launchd (`com.oscout.backend`), port 8000. `./dev.sh start` leaves it alone.
- After backend or UI code changes: `deploy/macos/install.sh` (rebuilds UI, restarts service).
- Status / log: `deploy/macos/install.sh status` · `.run/service.log`

## Backend: dev mode (auto-reload)
- `deploy/macos/install.sh uninstall` then `./dev.sh start`.
- Friends lose access until `deploy/macos/install.sh` again.

## Frontend dev
- `./dev.sh start frontend` → `localhost:5173`, live edits, API proxied to 8000.

More: [README.md](README.md) · [deploy/macos/README.md](deploy/macos/README.md)

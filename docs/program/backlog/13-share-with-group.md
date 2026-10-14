# #13 Share the app with a small group (Mac + Tailscale)

Status: Built (14 Oct 2026), Mac/Tailscale setup pending · Setup: [deploy/macos/README.md](../../../deploy/macos/README.md) · Index: [BACKLOG.md](../../../BACKLOG.md)

**Why:** a few close friends should see the live dashboard and signals. Cheapest reasonable route: keep it on my Mac, share it privately over Tailscale. ₹0/month, no domain, no Kite changes.

**Decisions (13 Oct 2026)**
- Host: my Mac (already runs live on Kite). Alternatives if uptime hurts later: AWS Lightsail Mumbai / DigitalOcean Bangalore (~₹500/mo) + Cloudflare Tunnel + Access (needs a domain); Oracle Cloud Always Free (Mumbai).
- Access: Tailscale (free personal plan). Friends install Tailscale, accept a share of the Mac, open `http://<mac-name>:8000`. Nothing public, so no app login needed.
- Kite: unchanged. Redirect stays `http://127.0.0.1:8000/auth/callback`; I click CONNECT on the Mac itself each morning (connecting from my phone is lost; accepted). Kite has no API to change the redirect URL.
- Friends are **viewers**: they never connect Kite, change config, run scans or toggle auto-scan. Admin = requests from the Mac itself (loopback).
- Compliance (inferred, not legal advice): Kite Connect is for personal use, so share signals, not raw Kite market data screens beyond what the dashboard needs; label the app "educational, not investment advice" (SEBI RA rules on sharing buy/sell calls).

**Scope**
1. **One origin.** Backend serves the built frontend: `npm run build`, mount `frontend/dist` with `StaticFiles` + SPA fallback (non-`/api`, non-`/auth`, non-`/health` paths return `index.html`). Frontend API base becomes relative (`VITE_API_BASE_URL` empty → `""`), today it defaults to `http://localhost:8000`, which would point friends' browsers at their own machine. `FRONTEND_URL` for the Kite callback redirect → `http://127.0.0.1:8000/`.
2. **Viewer guard.** Middleware: `POST/PUT/PATCH/DELETE` under `/api`, `GET /api/system/connect` and `/auth/callback` + `/api/system/callback` are allowed only when the client IP is loopback (or in `ADMIN_IPS`, comma list, optional). Others get 403 `{"detail":"read-only viewer"}`. Mutating routes today: `POST /api/scans/run`, `PUT /api/config`, `POST /api/config/reset`, `POST /api/system/autoscan`.
3. **Viewer UI.** `GET /api/system/whoami` → `{role: "admin"|"viewer"}`. Viewer hides CONNECT, Run scan, auto-scan toggle, config edit/reset; shows a small "View only" badge. Footer line: "Educational tool, not investment advice."
4. **Run as a service (no `--reload`).** launchd agents in `deploy/macos/` (`com.oscout.backend.plist`), `RunAtLoad` + `KeepAlive`, uvicorn `--host 0.0.0.0 --port 8000` from `backend/.venv`, logs to `.run/`. `deploy/macos/install.sh` builds the frontend, installs/reloads the agent. `dev.sh` stays for development (stop the agent first; same port).
5. **Keep the Mac awake in market hours.** Document: on power adapter, Battery → Options → "Prevent automatic sleeping when the display is off"; lid open (or external display); `sudo pmset repeat wakeorpoweron MTWRF 08:55:00`. Optionally a launchd job running `caffeinate -dims -t 24000` at 08:55 Mon–Fri.
6. **Tailscale setup (manual, documented in `deploy/macos/README.md`).** Install Tailscale on the Mac, set machine name (e.g. `oscout`), disable key expiry for it, share the machine to each friend's email (Machines → Share). Friend installs Tailscale, accepts, bookmarks `http://oscout:8000` (or the 100.x IP). macOS firewall: allow incoming for the python/uvicorn binary.
7. **Nightly backup.** launchd job 16:00 Mon–Fri: `sqlite3 oscout_v2_live.db ".backup backups/oscout_v2_$(date +%F).db"`, keep 30 days (backups/ gitignored).

**Out of scope:** public internet URL, own domain, app-level user accounts, phone-side Kite CONNECT, notifications to friends (Phase 4), cloud VPS (revisit if missed scans pile up).

**Acceptance**
- From another Tailscale device: dashboard loads at `http://oscout:8000`, live data and chime work; CONNECT/Run scan/auto-scan/config controls are hidden; a direct `curl -X POST .../api/scans/run` returns 403.
- On the Mac at `http://127.0.0.1:8000`: everything works as today, including CONNECT → Kite → callback → back to the dashboard.
- Reboot the Mac: backend comes back by itself and auto-scan resumes in market hours.
- Backup file appears after 16:00.
- pytest: guard allows loopback writes, blocks non-loopback writes and `/system/connect`, allows non-loopback GETs; SPA fallback serves `index.html`. vitest: viewer role hides admin controls. Existing tests stay green.

**Risks:** Mac sleep, power or Wi-Fi drop, or a macOS update during 09:15–15:30 means missed scans (scan gaps page #2 can backfill). Note `request.client.host` must be read directly (no proxy in front); don't put Tailscale Serve in front of it, or every request looks like loopback.

**Estimate:** 1 story, ~half a day of code + ~30 min manual Tailscale/Mac setup.

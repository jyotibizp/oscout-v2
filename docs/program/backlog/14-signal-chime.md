# #14 Attention-grabbing signal chime

Status: Done (14 Oct 2026) · fix + reject sound (5 Nov 2026) · Index: [BACKLOG.md](../../../BACKLOG.md)

**Why:** the new-signal chime was too quiet and short (<1s) to notice while away from the screen.

**Scope**
- Louder, longer chime: bright 3-note arpeggio repeated 6x (~9s). Rising = new signal, falling = exit.
- Pre-rendered WAVs (`frontend/public/chime-{signal,exit}.wav`, made by `frontend/scripts/gen-chimes.py`) played via `<audio>`: Safari plays these reliably, Web Audio oscillators it did not.
- Audio unlocked on the first click/key/tap (browser autoplay rule).
- Sound toggle in the header plays the full chime, to test it.

**Out of scope:** OS/phone notifications (Phase 4), per-user sound choice.

**Acceptance**
- New active signal → ~9s rising chime; exit → falling chime; muted → silent. Works in Safari and Chrome, on the Mac and for Tailscale viewers.
- Turning Sound on plays the chime.

**Built:** commits a834c16 → c052d7c. Reaches `127.0.0.1:8000` / friends after `deploy/macos/install.sh`.

**Fix (5 Nov 2026):** chime was silent on live signals. Mac check: build, WAVs, service and signals fine; cause is the browser blocking sound after each page load (incl. CONNECT redirect, vite reload) until a click, and the unlock gave up after one try.
- Unlock retries on every click until sound really plays; amber "Click page to enable sound" pill while blocked; tab title flashes "🔔 SIGNAL ALERT" if a chime was blocked.
- Chime keeps polling when Auto Refresh is off.
- REJECTED breakouts today (ATR, VIX, entry window, signal already open) play a short low "uh-oh" (`chime-reject.wav`, ~2.6s). API: `rejected_today` in `/api/signals/active`.
- Still by design: BANKNIFTY (testing) and late fills don't chime.

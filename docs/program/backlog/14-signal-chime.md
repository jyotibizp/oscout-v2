# #14 Attention-grabbing signal chime

Status: Done (14 Oct 2026) · Index: [BACKLOG.md](../../../BACKLOG.md)

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

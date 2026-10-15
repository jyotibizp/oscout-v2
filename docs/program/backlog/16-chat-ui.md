# #16 Chat-native UI (replaces nav menus)

Status: Groomed (15 Oct 2026) · Index: [BACKLOG.md](../../../BACKLOG.md) · Mockup: [16-chat-ui-mock.html](16-chat-ui-mock.html)

**Why:** 10 pages behind a sidebar; in a live market I want one screen where I ask and the answer appears, not menus to hunt through.

**Shape**
- One screen, three bands, no sidebar:
  - **Top:** today's header (connection, feeds, market, last/next scan, toggles, SCAN NOW). Unchanged.
  - **Live strip:** NIFTY / SENSEX mini-cards (state, gate dots, open trade R). Always visible; tap = "show NIFTY".
  - **Feed:** chat-style thread of my asks and inline answers, newest at bottom; answer cards use the full page width (tables, charts need it).
  - **Composer:** chips row + text box.
- **Chips** (auto-suggested, ≤6, from current state, not AI):
  - Signal open → *Track NIFTY trade*, *Why this signal?*, *Chart NIFTY*.
  - Breakout waiting → *What's pending on SENSEX?*.
  - Market closed → *Today's recap*, *Performance this week*.
  - Always → *Scan now* (admin), *Data health*, *Signal history*.
  - Feed health bad → *Data health* moves first.
- **Answers render existing components inline**, each with a "open full" ↗ to its page:
  - Signal card + pipeline, commentary, tracking (Dashboard / Live Signals).
  - Tables with filters (Signal History, Scan History, Trades), first 10 rows.
  - Performance KPIs + equity chart, analytics.
  - Data health, config (read-only view; editing stays on its page).
  - Chart / Chain tabs (#11, #15) once built.
- **Typed asks:** deterministic intent router in the frontend (keywords + symbol + date words: "nifty", "history yesterday", "trades this week", "why", "health", "config"). Unknown → "Try:" + chips. `/` opens a command list. No LLM.
- **System posts in the feed:** new signal, exit, scan failure, stale feed (same events that ring the chime #14).
- Feed kept per browser (localStorage, last 50 items); answers re-fetch live on render, nothing new stored server-side.
- Pages stay as routes (deep links, "open full", phone fallback); sidebar removed, `/` + chips replace it.
- Viewer role: admin-only chips/commands hidden.

**Fit**
- Frontend only; no new API (uses `client.ts` calls as they are).
- Supersedes [workflow.md](../../../workflow.md) §19 sidebar. §33 "no chatbot / no AI" still holds: rule-based router.
- #12 (AI chat companion) later plugs into the same composer as a fallback for asks the router can't parse. Phase 3 gate applies to that, not to this.
- Not a Phase 1 gate item; schedule after #11 so chart answers exist.

**Out of scope:** LLM answers (#12), voice, multi-turn context ("and SENSEX?" works only via chips), editing config from chat, server-side chat history.

**Acceptance**
- Every current page reachable from a chip or command; no sidebar.
- Chips change with state (signal open / waiting / closed market / bad feed).
- Each answer matches its page's data; ↗ opens the page with same filters.
- Works at phone width (strip scrolls sideways, chips wrap).
- vitest: router maps sample asks to intents; chips per state; existing tests green.

**Estimate:** 2 stories, ~2 days (shell + router + chips; inline answer wrappers).

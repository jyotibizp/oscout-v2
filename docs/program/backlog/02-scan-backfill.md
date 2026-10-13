# #2 Scan gaps page (user-driven backfill)

Status: Groomed (13 Oct 2026) · Index: [BACKLOG.md](../../../BACKLOG.md)

**Why:** a glitch (app down, laptop asleep, feed error, Kite token expired) leaves 5m candles unscanned. Signals that would have fired are missing, so live performance tracking is incomplete and can't be compared with the replay. I want to see the gaps and decide myself which to fill; nothing fills automatically.

**What exists:** candles already catch up (`sync_5m` fetches from the last stored candle), and open signals already catch up (`update_open_signals` walks every unseen candle, so a missed exit is still found). What is lost is the **scan** of the missed candles: new breakouts, confirmations, signals and their `scan_results` rows. `run_scan(now=…, ingest=False)` can already scan a past candle as of that candle (`tools/backfill.py` does it into a separate DB).

**Scope**
- **Gaps page** (`/gaps`, linked from the header): date range picker (default last 5 trading days).
  - **Total missing:** candles missing across the range, and per day.
  - **Blocks:** each run of consecutive missing candles as one row: date, from–to (IST), number of candles, and a type, **Latest** (no scans after it: full fill) or **Interior** (later scans exist: record-only fill), plus whether the candle data is present.
  - **Fill selected:** checkbox per block, "Fill selected" button, confirmation listing what will happen. Progress and result per block (scans written, signals found).
- **Gap detection:** expected = every completed 5m candle of each session (09:15 → 15:25, or the latest completed today); covered = candles with a `scan_runs` row of trigger AUTO or BACKFILL. Missing = expected − covered, grouped into blocks.
- **Fill:** ingest once, then `run_scan(trigger="BACKFILL", now=candle + 5m + delay, ingest=False)` for each candle of the block **in time order**.
  - **Latest block:** full fill. The lifecycle sees the candles in the same order as if nothing had broken, so signals, rejections and expiries match the replay.
  - **Interior block:** the lifecycle has already moved past it, so replaying would change history out of order. Fill **record-only**: write `scan_runs` / `scan_results` (note "late fill, lifecycle not replayed") and don't touch setups, events or trades. Exits are already covered by `update_open_signals`.
  - Blocks whose candles the provider can't return stay listed as "no data" and can't be selected.
- **Dedupe:** BACKFILL scans take the same `AUTO:{candle}` dedupe key, so a candle is scanned at most once; filling twice is a no-op.
- **Late signals:** a backfilled signal is kept for performance tracking (`signal_ts` = its candle, `detected_at` = when it was actually found). It shows a "late" badge, doesn't chime, and the performance view gets an "excluding late" toggle.
- **API:** `GET /api/scans/gaps?from=&to=` (totals + blocks), `POST /api/scans/gaps/fill` with the selected blocks. Fill runs one at a time; a second request while one runs returns busy.

**Out of scope:** automatic backfill (on start or before each AUTO scan), re-scanning candles scanned under a different config (the replay's job), option premium backfill (comes with Greeks #1).

**Acceptance**
- Stop the scanner for 30 minutes mid-session: the page shows one Latest block of 6 candles; filling it writes 6 BACKFILL scans in order, and the setups / signals / trades equal `tools/backfill.py` over the same day.
- An Interior block fills record-only: `scan_results` appear, `signal_setups` / `signal_events` / `trades` unchanged.
- No candle gets two AUTO/BACKFILL scans; no backfill scan sees a candle later than its own (no look-ahead).
- Page works on desktop and phone width; late signals carry the badge and no chime.
- pytest: gap detection, latest vs interior fill, dedupe; vitest: page renders blocks and fills a selection; existing tests stay green.

**Estimate:** 1 story, ~1 day (gap detection + fill API ~½ day, page + late badge ~½ day). `scan_runs.trigger` (String(8)) already fits "BACKFILL"; no migration needed (late is derived from the scan trigger).

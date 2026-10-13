# #2 Backfill missed scans

Status: Groomed (13 Oct 2026) · Index: [BACKLOG.md](../../../BACKLOG.md)

**Why:** a glitch (app down, laptop asleep, feed error, Kite token expired) leaves 5m candles unscanned. Signals that would have fired are missing, so live performance tracking is incomplete and can't be compared with the replay.

**What exists:** candles already catch up (`sync_5m` fetches from the last stored candle), and open signals already catch up (`update_open_signals` walks every unseen candle, so a missed exit is still found). What is lost is the **scan** of the missed candles: new breakouts, confirmations and signals, and their `scan_results` rows. `run_scan(now=…, ingest=False)` can already scan a past candle as of that candle (`tools/backfill.py` does it into a separate DB).

**Scope**
- **Gap detection:** expected = every completed 5m candle of the session (09:15 → latest completed); covered = candles with a `scan_runs` row of trigger AUTO or BACKFILL. Missing = expected − covered.
- **Trailing gap (the fix):** missing candles *after* the last scanned candle. Before each AUTO scan, and once at app start, the scheduler ingests once and then runs `run_scan(trigger="BACKFILL", now=candle + 5m + delay, ingest=False)` for each missing candle **in time order**, then the normal AUTO scan. The lifecycle sees the candles in the same order as if nothing had broken, so signals, rejections and expiries match the replay.
- **Interior gap** (a hole with later scans already stored, e.g. one candle errored): the lifecycle has moved past it, so replaying it would change history out of order. Fill it **observe-only**: write the `scan_runs` / `scan_results` rows (trigger BACKFILL, note "late fill, lifecycle not replayed") and do not touch setups, events or trades. Exits are already covered by `update_open_signals`.
- **Dedupe:** BACKFILL scans take the same `AUTO:{candle}` dedupe key, so a candle is scanned at most once whichever path gets there first.
- **Late signals:** a backfilled signal is kept for performance tracking (`signal_ts` = its candle, `detected_at` = when it was actually found). The dashboard shows it with a "late" badge and does **not** chime; it counts in stats, with an "excluding late" toggle on the performance view.
- **Previous days:** CLI `python -m app.tools.backfill --live --date YYYY-MM-DD` fills a past session in the live DB (trailing-gap rule: only if no later scans exist; otherwise observe-only). Needs today's Kite token.
- **Visibility:** `GET /api/scans/gaps?date=` lists missing candles; the header health shows "N candles backfilled today" and a SystemEvent per fill run.

**Out of scope:** re-scanning candles that were scanned with a different config (that's the replay's job), filling gaps where the provider has no candles (data gap stays visible as missing), option premium backfill (comes with Greeks #1).

**Acceptance**
- Stop the scanner for 30 minutes mid-session, restart: the 6 missing candles get BACKFILL scans in order before the next AUTO scan, and the setups / signals / trades equal those from `tools/backfill.py` over the same day.
- An interior gap is filled observe-only: `scan_results` appear, `signal_setups` / `signal_events` / `trades` unchanged.
- No candle has two AUTO/BACKFILL scans; no backfill scan sees a candle later than its own (no look-ahead).
- Late signals carry the badge and no chime.
- pytest: trailing gap, interior gap, dedupe and mock-provider end-to-end; existing tests stay green.

**Estimate:** 1 story, ~1 day (backend gap fill + scheduler hook ~½ day, endpoint / CLI / late badge ~½ day). `scan_runs.trigger` (String(8)) already fits "BACKFILL"; no migration needed unless a `late` flag is added to `signal_setups` (it can be derived from `scan_runs.trigger` instead).

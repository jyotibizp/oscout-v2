# #23 Replay fill for scan gaps

Status: Built (2 Nov 2026) · Index: [BACKLOG.md](../../../BACKLOG.md) · Follows [#2](02-scan-backfill.md)

**Why:** Interior fills were record-only, so qualified setups in gaps (31 breakouts, 8 Sep–30 Oct) never became trades and Performance missed them.

**Rules (agreed 2 Nov)**
- Append-only: no live setup, event, trade or old scan row is edited or deleted.
- Interior fill = replay: a QUALIFIED candle → new setup + trade, tagged LATE (`LATE_REPLAY` event), walked to its own exit over stored candles.
- One trade per index: if any trade (live or late) was open at that candle → setup written as REJECTED.
- Breakout already in history (live or replayed) → skipped.
- Never cut: a late trade runs to its natural exit even if a live trade starts; overlaps flagged (`overlap_setup_ids`).
- Never blocks live: late open trades are ignored by the live entry check and the "active" scan state.
- Latest block: unchanged (full fill).

**Catch-up:** Scan gaps page shows "Replay filled blocks (N)" for record-only fills from before #23. It re-evaluates each breakout as of its candle with the active config and replays it. If it doesn't qualify again, it's skipped. Idempotent. Old rows show LATE TRADE / LATE · REJECTED in Scan History.

**API:** `GET /api/scans/gaps` → `replay_pending`; `POST /api/scans/gaps/replay` (admin); fill result mode `REPLAY` with `signals`, `blocked`.

**Acceptance**
- Interior fill over an afternoon = same trades as an unbroken day; existing setups unchanged (pytest).
- Open trade at the candle → REJECTED; open late trade doesn't block live (pytest).
- Catch-up replays once; scan_results unchanged (pytest). vitest: button + LATE TRADE badge.
- On the Mac: replayed NIFTY+SENSEX from 8 Sep vs research replay (41 trades, +0.172R).

**Load history (2 Nov, pradeep chose UI button)**
- Scan gaps: "Candles stored from X. Load older history from [date]" (admin, ≤ 400 days back). `POST /api/market/history {from}`.
- Fetches 5m candles before the first stored one (all indexes + VIX), builds 15m, recomputes indicators from the new start (derived cache; scan results keep their values). Candles only added.
- Loaded days then show as Interior gaps: fill → replay → LATE trades. Fill a week or two at a time (each candle is one scan).

# #19 BANKNIFTY as a third index

Status: Built, in Testing (2 Nov 2026); backtest failed 2025, stays in Testing · Index: [BACKLOG.md](../../../BACKLOG.md)

**Why:** BANKNIFTY moves more than NIFTY; same ADX setup, one more chance per day.

**Scope**
- Instrument: `NSE:NIFTY BANK`, Kite token 260105. One entry in `market/symbols.py`; engine, scanner, health, backfill pick it up.
- Mock provider: BANKNIFTY base price so cloud/dev runs work.
- UI: third index card, commentary column, Symbol filters (Scans, Signals, Performance).
- Replay/backfill: `--cost BANKNIFTY=<pts>`.
- Options (#15 chain): BANKNIFTY has monthly expiry only (NSE dropped weeklies Nov 2024), so the chain shows the current monthly.

**Agreed (2 Nov 2026)**
1. Go-live: scan and record from day one, card tagged "Testing", no chime, until the backtest passes.
2. Cost per trade: 2 pts (NIFTY 1, SENSEX 3).
3. Strategy config: shared with NIFTY/SENSEX (one config, no per-index overrides).
4. Backtest pass: positive avg R after costs in 2025 AND 2026, real Kite data, run on the Mac via `app.tools.backfill`/`replay`.
5. Dashboard: 3 cards in one row on wide screens, stacked on narrow.

**Built:** `market/symbols.py` entry, `TESTING_SYMBOLS=BANKNIFTY` in settings (empty it in `.env` to go live), `GET /api/market/symbols`, card TESTING tag, chime skips testing indexes, filters from the API, 3-col dashboard at 2xl.
- First sync on the Mac backfills BANKNIFTY history (`INITIAL_BACKFILL_DAYS`).

**Backtest (2 Nov 2026):** FAIL. Live config v1.0.2, Kite 5m data from Dec 2024, 2 pts cost, `app.tools.replay`.
| Year | Trades | Win % | Avg R (net) | Net R | Max DD |
|---|---|---|---|---|---|
| 2025 | 129 | 64.3 | -0.018 | -2.3 | -9.5 |
| 2026 YTD | 88 | 73.9 | +0.099 | +8.7 | -3.0 |
- 2025 is negative before costs too (-0.006R); cost is ~0.012R/trade.
- Decision (2 Nov 2026): keep scanning in Testing; re-run the backtest later before removing the tag.

**Out of scope:** per-index strategy settings, FINNIFTY/MIDCPNIFTY, BANKNIFTY options selection (#1).

**Acceptance**
- BANKNIFTY scans every 5 min beside NIFTY/SENSEX; card, commentary, filters, health show it.
- Backtest 2025 + 2026 results in a README; "Testing" tag removed only if it passes.
- pytest/vitest green.

**Estimate:** ~half a day + backtest run on the Mac.

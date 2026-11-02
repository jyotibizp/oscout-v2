# #19 BANKNIFTY as a third index

Status: Groomed (2 Nov 2026), open choices below · Index: [BACKLOG.md](../../../BACKLOG.md)

**Why:** BANKNIFTY moves more than NIFTY; same ADX setup, one more chance per day.

**Scope**
- Instrument: `NSE:NIFTY BANK`, Kite token 260105. One entry in `market/symbols.py`; engine, scanner, health, backfill pick it up.
- Mock provider: BANKNIFTY base price so cloud/dev runs work.
- UI: third index card, commentary column, Symbol filters (Scans, Signals, Performance).
- Replay/backfill: `--cost BANKNIFTY=<pts>`.
- Options (#15 chain): BANKNIFTY has monthly expiry only (NSE dropped weeklies Nov 2024), so the chain shows the current monthly.

**Open choices (proposed)**
1. Go-live: scan and record from day one, card tagged "Testing", no chime, until the backtest passes.
2. Cost per trade: 2 pts (NIFTY 1, SENSEX 3).
3. Strategy config: shared with NIFTY/SENSEX (one config, no per-index overrides).
4. Backtest pass: positive avg R after costs in 2025 AND 2026, real Kite data, run on the Mac via `app.tools.backfill`/`replay`.
5. Dashboard: 3 cards in one row on wide screens, stacked on narrow.

**Out of scope:** per-index strategy settings, FINNIFTY/MIDCPNIFTY, BANKNIFTY options selection (#1).

**Acceptance**
- BANKNIFTY scans every 5 min beside NIFTY/SENSEX; card, commentary, filters, health show it.
- Backtest 2025 + 2026 results in a README; "Testing" tag removed only if it passes.
- pytest/vitest green.

**Estimate:** ~half a day + backtest run on the Mac.

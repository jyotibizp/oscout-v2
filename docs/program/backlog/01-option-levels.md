# #1 Option entry, stop and target per signal (0.70 delta)

Status: Groomed (2 Nov 2026), ready, next to build · Index: [BACKLOG.md](../../../BACKLOG.md)

**Why:** R is measured on index points today. The trade is an option, so I need entry / stop / target on the option premium and the real option R.

**Scope**
- Every signal (CALL → CE, PUT → PE): pick the strike nearest 0.70 delta from the chain (#15 pricing).
- Store per signal: strike, expiry, delta, IV, premium entry, premium stop, premium target.
- At exit: premium exit, option P&L (points, ₹ per lot), option R.
- Show on the signal card, Trades and Signal History; Performance gets an "Option R" view next to index R.
- Live signals use real chain LTP at entry; late / backfilled signals are modelled (Black-Scholes) and marked MODELLED.

**Out of scope:** placing orders, position sizing (#5), multi-leg.

**Agreed (2 Nov 2026)**
1. Expiry: current weekly; on expiry day roll to the next weekly (BANKNIFTY: monthly).
2. Premium stop / target: Black-Scholes re-price at the index stop / target (entry IV, time left). Recorded exit = real premium when the index exit fires.
3. Exits stay on the index (stop / target / ADX exit); premium levels don't trigger exits.
4. Costs per trade in premium points: NIFTY 1, SENSEX 3, BANKNIFTY 2 (one figure per trade, simple for now).
5. Past / late / gap-filled signals: modelled (Black-Scholes, IV from India VIX), marked MODELLED.

**Build notes (next session)**
- New table `option_legs` (one per setup): option, strike, expiry, source LIVE|MODELLED, iv, delta, entry / stop / target / exit premium, exit_source, cost, pnl, option R. Migration 0002; SQLite gets it via create_all.
- Option R = (exit − entry − cost) / (entry − stop premium).
- Live entry: real-time AUTO/MANUAL scan → chain (#15 build) strike nearest 0.70 delta, LTP. Needs `option_chain(..., min_expiry)` for the expiry-day roll.
- Live exit: chain LTP for that strike / expiry at the exit scan; else modelled.
- One sync step at the end of each scan: open legs for signals without one, close legs of exited signals. Never fails a scan. Covers live, late, replayed and history.
- Modelled expiry rule: NIFTY Tue, SENSEX Thu weekly, BANKNIFTY last Tue monthly (holiday shifts ignored).
- UI: card + Signal History show option, strike, Δ, premium E / SL / T; Trades: option P&L and R; Performance: Option R stats beside index R.

**Acceptance**
- Each new signal stores strike / delta / premium entry, stop, target; delta within ±0.05 of 0.70 when the chain allows.
- Closed trades show option R; Performance can switch index R / option R.
- pytest: strike pick, premium levels, option R; vitest: card + trades show premium levels.

**Estimate:** ~1 day.

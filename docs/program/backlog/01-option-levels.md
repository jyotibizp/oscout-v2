# #1 Option entry, stop and target per signal (0.70 delta)

Status: Groomed (2 Nov 2026), next to build · Index: [BACKLOG.md](../../../BACKLOG.md)

**Why:** R is measured on index points today. The trade is an option, so I need entry / stop / target on the option premium and the real option R.

**Scope**
- Every signal (CALL → CE, PUT → PE): pick the strike nearest 0.70 delta from the chain (#15 pricing).
- Store per signal: strike, expiry, delta, IV, premium entry, premium stop, premium target.
- At exit: premium exit, option P&L (points, ₹ per lot), option R.
- Show on the signal card, Trades and Signal History; Performance gets an "Option R" view next to index R.
- Live signals use real chain LTP at entry; late / backfilled signals are modelled (Black-Scholes) and marked MODELLED.

**Out of scope:** placing orders, position sizing (#5), multi-leg.

**Open questions (need your answers before build)**
1. Expiry: current weekly; switch to next weekly on expiry day (or < 1 day left)?
2. Stop / target premium: (a) re-price with Black-Scholes at the index stop / target (same IV, time left), (b) entry ± delta × index points, (c) keep index levels and just record the real premium when the index hits them. My pick: (a) for levels shown, (c) for the recorded exit.
3. Exit trigger stays on the index (stop / target / ADX exit), or should premium levels trigger exits?
4. Option costs per trade (brokerage + slippage, per lot)?
5. Past signals: options history for expired contracts isn't on Kite, so modelled with IV from VIX. OK?

**Acceptance**
- Each new signal stores strike / delta / premium entry, stop, target; delta within ±0.05 of 0.70 when the chain allows.
- Closed trades show option R; Performance can switch index R / option R.
- pytest: strike pick, premium levels, option R; vitest: card + trades show premium levels.

**Estimate:** ~1 day after the questions are answered.

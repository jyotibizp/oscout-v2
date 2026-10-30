# #21 Stuck-position exit playbook

Status: Brainstorm (30 Oct 2026) · Index: [BACKLOG.md](../../../BACKLOG.md)

**Why:** a position stuck in loss tempts averaging down. Instead: exit, and win the loss back by trading the reverse side, which often moves more smoothly than the stuck trade.

**Idea (mine)**
- Don't average a losing position.
- Exit when it is "stuck" (not moving my way).
- Take the reverse side (CE stuck → PE, or the other way) to cover the loss.

**Evidence so far (28 Oct 2026, real data, 2025 + 2026)**
- Reversing failed 5m P2 signals after the stop made money both years: +0.14R (2025) / +0.24R (2026), charges only.
- Fading failed P2 breakouts at the 20-session range edge: +29.6R / +18.5R vs baseline, holds with slippage.
- 15m reverse after stop: +0.30R / -0.26R, not reliable.
- Generic level-break reversals (not tied to our own failed trade) lost both years.
- Sources: project files `backtests/2026-10-28-false-breakout/`, `backtests/2026-10-28-adx-peak-and-swing-range/`; related [#20](20-breakout-reversal-regime.md).

**Open questions (for me to answer before any test)**
- "Stuck": stop hit, time in trade with no progress, loss size, or a chart cue?
- Exit trigger: same as stuck, or a separate rule?
- Reverse entry: immediately on exit, or wait for a confirm candle / level?
- Reverse stop and target: original entry as stop? Target = recover the loss only, or 1R+?
- Size of the reverse trade: same lots, or sized to recover the loss? Cap?
- One reverse try per trade/day, or more?
- Which systems: 5m P2 only, 15m too, manual trades?
- Cut-off time for a reverse entry?
- Alert only ("consider reverse") or a tracked signal with its own lifecycle?

**Next**
- I answer the questions above; agree rules before any test.
- Test exactly as written on 2025 and 2026 separately, costs NIFTY 1 / SENSEX 3 pts + slippage.
- Groom what to build only after that.

**Estimate:** after rules and tests.

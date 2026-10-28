# #20 Breakout vs reversal regime

Status: Brainstorm (28 Oct 2026) · Index: [BACKLOG.md](../../../BACKLOG.md)

**Why:** some days breakouts run (trade with them, ADX works); other days breakouts fail and reverse (trade the reversal). Detect which day it is and switch.

**Idea (mine)**
- ADX swings big (high peaks, big peak−trough range) → trade breakouts (ADX P2).
- ADX range falls below a cutoff ("spring getting smaller") → trade reversals of breakouts.
- Reversal entry not immediate: wait for the breakout to peak and settle, then enter against it.
- After a multi-day run, breakouts with the run fail more often.

**Next**
- I write the exact rules (detector, levels, entry, stop, target).
- Test exactly as written, on real 2025 and 2026 data separately, costs NIFTY 1 / SENSEX 3 pts + slippage.
- Conclude only after thorough testing; then groom what to implement.

**Tested 28 Oct 2026 (Claude's rule guesses, not mine)**
- 72-candle ADX max/min ratio: no link to wins (P2 entries already start from low ADX).
- ADX peak height / swing size: true on the chart, no link to P2 failures.
- Regime filter: P2 only when ADX swings > 25 beat P2 always both years (+0.04 / +0.26R vs +0.01 / +0.19R); weak in 2025 after slippage.
- Generic level-break reversals (day H/L, prior-day H/L, opening range): lost in both years.
- Fades of failed P2 signals held both years: reverse after stop (+0.14 / +0.24R); fade on failure at 20-session range edge (+29.6 / +18.5R vs baseline).
- Results: project files `backtests/2026-10-28-*`; scripts and reports on Mac `oscout/backend/backtest_data/`.

**Estimate:** after rules and tests.

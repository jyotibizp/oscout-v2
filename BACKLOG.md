# Backlog

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | Greeks integration | Planned (10 Oct 2026) | Map each CE/PE signal to an option: strike by delta, premium stop/target, theta over the hold, IV flag. |
| 2 | feature to backfill scans (if missed due to any glitch) | Planned (11 Oct 2026) | This make the system robust for performance tracking |
| 3 | Breakout pre-alert | Backlog | Mid-candle "breakout forming" heads-up when the forming 5m candle would meet the breakout rule; the real signal still waits for the candle close. |
| 4 | Leading indicator: Bollinger squeeze | Backlog | Bollinger Bands inside Keltner Channels flags compression before ADX drops. Feeds the pre-alert (#3); keep only if the replay shows a gain. |
| 5 | Leading indicator: range contraction | Backlog | NR7, inside bars, falling ATR: price-only compression hints for the pre-alert (#3). |
| 6 | Leading indicator: direction hints | Backlog | 5m DI crossover, RSI 50 cross, MACD histogram turn: early CE/PE side for the pre-alert (#3). |
| 7 | Leading indicator: option-chain data | Backlog | OI build-up by strike and PCR. Needs option-chain snapshots (Phase 2). |
| 8 | Daily ATR "day range used" warning | Backlog | Show today's range so far as % of the 14-day daily ATR beside the 5m ATR warning (card + commentary); warning only. Decide on a blocking rule once there is more data (60-day backfill: only 3 of 47 signals came above 80%). |
| 9 | Trade journal on each signal | Backlog | Record my decision per signal: taken / skipped, actual entry and exit, reason. Compare discretionary results with the system's after a few weeks (feeds Phase 3 shadow tracking). |
| 10 | Trailing stop | Built, off (13 Oct 2026) | `exit.breakeven_at_r`, `exit.trail_after_r`, `exit.trail_atr_multiple` (0 = off). Replay Jan 2025–Oct 2026, 376 trades, costs NIFTY 1 / SENSEX 3 pts: baseline +0.014R avg; breakeven at 1R and trail 2×ATR after 1R/1.5R ≈ same (±0.001R); breakeven at 0.5R +0.006R; trail 1.5×ATR after 1R +0.006R. 1R = 3×ATR, so the ADX exit closes most trades before a trail engages. Keep off. |
| 11 | Chart tab on each index card | Groomed (13 Oct 2026) | Signal / Chart tabs per card, maximize to full screen. Port v1 `CandleChart.tsx` (lightweight-charts). Details below. |

## #11 Chart tab on each index card

**Why:** the card tells me the state but not the picture; I want to see price, the breakout and the trade levels without leaving the dashboard.

**Scope**
- Each NIFTY / SENSEX card gets two tabs: **Signal** (today's card, default) and **Chart**. Tab choice remembered per browser.
- **Maximize** button on the Chart tab opens a full-screen overlay (Esc / ✕ closes); same chart, more history.
- Chart (5m, port of v1 `oscout/frontend/src/components/CandleChart.tsx`, lightweight-charts 4.2.0):
  - Candles, IST time axis, scroll and zoom, synced time scale across panes.
  - Lower pane: ADX, +DI, −DI with the dashed compression level (as the sparkline shows today).
  - Price lines while a signal is open: Entry (dashed), Stop (live, moves with the trailing stop), Target.
  - Markers: breakout candle, signal, exit (with reason).
  - Optional pane: 5m ATR. RSI from v1 is dropped (not part of this strategy).
- Live: refreshes with the scan (15s poll); no extra API calls beyond `/api/market/candles` and `/api/signals/active`.

**Out of scope:** 15m chart, drawing tools, option premium chart (comes with Greeks #1).

**Acceptance**
- Both tabs work on desktop and phone width; maximize fills the screen and restores cleanly.
- Entry / stop / target lines and breakout / signal / exit markers match the signal's lifecycle events.
- Chart theme matches the dark dashboard (v1 was light).
- vitest: tab switch and maximize render; existing tests stay green.

**Estimate:** 1 story, ~half a day. Needs `lightweight-charts` added to v2 `frontend/package.json`.

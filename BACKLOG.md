# Backlog

One row per item; groomed items get a spec in [docs/program/backlog/](docs/program/backlog/).

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | Greeks integration | Planned (10 Oct 2026) | Map each CE/PE signal to an option: strike by delta, premium stop/target, theta over the hold, IV flag. |
| 2 | Scan gaps page (user-driven backfill) | Groomed (13 Oct 2026) | Page lists missing scan blocks (total, per block candle count) and fills the ones I select; latest block full fill, interior blocks record-only; no auto fill. Spec: [02-scan-backfill.md](docs/program/backlog/02-scan-backfill.md). |
| 3 | Breakout pre-alert | Backlog | Mid-candle "breakout forming" heads-up when the forming 5m candle would meet the breakout rule; the real signal still waits for the candle close. |
| 4 | Leading indicator: Bollinger squeeze | Backlog | Bollinger Bands inside Keltner Channels flags compression before ADX drops. Feeds the pre-alert (#3); keep only if the replay shows a gain. |
| 5 | Leading indicator: range contraction | Backlog | NR7, inside bars, falling ATR: price-only compression hints for the pre-alert (#3). |
| 6 | Leading indicator: direction hints | Backlog | 5m DI crossover, RSI 50 cross, MACD histogram turn: early CE/PE side for the pre-alert (#3). |
| 7 | Leading indicator: option-chain data | Backlog | OI build-up by strike and PCR. Needs option-chain snapshots (Phase 2). |
| 8 | Daily ATR "day range used" warning | Backlog | Show today's range so far as % of the 14-day daily ATR beside the 5m ATR warning (card + commentary); warning only. Decide on a blocking rule once there is more data (60-day backfill: only 3 of 47 signals came above 80%). |
| 9 | Trade journal on each signal | Backlog | Record my decision per signal: taken / skipped, actual entry and exit, reason. Compare discretionary results with the system's after a few weeks (feeds Phase 3 shadow tracking). |
| 10 | Trailing stop | Built, off (13 Oct 2026) | `exit.breakeven_at_r`, `exit.trail_after_r`, `exit.trail_atr_multiple` (0 = off). Replay Jan 2025–Oct 2026, 376 trades, costs NIFTY 1 / SENSEX 3 pts: baseline +0.014R avg; breakeven at 1R and trail 2×ATR after 1R/1.5R ≈ same (±0.001R); breakeven at 0.5R +0.006R; trail 1.5×ATR after 1R +0.006R. 1R = 3×ATR, so the ADX exit closes most trades before a trail engages. Keep off. |
| 11 | Chart tab on each index card | Groomed (13 Oct 2026) | Signal / Chart tabs per card, maximize to full screen. Port v1 `CandleChart.tsx` (lightweight-charts) + TradingView widget button in the maximized view. Spec: [11-chart-tab.md](docs/program/backlog/11-chart-tab.md). |
| 12 | Chat companion | Backlog | AI chat companion with which trader can discuss scans, signals and get opinion in live market or otherwise also|
| 13 | Share with a small group (Mac + Tailscale) | Live (14 Oct 2026) | Keep it on my Mac, share privately via Tailscale (₹0, no domain, Kite redirect unchanged). Friends are view-only; backend serves the built frontend; launchd service + keep-awake + nightly DB backup. Spec: [13-share-with-group.md](docs/program/backlog/13-share-with-group.md). Setup: [deploy/macos/README.md](deploy/macos/README.md). |

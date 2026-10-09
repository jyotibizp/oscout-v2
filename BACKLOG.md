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

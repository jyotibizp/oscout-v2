# #11 Chart tab on each index card

Status: Groomed (13 Oct 2026) · Index: [BACKLOG.md](../../../BACKLOG.md)

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
- **TradingView button** in the maximized view: opens TradingView's free Advanced Chart widget for the index (full indicator menu, drawing tools, timeframes) for free exploration. It runs on TradingView's data feed (may be delayed for NSE/BSE without a TV login) and cannot show our lines or markers; our chart stays the source of truth.
- Live: refreshes with the scan (15s poll); no extra API calls beyond `/api/market/candles` and `/api/signals/active`.

**Out of scope:** 15m chart and drawing tools on our chart, option premium chart (comes with Greeks #1), TradingView Charting Library (licensed, needs TradingView approval).

**Acceptance**
- Both tabs work on desktop and phone width; maximize fills the screen and restores cleanly.
- Entry / stop / target lines and breakout / signal / exit markers match the signal's lifecycle events.
- Chart theme matches the dark dashboard (v1 was light).
- vitest: tab switch and maximize render; existing tests stay green.

**Estimate:** 1 story, ~half a day. Needs `lightweight-charts` added to v2 `frontend/package.json`.

# Build a Fresh ADX Signal Generator Micro-SaaS

Build a **clean, production-quality micro-SaaS web application** for generating **NIFTY and SENSEX options-buying signals** using **only one strategy: ADX Compression → ADX Breakout → ADX Exhaustion Exit**.

This is a **fresh implementation**. Do not inherit unnecessary logic, indicators, strategies, screens, or complexity from any previous scanner.

The application should be deliberately simple:

> **One strategy.  
> Three qualification gates.  
> One signal lifecycle.  
> Complete scan history.  
> Complete performance tracking.**

---

# 1. CORE OBJECTIVE

The application continuously scans NIFTY and SENSEX market data and identifies high-quality directional option-buying opportunities based exclusively on **ADX behaviour**.

The strategy lifecycle is:

```text
ADX Compression
      ↓
ADX Breakout Qualification
      ↓
15m ADX Pattern Confirmation
      ↓
ATR Exhaustion Check
      ↓
India VIX Filter
      ↓
SIGNAL GENERATED
      ↓
OPTION BUY
      ↓
ADX Exhaustion
      ↓
EXIT
```

Do NOT introduce RSI, MACD, Bollinger Bands, VWAP, moving averages, price-action strategies, candlestick strategies, OI analysis, Greeks, PCR, or any other trading methodology.

The application is an **ADX-only signal-generation engine**.

---

# 2. MARKET SCOPE

Initially support only:

- NIFTY
- SENSEX

The architecture should allow additional indices later, but do not build them now.

Signal type:

- CALL BUY
- PUT BUY

The application should determine direction from the ADX methodology and underlying market movement.

---

# 3. DATA REQUIREMENTS

The strategy requires historical and recent ADX data from:

### 5-minute candles

Maintain:

- Historical 5m candles
- Recent 5m candles
- Current/latest 5m candle
- ADX
- +DI
- -DI
- ATR
- OHLCV

### 15-minute candles

Maintain:

- Historical 15m candles
- Recent 15m candles
- Current/latest 15m candle
- ADX
- +DI
- -DI
- ATR
- OHLCV

### India VIX

Maintain:

- Current India VIX
- Historical India VIX
- VIX change
- VIX percentage change

Use the existing market-data provider / broker integration where available.

Design the data layer so that the provider can be replaced later without changing the strategy engine.

---

# 4. IMPORTANT DATA INGESTION RULE

Do NOT repeatedly download duplicate candles.

The system must use **incremental candle ingestion**.

For every symbol/timeframe:

1. Identify the latest stored candle timestamp.
2. Fetch only candles after that timestamp.
3. Insert only new candles.
4. Prevent duplicate records using a database uniqueness constraint.
5. Recalculate indicators only where required.
6. Preserve the complete historical dataset.

The database should become the application's permanent market-data store.

---

# 5. STRATEGY ENGINE

Create a dedicated strategy engine.

Keep strategy logic completely separate from:

- UI
- database
- broker/data provider
- scheduler
- authentication

The strategy engine should receive market data and configuration and return a structured result.

Example:

```json
{
  "symbol": "NIFTY",
  "timestamp": "...",
  "signal": "CALL",
  "status": "QUALIFIED",
  "gate1": true,
  "gate2": true,
  "atr_filter": true,
  "vix_filter": true,
  "entry_price": 0,
  "reason": "..."
}
```

---

# 6. GATE 1 — 5M ADX BREAKOUT QUALIFICATION

Gate 1 is the initial setup qualification.

The system must identify:

### A. ADX Compression

Detect periods where ADX remains below a configurable compression threshold.

Configurable parameters:

- ADX compression threshold
- Minimum compression candles
- Maximum compression candles
- ADX breakout threshold
- Breakout lookback
- Minimum ADX increase
- +DI / -DI relationship
- Minimum directional separation

The objective is:

> Find a period where ADX has compressed and then begins expanding with directional strength.

### B. ADX Breakout

A breakout occurs when the configured ADX breakout conditions are satisfied.

The engine should record:

- ADX before breakout
- ADX at breakout
- ADX change
- +DI
- -DI
- Direction
- Breakout candle timestamp
- Breakout candle OHLC

Gate 1 passes only when all configured conditions are satisfied.

---

# 7. GATE 2 — 15M ADX PATTERN CONFIRMATION

After Gate 1 qualifies, validate the higher timeframe using the **15-minute ADX structure**.

The 15m pattern should evaluate the **last configurable number of candles**, with the default being:

> **15 candles**

Make this configurable.

Example:

```text
15m lookback = 15 candles
```

Analyze:

- ADX progression
- ADX slope
- ADX compression → expansion behaviour
- +DI / -DI relationship
- directional consistency
- ADX acceleration/deceleration
- recent ADX high/low
- current ADX position within the pattern

Create a configurable 15m pattern qualification engine.

The UI should clearly explain:

```text
15M PATTERN
✓ Confirmed
or
✕ Failed
```

with the actual reasons.

---

# 8. GATE 2B — ATR EXHAUSTION FILTER

Before generating a signal, check whether the move is already excessively extended.

The purpose is to avoid buying options after the underlying has already made an abnormally large move.

Use ATR-based exhaustion logic.

Configurable parameters:

- ATR period
- ATR timeframe
- Maximum move / ATR multiple
- Exhaustion threshold
- Lookback period

The engine should determine:

```text
ATR STATUS
NORMAL
WARNING
EXHAUSTED
```

If the move is exhausted according to configuration:

> Do NOT generate a fresh entry signal.

Important:

ATR exhaustion is a **filter**, not an entry strategy.

---

# 9. GATE 3 — INDIA VIX FILTER

Use India VIX as a market-condition filter.

Configurable parameters:

- Minimum VIX
- Maximum VIX
- VIX change threshold
- VIX spike threshold
- VIX trend requirement
- Enable/disable VIX filter

The engine should return:

```text
VIX FILTER
✓ PASS
or
✕ FAIL
```

with the actual reason.

Do not make India VIX itself an entry indicator.

It is only a qualification/risk filter.

---

# 10. FINAL SIGNAL LOGIC

A signal should only be generated when:

```text
Gate 1 = PASS
AND
15M Pattern = PASS
AND
ATR Exhaustion = NOT EXHAUSTED
AND
India VIX Filter = PASS
```

Then:

```text
CALL → bullish directional qualification
PUT  → bearish directional qualification
```

No partial signals.

No "maybe" signals.

No signal unless all mandatory gates pass.

---

# 11. SIGNAL STATES

Every scan should have a clear state.

Use:

```text
WATCHING
COMPRESSION
BREAKOUT_DETECTED
WAITING_CONFIRMATION
QUALIFIED
SIGNAL_GENERATED
ACTIVE
EXIT_TRIGGERED
EXPIRED
REJECTED
```

This allows us to understand exactly where every setup is in its lifecycle.

---

# 12. SIGNAL LIFECYCLE

The system must track a setup from beginning to end.

Example:

```text
09:35
ADX Compression detected

09:50
5m ADX breakout detected

10:00
15m pattern confirmation PASS

10:00
ATR filter PASS

10:00
VIX filter PASS

10:00
CALL BUY SIGNAL

10:45
ADX exhaustion detected

10:45
EXIT
```

Every event should be stored.

---

# 13. ADX EXHAUSTION EXIT

The exit methodology must also be ADX-based.

The primary exit condition is:

> ADX exhaustion / loss of directional strength.

Make exit parameters configurable.

Potential configurable conditions:

- ADX decline from peak
- ADX peak-to-current decline %
- ADX slope reversal
- DI crossover
- Minimum ADX decline
- Number of confirming candles

The strategy should not continuously generate new entries while an existing signal is still active unless explicitly allowed by configuration.

---

# 14. CONFIGURATION SYSTEM

Every important strategy parameter must be configurable.

Create a central configuration model.

Example:

```text
5M SETTINGS
ADX Period
Compression Threshold
Compression Candles
Breakout Threshold
ADX Increase
DI Separation
Breakout Lookback

15M SETTINGS
ADX Period
Lookback Candles
Pattern Threshold
ADX Slope
DI Conditions

ATR SETTINGS
ATR Period
ATR Timeframe
Exhaustion Multiple
Lookback

VIX SETTINGS
Minimum VIX
Maximum VIX
VIX Change
VIX Spike

EXIT SETTINGS
ADX Decline %
ADX Peak Lookback
DI Reversal
Confirmation Candles
```

Never hard-code strategy values inside the strategy engine.

---

# 15. SCAN ENGINE

Create a lightweight scan engine.

Support:

### Manual Scan

User clicks:

> SCAN NOW

The system immediately evaluates NIFTY and SENSEX.

### Automatic Scan

Configurable automatic scanning interval.

Default:

```text
Every 5 minutes
```

Allow:

- Enable/Disable Auto Scan
- Scan interval
- Market-hours-only scanning

Do not run scans outside configured market hours.

---

# 16. SCAN HISTORY

Store every scan.

This is extremely important.

For every scan store:

- Scan ID
- Timestamp
- Symbol
- 5m ADX
- 5m +DI
- 5m -DI
- 15m ADX
- 15m +DI
- 15m -DI
- ATR
- ATR status
- India VIX
- Gate 1 result
- Gate 2 result
- ATR filter result
- VIX filter result
- Final result
- Signal direction
- Rejection reason
- Strategy configuration version

Do not overwrite previous scans.

The history should allow us to reconstruct exactly why a signal was or was not generated.

---

# 17. PERFORMANCE TRACKING

Build performance analytics specifically for this strategy.

Track:

### Signal statistics

- Total scans
- Total setups
- Total signals
- CALL signals
- PUT signals
- Qualified signals
- Rejected signals
- Gate-wise rejection rate

### Trading performance

- Total trades
- Winning trades
- Losing trades
- Win rate
- Average gain
- Average loss
- Risk/reward
- Expectancy
- Maximum drawdown
- Profit factor
- Average holding time

### Strategy analytics

Analyze performance by:

- NIFTY vs SENSEX
- CALL vs PUT
- Time of day
- Day of week
- ADX breakout strength
- 15m ADX strength
- ATR state
- VIX regime

Keep analytics focused on the ADX strategy.

---

# 18. DASHBOARD UI

Build a **premium but simple trading dashboard**.

Theme:

> Dark Blue + Grey

Avoid excessive colors, gradients, animations, cards, and visual clutter.

The interface should feel like a professional market terminal.

---

# 19. LEFT SIDEBAR

Create a persistent left navigation sidebar.

Menu:

```text
Dashboard

Signals
  ├─ Live Signals
  └─ Signal History

Scans
  └─ Scan History

Performance
  ├─ Overview
  ├─ Trades
  └─ Analytics

Strategy
  └─ ADX Configuration

Market Data
  └─ Data Health

System
  └─ Settings
```

Keep navigation simple.

---

# 20. TOP HEADER

Create a polished fixed top header.

Include:

### Connection Status

```text
● Connected
```

or

```text
● Disconnected
```

### Data Status

```text
NIFTY 5M ✓
NIFTY 15M ✓
SENSEX 5M ✓
SENSEX 15M ✓
VIX ✓
```

### Controls

- Auto Scan ON/OFF
- Auto Refresh ON/OFF
- Market Status
- Last Scan Time
- Next Scan Time

### Primary buttons

```text
CONNECT
SCAN NOW
```

The SCAN NOW button should be visually prominent.

---

# 21. DASHBOARD

The main dashboard should immediately answer:

> "Is there a trade right now?"

Top section:

```text
NIFTY
ADX Status
Compression
Breakout
15M Confirmation
ATR
VIX
Final Signal
```

and:

```text
SENSEX
ADX Status
Compression
Breakout
15M Confirmation
ATR
VIX
Final Signal
```

Use clear states:

```text
PASS
WAIT
FAILED
EXHAUSTED
SIGNAL
```

---

# 22. SIGNAL CARD

When a signal exists, show a prominent signal card.

Example:

```text
NIFTY

CALL BUY

ADX BREAKOUT CONFIRMED

5M ADX       28.4 ↑
15M ADX      31.2 ↑
ATR          NORMAL
INDIA VIX    14.8
DIRECTION    BULLISH

Gate 1       ✓ PASS
Gate 2       ✓ PASS
ATR Filter   ✓ PASS
VIX Filter   ✓ PASS

SIGNAL TIME  10:15
```

Also show:

> Why this signal was generated.

Avoid black-box signals.

---

# 23. GATE VISUALIZATION

Every setup should expose its qualification pipeline:

```text
GATE 1
5M ADX BREAKOUT
       ✓
       ↓
GATE 2
15M ADX PATTERN
       ✓
       ↓
ATR FILTER
       ✓
       ↓
VIX FILTER
       ✓
       ↓
SIGNAL
CALL BUY
```

If rejected:

```text
GATE 1 ✓
GATE 2 ✓
ATR FILTER ✕
VIX FILTER —
FINAL: NO SIGNAL
```

This should make debugging the strategy extremely easy.

---

# 24. SIGNAL HISTORY UI

Create a searchable/filterable table.

Columns:

```text
Time
Symbol
Direction
5M ADX
15M ADX
ATR
VIX
Gate 1
Gate 2
ATR
VIX
Final Result
Status
```

Filters:

- Date
- Symbol
- CALL / PUT
- Qualified / Rejected
- Active / Closed
- Gate failure
- VIX regime

Clicking a row should open detailed scan information.

---

# 25. PERFORMANCE UI

Create a clean performance dashboard.

Top metrics:

```text
Signals
Win Rate
Profit Factor
Expectancy
Net P&L
Max Drawdown
Avg Holding Time
```

Charts:

- Cumulative P&L
- Win/Loss distribution
- Signals by hour
- NIFTY vs SENSEX
- CALL vs PUT
- Gate rejection funnel

Do not overload the page with charts.

---

# 26. STRATEGY CONFIGURATION UI

Create a dedicated configuration page.

Group settings:

```text
5M ADX
15M ADX
ATR
INDIA VIX
EXIT
SCANNER
```

Each parameter should have:

- Name
- Current value
- Description
- Input
- Default value
- Validation

Include:

```text
SAVE CONFIGURATION
RESET DEFAULTS
```

Every saved configuration must receive a version number.

Example:

```text
ADX Strategy v1.0.3
```

Store the configuration version with every scan and signal.

This is essential for historical backtesting/performance analysis.

---

# 27. DATA HEALTH

Create a lightweight data-health page.

Show:

```text
NIFTY 5M       HEALTHY
NIFTY 15M      HEALTHY
SENSEX 5M      HEALTHY
SENSEX 15M     HEALTHY
INDIA VIX      HEALTHY
```

For each:

- Last candle
- Last update
- Number of stored candles
- Latest timestamp
- Connection status
- Error status

Highlight stale data.

Never generate a signal if required market data is stale or unavailable.

---

# 28. DATABASE DESIGN

Use a proper relational database.

At minimum create tables for:

```text
market_candles
indicator_values
scan_runs
scan_results
signal_setups
signal_events
trades
strategy_configurations
system_events
```

Add appropriate indexes.

Prevent duplicate candles and duplicate scans.

Keep timestamps timezone-aware.

Use:

```text
Asia/Kolkata
```

for market/session display.

Store timestamps consistently in UTC internally if appropriate.

---

# 29. API DESIGN

Keep the backend modular.

Suggested API areas:

```text
/api/market
/api/scans
/api/signals
/api/strategy
/api/performance
/api/config
/api/system
```

Examples:

```text
POST /api/scans/run
GET  /api/scans/latest
GET  /api/scans/history

GET  /api/signals/active
GET  /api/signals/history

GET  /api/performance/summary

GET  /api/config
PUT  /api/config

GET  /api/system/health
```

---

# 30. LOGGING

Create structured application logs.

Log:

- Data ingestion
- Scan execution
- Strategy evaluation
- Gate failures
- Signal creation
- Signal exit
- Connection failures
- Data errors
- Configuration changes

Every signal should be explainable from logs and stored scan data.

---

# 31. ERROR HANDLING

The system must fail safely.

Examples:

If 5m data unavailable:

```text
NO SIGNAL
Reason: 5M DATA STALE
```

If VIX unavailable:

```text
NO SIGNAL
Reason: VIX DATA UNAVAILABLE
```

If duplicate candle received:

```text
Ignore duplicate
```

Never generate a signal using incomplete or stale data.

---

# 32. DESIGN PRINCIPLES

The application must follow these principles:

### SIMPLE

Do not build unnecessary features.

### EXPLAINABLE

Every signal must explain why it exists.

### CONFIGURABLE

Strategy parameters must not be hard-coded.

### AUDITABLE

Every scan and signal must be stored.

### REPRODUCIBLE

Given the same market data + strategy configuration, the same result should be produced.

### MODULAR

Separate:

```text
Data
Indicators
Strategy
Scanner
Signals
Performance
API
UI
```

### FAST

The dashboard should feel instant.

### CLEAN

Avoid UI clutter.

---

# 33. WHAT NOT TO BUILD

Do NOT add:

- RSI
- MACD
- Bollinger Bands
- VWAP
- Supertrend
- Moving-average strategies
- OI strategy
- PCR
- Greeks-based strategy
- News sentiment
- AI prediction
- Machine learning
- Price prediction
- Portfolio management
- Multi-strategy framework
- Social features
- Chatbot
- Complex user-management system

This is intentionally a **single-strategy ADX micro-SaaS**.

---

# 34. TESTING

Create automated tests for:

### Indicator calculations

- ADX
- +DI
- -DI
- ATR

### Gate 1

- Compression detected
- Breakout detected
- False breakout rejected

### Gate 2

- 15m confirmation
- Failed pattern
- Insufficient candles

### ATR

- Normal
- Warning
- Exhausted

### VIX

- Pass
- Fail
- Missing data

### Final signal

- All gates pass → signal
- Any mandatory gate fails → no signal

### Exit

- ADX exhaustion
- DI reversal
- Confirmation logic

### Data ingestion

- Incremental candles
- Duplicate prevention
- Missing candles
- Stale data

---

# 35. DEVELOPMENT APPROACH

Build this in phases.

### Phase 1 — Foundation

- Project setup
- Database
- Market data model
- Configuration model
- Basic API
- Basic UI shell

### Phase 2 — ADX Engine

- ADX
- DI
- ATR
- Gate 1
- Gate 2
- ATR filter
- VIX filter
- Exit engine

### Phase 3 — Scanner

- Manual scan
- Automatic scan
- Incremental data ingestion
- Scan history
- Signal lifecycle

### Phase 4 — Dashboard

- Sidebar
- Header
- Dashboard
- Signal cards
- Gate visualization
- History

### Phase 5 — Performance

- Trade tracking
- Performance metrics
- Analytics
- Charts

### Phase 6 — Hardening

- Error handling
- Logging
- Tests
- Data integrity
- Performance optimization
- Production readiness

---

# 36. IMPORTANT IMPLEMENTATION RULE

Before writing large amounts of code:

1. Inspect the existing project structure.
2. Identify the existing tech stack.
3. Reuse only useful infrastructure.
4. Remove/ignore unrelated strategy logic.
5. Establish the database schema.
6. Establish the strategy configuration model.
7. Establish the ADX strategy engine.
8. Then build the UI around the strategy.

Do not blindly rewrite the entire project if useful infrastructure already exists.

However, the resulting application must behave as a **fresh, clean ADX-only product**.

---

# 37. DEFINITION OF DONE

The application is considered complete when:

- NIFTY and SENSEX data are available.
- 5m and 15m candles are stored incrementally.
- ADX/+DI/-DI/ATR are calculated correctly.
- Gate 1 identifies 5m ADX compression → breakout.
- Gate 2 validates the 15m ADX pattern.
- ATR exhaustion prevents late entries.
- India VIX filters signals.
- Valid setups generate CALL/PUT signals.
- ADX exhaustion can trigger exits.
- Every scan is stored.
- Every signal is stored.
- Every rejection has a reason.
- Configuration is editable.
- Configuration versions are stored.
- Performance is tracked.
- Dashboard clearly shows current market state.
- Manual scanning works.
- Automatic 5-minute scanning works.
- Duplicate candles are prevented.
- Stale data prevents signals.
- Tests cover the strategy engine.
- UI is clean, dark-blue/grey, responsive and production-quality.

---

# FINAL PRODUCT PHILOSOPHY

This should NOT feel like a giant trading platform.

It should feel like a **precision instrument for one strategy**.

The entire product should revolve around:

```text
COMPRESSION
     ↓
BREAKOUT
     ↓
CONFIRMATION
     ↓
FILTER
     ↓
ENTRY
     ↓
EXHAUSTION
     ↓
EXIT
```

Build this as a clean, maintainable micro-SaaS with a strong separation between **market data → ADX strategy engine → signal lifecycle → performance analytics → UI**.

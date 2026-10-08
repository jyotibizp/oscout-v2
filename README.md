# oscout v2 — ADX Signal Generator

A single-strategy micro-SaaS that scans **NIFTY** and **SENSEX** and generates CALL / PUT option-buying signals
from **ADX behaviour only**:

```text
5m ADX compression → 5m ADX breakout (Gate 1) → 15m ADX pattern (Gate 2) → ATR exhaustion filter
→ India VIX filter → SIGNAL → ADX exhaustion exit
```

Every scan, every rejection and every signal is stored with its reasons and the strategy-configuration
version that produced it. The product spec is [`workflow.md`](workflow.md).

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL (SQLite for dev/tests) |
| Market data | Zerodha Kite Connect (`DATA_PROVIDER=kite`) or a deterministic mock market (`mock`) |
| Frontend | React 18, TypeScript, Vite, Tailwind (dark blue / grey terminal theme) |

## Run it

```bash
# backend (http://localhost:8000)
cd backend
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # DATA_PROVIDER=mock works without any broker account
.venv/bin/alembic upgrade head  # PostgreSQL; SQLite tables are created automatically on start
.venv/bin/uvicorn app.main:app --port 8000

# frontend (http://localhost:5173)
cd frontend
npm install
cp .env.example .env            # VITE_API_BASE_URL=http://localhost:8000
npm run dev
```

With `DATA_PROVIDER=kite`, set `KITE_API_KEY` / `KITE_API_SECRET`, point the Kite app's redirect URL at
`http://localhost:8000/api/system/callback`, and press **CONNECT** each morning (Kite sessions expire daily).

### Tests

```bash
cd backend && .venv/bin/python -m pytest -q     # indicators, gates, ATR, VIX, final signal, exit, ingestion, lifecycle, API
cd frontend && npm test && npm run build
```

### Historical replay (research)

Runs the same engine over historical 5m CSVs (`timestamp,open,high,low,close` in IST) and a daily VIX CSV:

```bash
cd backend
.venv/bin/python -m app.tools.replay --csv NIFTY=nifty.csv --csv SENSEX=sensex.csv --vix vix_daily.csv \
  --cost NIFTY=5 --cost SENSEX=17 [--set exit.stop_atr_multiple=2 ...]
```

## Architecture

```text
backend/app
  core/        settings, market clock (UTC storage, IST display), JSON logging
  db/          models (9 tables + broker session), UTC datetime type, sessions
  market/      providers (Kite, Mock), incremental ingestion + 15m aggregation, repository, data health
  indicators/  Wilder ADX / +DI / -DI / ATR as an exact incremental recurrence
  strategy/    config (versioned, validated, UI metadata), engine (gates + exit), config store
  scanner/     scan orchestration, auto-scan scheduler
  signals/     setup / signal lifecycle (events, trades)
  performance/ metrics and analytics
  api/         REST routes (/api/market, scans, signals, config, performance, system)
  tools/       replay (research)
frontend/src
  components/  layout (sidebar + header), pipeline, signal card, charts, drawers
  pages/       Dashboard, Live Signals, Signal History, Scan History, Performance (Overview / Trades /
               Analytics), ADX Configuration, Data Health, Settings
```

### Data rules
- **Incremental only.** For each symbol the latest stored 5m candle is found, only newer *completed* candles are
  fetched, and inserts are idempotent (`UNIQUE(symbol, timeframe, ts)`). Nothing is deleted.
- **15m candles** are built from three stored 5m candles (aligned to 09:15 IST); an incomplete bucket is never built.
- **Indicators** are stored per candle together with the Wilder smoothing state, so each new candle extends the
  series exactly (identical to a full recalculation).
- **Stale or missing data never produces a signal** (`5M DATA STALE`, `VIX DATA UNAVAILABLE`, …).
- Timestamps are timezone-aware, stored in UTC, displayed in Asia/Kolkata. A candle's timestamp is its start.

### Strategy
| Step | Default rule (all editable in *ADX Configuration*) |
|---|---|
| Gate 1 — 5m | ADX ≤ 20 for ≥ 6 candles, then a fresh breakout: ADX closes above its previous-5 average and rises ≥ 0.5; DI gap ≥ 3. +DI leads → CALL, −DI → PUT. Valid for 3 candles. |
| Gate 2 — 15m | Last 15 candles: 15m ADX rising, 15m leading DI agrees, DI consistency ≥ 50 %, 15m ADX ≤ 45. |
| ATR filter | Move from the 12-candle extreme ÷ 5m ATR: ≥ 2.5× WARNING, ≥ 3.5× EXHAUSTED (no entry). |
| VIX filter | 10 ≤ VIX ≤ 30, day change within ±15 %, no spike > +10 %. |
| Entry | 09:30–14:45 IST, one active signal per symbol. Entry = index close of the signal candle. |
| Exit | 2 consecutive falling 5m ADX candles while in profit (ADX exhaustion); safety stop 3× ATR, target 4.5× ATR, max 36 candles, 15:25 session end. DI-reversal and %-from-peak exits are optional. |

Performance is measured on the underlying index move (points, % and R = points ÷ stop distance); option
premiums, Greeks and OI are deliberately out of scope.

> Research note (2025-01 → 2026-10 real NIFTY/SENSEX 5m data, costs included): this ADX setup is roughly
> break-even (about +0.03 R per trade with the defaults). Treat signals as a disciplined framework to test,
> not as a proven edge.

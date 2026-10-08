"""Historical replay of the ADX strategy engine (research tool, not part of the live app).

Runs the SAME engine.evaluate() and engine.evaluate_exit() over historical 5m candles (CSV with columns
timestamp,open,high,low,close in IST) for one configuration, and reports trades measured on the underlying.
India VIX: daily closes (CSV day,close); each day uses the PREVIOUS day's close (no look-ahead).

Usage:
  python -m app.tools.replay --csv NIFTY=path.csv --csv SENSEX=path.csv --vix vix_daily.csv \
      [--set exit.stop_atr_multiple=2] [--from 2025-01-01] [--cost NIFTY=5 --cost SENSEX=17]
"""
import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta

from app.core.clock import IST, as_utc, is_session_last_candle, session_open, to_ist
from app.indicators.wilder import series
from app.strategy.config import StrategyConfig
from app.strategy.engine import Bar, Position, VixSnapshot, evaluate, evaluate_exit


def read_5m(path: str) -> list[dict]:
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            ts = datetime.fromisoformat(r["timestamp"]).replace(tzinfo=IST)
            rows.append({"ts": as_utc(ts), "open": float(r["open"]), "high": float(r["high"]),
                         "low": float(r["low"]), "close": float(r["close"])})
    rows.sort(key=lambda x: x["ts"])
    out, seen = [], set()
    for r in rows:
        if r["ts"] not in seen:
            seen.add(r["ts"]); out.append(r)
    return out


def to_15m(rows: list[dict]) -> list[dict]:
    b = defaultdict(list)
    for r in rows:
        t = to_ist(r["ts"]); o = session_open(t.date())
        b[as_utc(o + ((t - o) // timedelta(minutes=15)) * timedelta(minutes=15))].append(r)
    return [{"ts": k, "open": v[0]["open"], "high": max(x["high"] for x in v), "low": min(x["low"] for x in v),
             "close": v[-1]["close"]} for k, v in sorted(b.items()) if len(v) == 3]


def with_ind(rows, adx_p, atr_p) -> list[Bar]:
    a = series([r["high"] for r in rows], [r["low"] for r in rows], [r["close"] for r in rows], adx_p)
    t = a if atr_p == adx_p else series([r["high"] for r in rows], [r["low"] for r in rows], [r["close"] for r in rows], atr_p)
    return [Bar(r["ts"], r["open"], r["high"], r["low"], r["close"], s.adx, s.pdi, s.mdi, u.atr) for r, s, u in zip(rows, a, t)]


def apply_overrides(cfg: StrategyConfig, sets: list[str]) -> StrategyConfig:
    d = cfg.model_dump()
    for s in sets:
        k, v = s.split("=", 1)
        g, p = k.split(".")
        cur = d[g][p]
        d[g][p] = (v.lower() == "true") if isinstance(cur, bool) else type(cur)(v) if cur is not None else v
    return StrategyConfig.model_validate(d)


def replay(symbol: str, rows: list[dict], vix_daily: dict, cfg: StrategyConfig, start: str, cost: float) -> list[dict]:
    f, q, a = cfg.five_min, cfg.fifteen_min, cfg.atr
    b5 = with_ind(rows, f.adx_period, a.atr_period)
    r15 = to_15m(rows)
    b15 = with_ind(r15, q.adx_period, a.atr_period)
    days = sorted(vix_daily)
    trades, pos, sig, used = [], None, None, set()
    j15 = 0
    W5 = max(f.max_compression_candles + f.breakout_lookback + f.breakout_valid_candles + 40, 300)
    for t in range(60, len(b5)):
        bar = b5[t]
        d = to_ist(bar.ts).date()
        if str(d) < start:
            continue
        if pos is not None:
            pos, ex = evaluate_exit(pos, [bar], cfg, lambda ts: is_session_last_candle(ts, "5m"))
            if ex:
                pts = (ex.price - sig["entry"]) * pos.direction
                trades.append({**sig, "exit_ts": ex.ts.isoformat(), "exit": ex.price, "reason": ex.reason,
                               "pts": pts, "R": (pts - cost) / sig["risk"] if sig["risk"] else None,
                               "held": pos.held})
                pos = None
        end5 = bar.ts + timedelta(minutes=5)
        while j15 < len(b15) and b15[j15].ts + timedelta(minutes=15) <= end5:
            j15 += 1
        prev = [x for x in days if x < str(d)]
        vv = VixSnapshot(vix_daily[prev[-1]], vix_daily[prev[-2]] if len(prev) > 1 else None, bar.ts) if prev else None
        w5 = b5[max(0, t - W5 + 1):t + 1]
        w15 = b15[max(0, j15 - q.lookback_candles - 60):j15]
        res = evaluate(symbol, w5, w15, w5 if a.atr_timeframe == "5m" else w15, vv, cfg)
        if not res.breakout or res.breakout["ts"] in used:
            continue
        if res.state == "REJECTED" or (res.state == "QUALIFIED" and pos is not None):
            used.add(res.breakout["ts"])  # live lifecycle: a rejected setup is final
            continue
        if res.state != "QUALIFIED":
            continue
        used.add(res.breakout["ts"])
        dr = 1 if res.direction == "CALL" else -1
        risk = abs(res.entry_price - res.stop_price) if res.stop_price else (res.atr_value or 0)
        sig = {"symbol": symbol, "dir": res.direction, "ts": bar.ts.isoformat(), "entry": res.entry_price, "risk": risk,
               "adx5": res.snapshot.get("adx5"), "adx15": res.snapshot.get("adx15"), "atr_status": res.snapshot.get("atr_status")}
        pos = Position(dr, res.entry_price, res.stop_price, res.target_price, res.snapshot.get("adx5") or 0,
                       res.snapshot.get("adx5") or 0)
    return trades


def stats(tr: list[dict]) -> str:
    if not tr:
        return "0 trades"
    rs = [x["R"] for x in tr if x["R"] is not None]
    wins = sum(1 for r in rs if r > 0)
    eq = pk = dd = 0.0
    for r in rs:
        eq += r; pk = max(pk, eq); dd = min(dd, eq - pk)
    months = max(1, len({x["ts"][:7] for x in tr}))
    reasons = defaultdict(int)
    for x in tr:
        reasons[x["reason"]] += 1
    return (f"{len(tr)} trades ({len(tr)/months:.1f}/mo) | win {100*wins/len(rs):.1f}% | avg {sum(rs)/len(rs):+.3f}R | "
            f"total {sum(rs):+.1f}R | maxDD {dd:.1f}R | exits {dict(reasons)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", action="append", required=True)
    ap.add_argument("--vix", required=True)
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--cost", action="append", default=[])
    ap.add_argument("--from", dest="start", default="2025-01-01")
    ap.add_argument("--split", default="2026-01-13")
    ap.add_argument("--out")
    a = ap.parse_args()
    cfg = apply_overrides(StrategyConfig(), a.set)
    costs = {k: float(v) for k, v in (c.split("=") for c in a.cost)}
    vix = {}
    with open(a.vix) as f:
        for r in csv.DictReader(f):
            vix[r["day"]] = float(r["close"])
    allt = []
    for spec in a.csv:
        sym, path = spec.split("=", 1)
        rows = []
        for p in path.split(","):
            rows += read_5m(p)
        rows = sorted({r["ts"]: r for r in rows}.values(), key=lambda r: r["ts"])
        tr = replay(sym, rows, vix, cfg, a.start, costs.get(sym, 0))
        allt += tr
        h1 = [x for x in tr if x["ts"] < a.split]; h2 = [x for x in tr if x["ts"] >= a.split]
        print(f"{sym:<7} ALL  {stats(tr)}\n{sym:<7} <{a.split} {stats(h1)}\n{sym:<7} >={a.split} {stats(h2)}")
    print(f"BOTH    ALL  {stats(sorted(allt, key=lambda x: x['ts']))}")
    if a.out:
        json.dump(allt, open(a.out, "w"), default=str)


if __name__ == "__main__":
    main()

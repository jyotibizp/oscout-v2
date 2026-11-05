"""Research: do v1.0.2 trades do better when the 15m ADX slope turns from negative to positive at the 5m breakout?

Rules agreed with pradeep (thread "Analyse 15m ADX turn plus 5m breakout trades", 4-5 Nov 2026):
- 5m breakout, entry, stop, target, exits: the v1.0.2 engine, unchanged (all trades already pass it).
- 15m slope[k] = 15m ADX[k] - 15m ADX[k-2] (app's slope_candles = 2).
- Turn at 15m candle k: slope[k-1] < 0 and slope[k] > 0.
- Same time: turn on the 15m candle containing the 5m breakout candle, or the one just before it,
  and that 15m candle must be complete by the close of the signal candle (no look-ahead).
- 15m "breakout" was not decided, so both readings are reported:
    a) the turn itself;  b) the turn AND 15m ADX[k] > mean of its previous 5 values.
- Costs in index points per trade: NIFTY 1, SENSEX 3, BANKNIFTY 2. R = (points - cost) / risk points.

Usage (from backend/):
  python -m app.tools.adx15_turn replay --csv NIFTY=a.csv,b.csv --csv SENSEX=... --vix vix.csv [--from 2025-01-01]
  python -m app.tools.adx15_turn db            # closed live + LATE trades in the app database (.env DATABASE_URL)
"""
import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta

COSTS = {"NIFTY": 1.0, "SENSEX": 3.0, "BANKNIFTY": 2.0}
M15 = timedelta(minutes=15)
M5 = timedelta(minutes=5)


def _ts(x) -> datetime:
    from app.core.clock import UTC
    t = datetime.fromisoformat(x) if isinstance(x, str) else x
    return t.replace(tzinfo=UTC) if t.tzinfo is None else t


def tag(b15, breakout_ts: datetime, signal_ts: datetime) -> dict:
    """b15: 15m Bars ascending (ts = candle start). Returns turn flags for readings a and b."""
    idx = {b.ts: i for i, b in enumerate(b15)}
    adx = [b.adx for b in b15]
    K = next((i for i, b in enumerate(b15) if b.ts <= breakout_ts < b.ts + M15), None)
    out = {"a": False, "b": False, "turn_after_signal": False, "slope15": None}
    if K is None:
        out["no_15m"] = True
        return out

    def slope(k):
        if k < 2 or adx[k] is None or adx[k - 2] is None:
            return None
        return adx[k] - adx[k - 2]

    for k in (K - 1, K):
        if k < 3:
            continue
        s0, s1 = slope(k - 1), slope(k)
        if s0 is None or s1 is None or not (s0 < 0 and s1 > 0):
            continue
        if b15[k].ts + M15 > signal_ts + M5:      # 15m candle not complete when the signal fired
            out["turn_after_signal"] = True
            continue
        out["a"] = True
        prev = [v for v in adx[max(0, k - 5):k] if v is not None]
        if len(prev) == 5 and adx[k] > sum(prev) / 5:
            out["b"] = True
    # 15m slope on the last 15m candle complete at the signal (for reference)
    done = [i for i, b in enumerate(b15) if b.ts + M15 <= signal_ts + M5]
    if done:
        out["slope15"] = slope(done[-1])
    return out


def stats(tr: list[dict]) -> str:
    rs = [t["R"] for t in tr if t["R"] is not None]
    if not rs:
        return "  0 trades"
    w = sum(1 for r in rs if r > 0)
    pos = [r for r in rs if r > 0]; neg = [r for r in rs if r <= 0]
    return (f"{len(rs):4d} trades | win {100*w/len(rs):5.1f}% | avg {sum(rs)/len(rs):+.3f}R | total {sum(rs):+6.1f}R"
            f" | avg win {sum(pos)/len(pos) if pos else 0:+.2f}R | avg loss {sum(neg)/len(neg) if neg else 0:+.2f}R"
            f" | best {max(rs):+.2f}R")


def report(trades: list[dict], title: str) -> str:
    lines = [f"== {title} =="]
    years = sorted({t["ts"][:4] for t in trades})
    for scope, sel in [("ALL", trades)] + [(y, [t for t in trades if t["ts"][:4] == y]) for y in years]:
        lines.append(f"-- {scope}")
        lines.append(f"  all v1.0.2 trades      {stats(sel)}")
        for v in ("a", "b"):
            lines.append(f"  turn ({v}) YES          {stats([t for t in sel if t[v]])}")
            lines.append(f"  turn ({v}) NO           {stats([t for t in sel if not t[v]])}")
        n = sum(1 for t in sel if t["turn_after_signal"] and not t["a"])
        lines.append(f"  (turn only completed after the signal fired, excluded from YES: {n})")
        for sym in sorted({t["symbol"] for t in sel}):
            s = [t for t in sel if t["symbol"] == sym]
            lines.append(f"  {sym:<9} a YES {stats([t for t in s if t['a']])}")
            lines.append(f"  {sym:<9} a NO  {stats([t for t in s if not t['a']])}")
    return "\n".join(lines)


def run_replay(a) -> list[dict]:
    from app.strategy.config import StrategyConfig
    from app.tools.replay import read_5m, replay, to_15m, with_ind
    cfg = StrategyConfig()
    vix = {}
    with open(a.vix) as f:
        for r in csv.DictReader(f):
            vix[r["day"]] = float(r["close"])
    out = []
    for spec in a.csv:
        sym, path = spec.split("=", 1)
        rows = []
        for p in path.split(","):
            rows += read_5m(p)
        rows = sorted({r["ts"]: r for r in rows}.values(), key=lambda r: r["ts"])
        b15 = with_ind(to_15m(rows), cfg.fifteen_min.adx_period, cfg.atr.atr_period)
        for t in replay(sym, rows, vix, cfg, a.start, COSTS.get(sym, 0)):
            t.update(tag(b15, _ts(t["breakout_ts"]), _ts(t["ts"])))
            out.append(t)
        print(f"{sym}: {sum(1 for t in out if t['symbol'] == sym)} trades", file=sys.stderr)
    return out


def run_db(a) -> list[dict]:
    from sqlalchemy import select
    from app.db.models import SignalEvent, SignalSetup, Trade
    from app.db.session import SessionLocal, get_engine
    from app.market.repository import load_bars
    from app.signals.lifecycle import LATE_EVENT
    get_engine()
    db = SessionLocal()
    late = set(db.scalars(select(SignalEvent.setup_id).where(SignalEvent.event == LATE_EVENT)))
    rows = db.execute(select(Trade, SignalSetup).join(SignalSetup, SignalSetup.id == Trade.setup_id)
                      .where(Trade.status == "CLOSED")).all()
    out = []
    for tr, s in rows:
        if a.symbols and tr.symbol not in a.symbols:
            continue
        sig = _ts(s.signal_ts or tr.entry_ts)
        b15 = load_bars(db, tr.symbol, "15m", 14, 14, 60, until=sig + timedelta(hours=1))
        cost = COSTS.get(tr.symbol, 0)
        R = (tr.pnl_points - cost) / tr.risk_points if tr.risk_points and tr.pnl_points is not None else None
        t = {"symbol": tr.symbol, "dir": tr.direction, "ts": sig.isoformat(), "breakout_ts": _ts(s.breakout_ts).isoformat(),
             "entry": tr.entry_price, "exit": tr.exit_price, "reason": tr.exit_reason, "pts": tr.pnl_points,
             "risk": tr.risk_points, "R": R, "late": s.id in late, "config": tr.config_version}
        t.update(tag(b15, _ts(s.breakout_ts), sig))
        out.append(t)
    return sorted(out, key=lambda t: t["ts"])


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    r = sub.add_parser("replay")
    r.add_argument("--csv", action="append", required=True)
    r.add_argument("--vix", required=True)
    r.add_argument("--from", dest="start", default="2025-01-01")
    r.add_argument("--out")
    d = sub.add_parser("db")
    d.add_argument("--symbols", nargs="*", default=["NIFTY", "SENSEX"])
    d.add_argument("--out")
    a = ap.parse_args()
    trades = run_replay(a) if a.mode == "replay" else run_db(a)
    print(report(trades, "replay on CSV candles" if a.mode == "replay" else "live + LATE trades in the database"))
    if a.mode == "db":
        print("\nPer trade (a/b = turn flags):")
        for t in trades:
            print(f"  {t['ts'][:16]} {t['symbol']:<7} {t['dir']:<4} {'LATE' if t['late'] else 'LIVE'} "
                  f"R {t['R'] if t['R'] is None else round(t['R'], 2):>6} a={int(t['a'])} b={int(t['b'])} "
                  f"slope15={t['slope15'] if t['slope15'] is None else round(t['slope15'], 1)} {t['reason']}")
    if a.out:
        json.dump(trades, open(a.out, "w"), default=str, indent=1)


if __name__ == "__main__":
    main()

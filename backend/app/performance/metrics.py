"""Performance analytics for the ADX strategy, measured on the underlying (index points, % and R)."""
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import to_ist
from app.db.models import ScanResult, ScanRun, SignalSetup, Trade


def _trades(db: Session, symbol: str | None = None, version: str | None = None) -> list[Trade]:
    q = select(Trade).where(Trade.status == "CLOSED")
    if symbol:
        q = q.where(Trade.symbol == symbol)
    if version:
        q = q.where(Trade.config_version == version)
    return list(db.scalars(q.order_by(Trade.exit_ts)))


def trade_stats(ts: list[Trade]) -> dict:
    n = len(ts)
    if n == 0:
        return {"trades": 0}
    pts = [t.pnl_points for t in ts]
    wins = [p for p in pts if p > 0]
    losses = [p for p in pts if p <= 0]
    rs = [t.r_multiple for t in ts if t.r_multiple is not None]
    eq, peak, mdd = 0.0, 0.0, 0.0
    for p in pts:
        eq += p
        peak = max(peak, eq)
        mdd = min(mdd, eq - peak)
    avg_gain = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    return {"trades": n, "wins": len(wins), "losses": len(losses), "win_rate": round(100 * len(wins) / n, 1),
            "avg_gain_points": round(avg_gain, 2), "avg_loss_points": round(avg_loss, 2),
            "risk_reward": round(avg_gain / abs(avg_loss), 2) if avg_loss else None,
            "expectancy_points": round(sum(pts) / n, 2), "expectancy_r": round(sum(rs) / len(rs), 3) if rs else None,
            "net_points": round(sum(pts), 2), "net_pct": round(sum(t.pnl_pct or 0 for t in ts), 3),
            "net_r": round(sum(rs), 2) if rs else None,
            "profit_factor": round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) != 0 else None,
            "max_drawdown_points": round(mdd, 2),
            "avg_holding_minutes": round(sum(t.holding_minutes or 0 for t in ts) / n, 1)}


def summary(db: Session, symbol: str | None = None, version: str | None = None) -> dict:
    ts = _trades(db, symbol, version)
    scans = db.scalar(select(func.count()).select_from(ScanRun)) or 0
    setups = db.scalar(select(func.count()).select_from(SignalSetup)) or 0
    sig_q = select(SignalSetup.direction, func.count()).where(SignalSetup.signal_ts.is_not(None)).group_by(SignalSetup.direction)
    by_dir = dict(db.execute(sig_q).all())
    rejected = db.scalar(select(func.count()).select_from(SignalSetup).where(SignalSetup.state.in_(("REJECTED", "EXPIRED")))) or 0
    open_trades = db.scalar(select(func.count()).select_from(Trade).where(Trade.status == "OPEN")) or 0
    return {"signals": {"total_scans": scans, "total_setups": setups, "total_signals": sum(by_dir.values()),
                        "call_signals": by_dir.get("CALL", 0), "put_signals": by_dir.get("PUT", 0),
                        "rejected_or_expired_setups": rejected, "open_trades": open_trades},
            "trading": trade_stats(ts), "funnel": funnel(db)}


def funnel(db: Session) -> dict:
    """Gate-wise outcome of every symbol evaluation (scan_results)."""
    total = db.scalar(select(func.count()).select_from(ScanResult)) or 0
    g1 = db.scalar(select(func.count()).select_from(ScanResult).where(ScanResult.gate1 == "PASS")) or 0
    g2 = db.scalar(select(func.count()).select_from(ScanResult).where(ScanResult.gate2 == "PASS")) or 0
    atr = db.scalar(select(func.count()).select_from(ScanResult).where(ScanResult.gate2 == "PASS", ScanResult.atr_filter == "PASS")) or 0
    vix = db.scalar(select(func.count()).select_from(ScanResult).where(ScanResult.atr_filter == "PASS", ScanResult.vix_filter == "PASS", ScanResult.gate2 == "PASS")) or 0
    sig = db.scalar(select(func.count()).select_from(ScanResult).where(ScanResult.final_result == "SIGNAL")) or 0
    def rate(a, b):
        return round(100 * (1 - a / b), 1) if b else None
    return {"evaluations": total, "gate1_pass": g1, "gate2_pass": g2, "atr_pass": atr, "vix_pass": vix, "signals": sig,
            "rejection_rate": {"gate1": rate(g1, total), "gate2": rate(g2, g1), "atr": rate(atr, g2), "vix": rate(vix, atr)}}


def equity_curve(db: Session, symbol: str | None = None) -> list[dict]:
    out, eq, eqr = [], 0.0, 0.0
    for t in _trades(db, symbol):
        eq += t.pnl_points
        eqr += t.r_multiple or 0
        out.append({"ts": t.exit_ts.isoformat(), "symbol": t.symbol, "pnl_points": t.pnl_points, "cum_points": round(eq, 2),
                    "r": t.r_multiple, "cum_r": round(eqr, 3)})
    return out


def _bucket(v, edges, labels):
    if v is None:
        return "n/a"
    for e, lab in zip(edges, labels):
        if v < e:
            return lab
    return labels[-1]


def analytics(db: Session) -> dict:
    ts = _trades(db)
    dims = {
        "symbol": lambda t: t.symbol,
        "direction": lambda t: t.direction,
        "hour": lambda t: f"{to_ist(t.entry_ts):%H}:00",
        "weekday": lambda t: f"{to_ist(t.entry_ts):%a}",
        "breakout_strength": lambda t: _bucket(t.breakout_adx_change, [1, 2, 3], ["<1", "1–2", "2–3", "3+"]),
        "adx15": lambda t: _bucket(t.adx15_entry, [15, 20, 25, 30], ["<15", "15–20", "20–25", "25–30", "30+"]),
        "atr_status": lambda t: t.atr_status or "n/a",
        "vix_regime": lambda t: _bucket(t.vix_entry, [13, 18], ["LOW (<13)", "NORMAL (13–18)", "HIGH (18+)"]),
    }
    out = {}
    for name, fn in dims.items():
        groups = defaultdict(list)
        for t in ts:
            groups[fn(t)].append(t)
        out[name] = [{"bucket": k, **trade_stats(v)} for k, v in sorted(groups.items())]
    hist = defaultdict(int)
    for t in ts:
        r = t.r_multiple if t.r_multiple is not None else 0
        hist[max(-3.0, min(3.0, round(r * 2) / 2))] += 1
    out["r_distribution"] = [{"r": k, "count": v} for k, v in sorted(hist.items())]
    sig_hours = defaultdict(int)
    for s in db.scalars(select(SignalSetup).where(SignalSetup.signal_ts.is_not(None))):
        sig_hours[f"{to_ist(s.signal_ts):%H}:00"] += 1
    out["signals_by_hour"] = [{"hour": k, "count": v} for k, v in sorted(sig_hours.items())]
    return out

"""REST API: /api/market, /api/scans, /api/signals, /api/config, /api/performance, /api/system."""
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api import serializers as ser
from app.core.clock import IST, as_utc, is_market_open, now_utc, to_ist
from app.core.settings import get_settings
from app.db.models import (MarketCandle, ScanResult, ScanRun, SignalEvent, SignalSetup, StrategyConfiguration,
                           SystemEvent, Trade)
from app.db.session import get_db
from app.market import health
from app.market.factory import get_provider, save_token
from app.market.providers import AuthError
from app.market.repository import load_bars
from app.market.symbols import TRADABLE
from app.performance import metrics
from app.scanner.scheduler import auto_scanner
from app.scanner.service import run_scan
from app.signals.lifecycle import OPEN
from app.strategy import store
from app.strategy.config import StrategyConfig, describe

router = APIRouter(prefix="/api")


def _day_range(d_from: date | None, d_to: date | None):
    lo = as_utc(datetime.combine(d_from, time(0), tzinfo=IST)) if d_from else None
    hi = as_utc(datetime.combine(d_to, time(23, 59, 59), tzinfo=IST)) if d_to else None
    return lo, hi


# ---------------- market ----------------
@router.get("/market/candles")
def candles(symbol: str, timeframe: str = "5m", limit: int = Query(150, le=1000), db: Session = Depends(get_db)):
    _, cfg = store.get_active(db)
    p = cfg.five_min.adx_period if timeframe == "5m" else cfg.fifteen_min.adx_period
    bars = load_bars(db, symbol.upper(), timeframe, p, cfg.atr.atr_period, limit)
    return [{"ts": b.ts.isoformat(), "open": b.open, "high": b.high, "low": b.low, "close": b.close,
             "adx": b.adx, "pdi": b.pdi, "mdi": b.mdi, "atr": b.atr} for b in bars]


# ---------------- scans ----------------
@router.post("/scans/run")
def scan_now(db: Session = Depends(get_db)):
    try:
        run, _ = run_scan(db, get_provider(), trigger="MANUAL")
    except AuthError as e:
        raise HTTPException(401, str(e))
    results = db.scalars(select(ScanResult).where(ScanResult.scan_run_id == run.id)).all()
    return {"run": ser.scan_run(run), "results": [ser.scan_result(r) for r in results]}


@router.get("/scans/latest")
def scans_latest(db: Session = Depends(get_db)):
    out = {}
    for sym in TRADABLE:
        r = db.scalar(select(ScanResult).where(ScanResult.symbol == sym).order_by(ScanResult.id.desc()).limit(1))
        out[sym] = ser.scan_result(r, full=True) if r else None
    run = db.scalar(select(ScanRun).order_by(ScanRun.id.desc()).limit(1))
    return {"run": ser.scan_run(run) if run else None, "symbols": out}


@router.get("/scans/history")
def scans_history(symbol: str | None = None, final: str | None = None, state: str | None = None,
                  direction: str | None = None, gate_failed: str | None = None, date_from: date | None = None,
                  date_to: date | None = None, limit: int = Query(100, le=1000), offset: int = 0,
                  db: Session = Depends(get_db)):
    q = select(ScanResult)
    if symbol:
        q = q.where(ScanResult.symbol == symbol.upper())
    if final:
        q = q.where(ScanResult.final_result == final)
    if state:
        q = q.where(ScanResult.state == state)
    if direction:
        q = q.where(ScanResult.direction == direction)
    if gate_failed in ("gate1", "gate2", "atr_filter", "vix_filter"):
        q = q.where(getattr(ScanResult, gate_failed) == "FAIL")
    lo, hi = _day_range(date_from, date_to)
    if lo:
        q = q.where(ScanResult.candle_ts >= lo)
    if hi:
        q = q.where(ScanResult.candle_ts <= hi)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(ScanResult.id.desc()).offset(offset).limit(limit)).all()
    return {"total": total, "items": [ser.scan_result(r) for r in rows]}


@router.get("/scans/results/{rid}")
def scan_result_detail(rid: int, db: Session = Depends(get_db)):
    r = db.get(ScanResult, rid)
    if r is None:
        raise HTTPException(404, "Scan result not found")
    return ser.scan_result(r, full=True)


@router.get("/scans/{sid}")
def scan_detail(sid: int, db: Session = Depends(get_db)):
    run = db.get(ScanRun, sid)
    if run is None:
        raise HTTPException(404, "Scan not found")
    results = db.scalars(select(ScanResult).where(ScanResult.scan_run_id == sid)).all()
    return {"run": ser.scan_run(run), "results": [ser.scan_result(r, full=True) for r in results]}


# ---------------- signals ----------------
def _setup_full(db: Session, s: SignalSetup) -> dict:
    events = db.scalars(select(SignalEvent).where(SignalEvent.setup_id == s.id).order_by(SignalEvent.id)).all()
    return ser.setup(s, events, db.scalar(select(Trade).where(Trade.setup_id == s.id)))


@router.get("/signals/active")
def signals_active(db: Session = Depends(get_db)):
    rows = db.scalars(select(SignalSetup).where(SignalSetup.state.in_(OPEN)).order_by(SignalSetup.id.desc())).all()
    pending = db.scalars(select(SignalSetup).where(SignalSetup.state.in_(("BREAKOUT_DETECTED", "WAITING_CONFIRMATION")))
                         .order_by(SignalSetup.id.desc())).all()
    return {"active": [_setup_full(db, s) for s in rows], "pending": [_setup_full(db, s) for s in pending]}


@router.get("/signals/history")
def signals_history(symbol: str | None = None, direction: str | None = None, status: str | None = None,
                    outcome: str | None = None, vix_regime: str | None = None, date_from: date | None = None,
                    date_to: date | None = None, limit: int = Query(100, le=1000), offset: int = 0,
                    db: Session = Depends(get_db)):
    q = select(SignalSetup)
    if symbol:
        q = q.where(SignalSetup.symbol == symbol.upper())
    if direction:
        q = q.where(SignalSetup.direction == direction)
    if status == "active":
        q = q.where(SignalSetup.state.in_(OPEN))
    elif status == "closed":
        q = q.where(SignalSetup.state.in_(("EXIT_TRIGGERED", "EXPIRED", "REJECTED")))
    if outcome == "qualified":
        q = q.where(SignalSetup.signal_ts.is_not(None))
    elif outcome == "rejected":
        q = q.where(SignalSetup.signal_ts.is_(None))
    lo, hi = _day_range(date_from, date_to)
    if lo:
        q = q.where(SignalSetup.breakout_ts >= lo)
    if hi:
        q = q.where(SignalSetup.breakout_ts <= hi)
    rows = db.scalars(q.order_by(SignalSetup.id.desc()).offset(offset).limit(limit * 3 if vix_regime else limit)).all()
    items = []
    for s in rows:
        t = db.scalar(select(Trade).where(Trade.setup_id == s.id))
        if vix_regime:
            v = (s.signal_context or {}).get("vix")
            reg = None if v is None else "LOW" if v < 13 else "NORMAL" if v < 18 else "HIGH"
            if reg != vix_regime:
                continue
        items.append(ser.setup(s, None, t))
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    return {"total": total, "items": items[:limit]}


@router.get("/signals/{sid}")
def signal_detail(sid: int, db: Session = Depends(get_db)):
    s = db.get(SignalSetup, sid)
    if s is None:
        raise HTTPException(404, "Signal not found")
    out = _setup_full(db, s)
    out["scans"] = [ser.scan_result(r) for r in db.scalars(
        select(ScanResult).where(ScanResult.setup_id == sid).order_by(ScanResult.id))]
    return out


# ---------------- configuration ----------------
class ConfigUpdate(BaseModel):
    params: dict
    note: str | None = None


@router.get("/config")
def config_get(db: Session = Depends(get_db)):
    row, cfg = store.get_active(db)
    return {"version": row.version, "id": row.id, "created_at": ser.iso(row.created_at), "note": row.note,
            "params": cfg.model_dump(), "defaults": StrategyConfig().model_dump(), "schema": describe()}


@router.put("/config")
def config_put(body: ConfigUpdate, db: Session = Depends(get_db)):
    row, cfg = store.get_active(db)
    try:
        new = StrategyConfig.model_validate(body.params)
    except ValidationError as e:
        raise HTTPException(422, [{"loc": ".".join(str(x) for x in err["loc"]), "msg": err["msg"]} for err in e.errors()])
    changes = store.diff(cfg.model_dump(), new.model_dump())
    if not changes:
        return {"version": row.version, "changed": [], "message": "No changes"}
    saved = store.save(db, new, body.note or f"{len(changes)} parameter(s) changed")
    return {"version": saved.version, "changed": changes}


@router.post("/config/reset")
def config_reset(db: Session = Depends(get_db)):
    saved = store.save(db, StrategyConfig(), "Reset to defaults")
    return {"version": saved.version}


@router.get("/config/versions")
def config_versions(db: Session = Depends(get_db)):
    rows = db.scalars(select(StrategyConfiguration).order_by(StrategyConfiguration.id.desc())).all()
    return [{"id": r.id, "version": r.version, "is_active": r.is_active, "note": r.note,
             "created_at": ser.iso(r.created_at)} for r in rows]


# ---------------- performance ----------------
@router.get("/performance/summary")
def perf_summary(symbol: str | None = None, version: str | None = None, db: Session = Depends(get_db)):
    return metrics.summary(db, symbol, version)


@router.get("/performance/trades")
def perf_trades(symbol: str | None = None, direction: str | None = None, status: str | None = None,
                limit: int = Query(200, le=2000), db: Session = Depends(get_db)):
    q = select(Trade)
    if symbol:
        q = q.where(Trade.symbol == symbol.upper())
    if direction:
        q = q.where(Trade.direction == direction)
    if status:
        q = q.where(Trade.status == status.upper())
    return [ser.trade(t) for t in db.scalars(q.order_by(Trade.id.desc()).limit(limit))]


@router.get("/performance/equity")
def perf_equity(symbol: str | None = None, db: Session = Depends(get_db)):
    return metrics.equity_curve(db, symbol)


@router.get("/performance/analytics")
def perf_analytics(db: Session = Depends(get_db)):
    return metrics.analytics(db)


# ---------------- system ----------------
class AutoScanToggle(BaseModel):
    enabled: bool


@router.get("/system/health")
def system_health(db: Session = Depends(get_db)):
    now = now_utc()
    _, cfg = store.get_active(db)
    p = get_provider()
    feeds = health.all_feeds(db, now, cfg.scanner.max_data_age_minutes)
    last = db.scalar(select(ScanRun).order_by(ScanRun.id.desc()).limit(1))
    return {"now": now.isoformat(), "market_open": is_market_open(now), "provider": p.name,
            "connected": p.is_connected(), "session_date": str(getattr(p, "_token_day", "") or "") or None, "feeds": feeds, "auto_scan": auto_scanner.status(),
            "last_scan": ser.scan_run(last) if last else None}


@router.get("/system/connect")
def system_connect():
    p = get_provider()
    if p.name != "kite":
        return {"provider": p.name, "connected": True, "login_url": None, "message": "Mock data provider — no login needed"}
    return {"provider": "kite", "connected": p.is_connected(), "login_url": p.login_url()}


@router.get("/system/callback")
@router.get("/auth/callback")  # same redirect URL as v1, so the existing Kite app works unchanged
def system_callback(request_token: str, db: Session = Depends(get_db)):
    p = get_provider()
    if p.name != "kite":
        raise HTTPException(400, "Kite provider is not active")
    try:
        data = p.complete_login(request_token)
    except AuthError as e:
        raise HTTPException(401, str(e))
    save_token(data.get("user_id"), data["access_token"])
    db.add(SystemEvent(ts=now_utc(), level="INFO", category="CONNECTION", message="Kite session connected",
                       data={"user_id": data.get("user_id")}))
    db.commit()
    return RedirectResponse(get_settings().frontend_url)


@router.post("/system/autoscan")
def system_autoscan(body: AutoScanToggle, db: Session = Depends(get_db)):
    auto_scanner.runtime_enabled = body.enabled
    db.add(SystemEvent(ts=now_utc(), level="INFO", category="SCAN", message=f"Auto scan switched {'ON' if body.enabled else 'OFF'}"))
    db.commit()
    return auto_scanner.status()


@router.get("/system/events")
def system_events(category: str | None = None, limit: int = Query(100, le=1000), db: Session = Depends(get_db)):
    q = select(SystemEvent)
    if category:
        q = q.where(SystemEvent.category == category.upper())
    return [{"id": e.id, "ts": ser.iso(e.ts), "level": e.level, "category": e.category, "message": e.message,
             "data": e.data} for e in db.scalars(q.order_by(SystemEvent.id.desc()).limit(limit))]

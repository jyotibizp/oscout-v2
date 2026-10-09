"""Scan orchestration: ingest -> check freshness -> evaluate -> persist scan results -> advance lifecycle.

Every scan (manual or automatic) writes one scan_runs row and one scan_results row per symbol, including
rejections, so any decision can be reconstructed later together with the configuration version used.
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import is_market_open, latest_completed_start, now_utc
from app.db.models import ScanResult, ScanRun, SignalSetup, SystemEvent
from app.market import health
from app.market.ingestion import latest_ts, sync_symbol
from app.market.repository import load_bars, vix_snapshot, wilder_state
from app.market.symbols import TRADABLE, VIX
from app.signals.lifecycle import OPEN, apply_result, update_open_signals
from app.strategy import store
from app.strategy import commentary
from app.strategy.config import StrategyConfig
from app.strategy.engine import evaluate

log = logging.getLogger(__name__)


class ScanBusy(Exception):
    pass


def ingest_all(db: Session, provider, cfg: StrategyConfig, now: datetime) -> dict:
    out = {}
    for sym in TRADABLE + [VIX]:
        try:
            r = sync_symbol(db, provider, sym, cfg.indicator_periods(), now)
            db.commit()
            health.LAST_SYNC[sym] = {"at": now.isoformat(), "error": None}
            out[sym] = {"inserted_5m": r.inserted_5m, "inserted_15m": r.inserted_15m, "duplicates": r.duplicates,
                        "rejected": r.rejected, "latest_5m": r.latest_5m.isoformat() if r.latest_5m else None}
        except Exception as e:  # noqa: BLE001 - a failing feed must not stop the other symbols
            db.rollback()
            health.LAST_SYNC[sym] = {"at": now.isoformat(), "error": str(e)}
            db.add(SystemEvent(ts=now, level="ERROR", category="DATA", message=f"{sym} ingestion failed: {e}"[:300]))
            db.commit()
            log.error("ingestion failed", extra={"ctx": {"symbol": sym, "error": str(e)}})
            out[sym] = {"error": str(e)}
    return out


def _stale(db: Session, symbol: str, now: datetime, cfg: StrategyConfig) -> dict[str, str]:
    if not is_market_open(now):
        return {}
    out = {}
    age = timedelta(minutes=cfg.scanner.max_data_age_minutes)
    last5 = latest_ts(db, symbol, "5m")
    if last5 is None:
        out["5m"] = "5M DATA UNAVAILABLE"
    elif last5 < latest_completed_start(now, "5m") - age:
        out["5m"] = "5M DATA STALE"
    last15 = latest_ts(db, symbol, "15m")
    if last15 is None:
        out["15m"] = "15M DATA UNAVAILABLE"
    elif last15 < latest_completed_start(now, "15m") - age - timedelta(minutes=15):
        out["15m"] = "15M DATA STALE"
    return out


def evaluate_symbol(db: Session, symbol: str, cfg: StrategyConfig, now: datetime, until: datetime | None = None):
    f, q, a = cfg.five_min, cfg.fifteen_min, cfg.atr
    n5 = max(f.max_compression_candles + f.breakout_lookback + f.breakout_valid_candles + 40, 300)
    bars5 = load_bars(db, symbol, "5m", f.adx_period, a.atr_period, n5, until)
    if not bars5:
        return None, bars5
    end5 = bars5[-1].ts + timedelta(minutes=5)
    bars15 = [b for b in load_bars(db, symbol, "15m", q.adx_period, a.atr_period, q.lookback_candles + 60, until)
              if b.ts + timedelta(minutes=15) <= end5]
    atr_bars = bars5 if a.atr_timeframe == "5m" else bars15
    vix = vix_snapshot(db, now, cfg.vix.max_age_minutes, is_market_open(now))  # None -> "VIX DATA UNAVAILABLE"
    stale = _stale(db, symbol, now, cfg)
    res = evaluate(symbol, bars5, bars15, atr_bars, vix, cfg, stale or None)
    try:
        res.commentary = commentary.build(res, bars5, bars15, cfg,
                                          wilder_state(db, symbol, "5m", f.adx_period, bars5[-1].ts))
    except Exception:  # noqa: BLE001 - commentary is explanatory; it must never fail a scan
        log.exception("commentary failed", extra={"ctx": {"symbol": symbol}})
    return res, bars5


def run_scan(db: Session, provider, trigger: str = "MANUAL", now: datetime | None = None,
             ingest: bool = True) -> tuple[ScanRun, bool]:
    """Returns (scan_run, created). AUTO scans are unique per completed 5m candle."""
    now = now or now_utc()
    cfg_row, cfg = store.get_active(db)
    candle = latest_completed_start(now, "5m")
    dedupe = f"AUTO:{candle.isoformat()}" if trigger == "AUTO" else None
    if dedupe and db.scalar(select(ScanRun).where(ScanRun.dedupe_key == dedupe)):
        return db.scalar(select(ScanRun).where(ScanRun.dedupe_key == dedupe)), False
    run = ScanRun(trigger=trigger, candle_ts=candle, dedupe_key=dedupe, started_at=now, status="RUNNING",
                  config_id=cfg_row.id, config_version=cfg_row.version)
    db.add(run)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return db.scalar(select(ScanRun).where(ScanRun.dedupe_key == dedupe)), False

    summary = {"ingestion": ingest_all(db, provider, cfg, now) if ingest else {}, "symbols": {}}
    errors = 0
    for sym in TRADABLE:
        try:
            res, bars5 = evaluate_symbol(db, sym, cfg, now)
            if res is None:
                raise RuntimeError(f"No {sym} 5m data")
            stale = res.state == "REJECTED" and res.gate1.status == "FAIL" and "DATA" in res.reason
            exited = [] if stale else update_open_signals(db, sym, bars5, cfg)
            setup, state, note = (None, res.state, None) if stale else apply_result(
                db, res, cfg, cfg_row.id, cfg_row.version, now)
            if exited and state not in ("SIGNAL_GENERATED",):
                state, note = "EXIT_TRIGGERED", f"{exited[-1].direction} exit: {exited[-1].exit_reason}"
            elif state in ("WATCHING", "COMPRESSION", "EXPIRED"):
                act = db.scalar(select(SignalSetup).where(SignalSetup.symbol == sym, SignalSetup.state.in_(OPEN)))
                if act is not None:
                    state, setup = "ACTIVE", act
            final = "SIGNAL" if state == "SIGNAL_GENERATED" else "NO_SIGNAL"
            reason = None if final == "SIGNAL" else (note or res.reason)
            s = res.snapshot
            details = res.to_dict()
            details["effective_state"] = state
            details["note"] = note
            db.add(ScanResult(scan_run_id=run.id, symbol=sym, candle_ts=res.candle_ts, adx5=s.get("adx5"),
                              pdi5=s.get("pdi5"), mdi5=s.get("mdi5"), adx15=s.get("adx15"), pdi15=s.get("pdi15"),
                              mdi15=s.get("mdi15"), atr=s.get("atr"), atr_status=s.get("atr_status"), vix=s.get("vix"),
                              vix_change_pct=s.get("vix_change_pct"), gate1=res.gate1.status, gate2=res.gate2.status,
                              atr_filter=res.atr.status, vix_filter=res.vix.status, final_result=final, state=state,
                              direction=res.direction or (setup.direction if setup else None),
                              rejection_reason=(reason or "")[:200] or None, details=_jsonable(details),
                              config_version=cfg_row.version, setup_id=setup.id if setup else None))
            db.commit()
            summary["symbols"][sym] = {"state": state, "final": final, "direction": res.direction, "reason": reason}
            log.info("scan result", extra={"ctx": {"scan_id": run.id, "symbol": sym, "state": state, "final": final,
                                                   "gate1": res.gate1.status, "gate2": res.gate2.status,
                                                   "atr": res.atr.status, "vix": res.vix.status, "reason": reason}})
        except Exception as e:  # noqa: BLE001
            db.rollback()
            errors += 1
            summary["symbols"][sym] = {"error": str(e)}
            db.add(SystemEvent(ts=now, level="ERROR", category="SCAN", message=f"{sym} evaluation failed: {e}"[:300]))
            db.commit()
            log.exception("evaluation failed", extra={"ctx": {"symbol": sym}})
    run = db.get(ScanRun, run.id)
    run.finished_at = now_utc()
    run.status = "OK" if errors == 0 else ("ERROR" if errors == len(TRADABLE) else "PARTIAL")
    run.summary = summary
    db.add(SystemEvent(ts=now, level="INFO" if errors == 0 else "WARNING", category="SCAN",
                       message=f"{trigger} scan #{run.id} {run.status}",
                       data={k: v.get("state") or v.get("error") for k, v in summary["symbols"].items()}))
    db.commit()
    return run, True


def _jsonable(o):
    if isinstance(o, dict):
        return {k: _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, datetime):
        return o.isoformat()
    if hasattr(o, "item"):
        return o.item()
    return o

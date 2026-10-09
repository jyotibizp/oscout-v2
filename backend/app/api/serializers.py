from app.db.models import ScanResult, ScanRun, SignalEvent, SignalSetup, Trade


def iso(dt):
    return dt.isoformat() if dt else None


def scan_result(r: ScanResult, full: bool = False) -> dict:
    d = {"id": r.id, "scan_run_id": r.scan_run_id, "symbol": r.symbol, "candle_ts": iso(r.candle_ts),
         "created_at": iso(r.created_at), "adx5": r.adx5, "pdi5": r.pdi5, "mdi5": r.mdi5, "adx15": r.adx15,
         "pdi15": r.pdi15, "mdi15": r.mdi15, "atr": r.atr, "atr_status": r.atr_status, "vix": r.vix,
         "vix_change_pct": r.vix_change_pct, "gate1": r.gate1, "gate2": r.gate2, "atr_filter": r.atr_filter,
         "vix_filter": r.vix_filter, "final_result": r.final_result, "state": r.state, "direction": r.direction,
         "rejection_reason": r.rejection_reason, "config_version": r.config_version, "setup_id": r.setup_id}
    if full:
        d["details"] = r.details
    else:
        det = r.details or {}
        d["reason"] = det.get("reason")
        d["entry_price"] = det.get("entry_price")
        d["commentary"] = det.get("commentary")
        d["gates"] = {k: {"status": (det.get(k) or {}).get("status"), "reasons": (det.get(k) or {}).get("reasons", [])[:4]}
                      for k in ("gate1", "gate2", "atr", "vix")}
    return d


def scan_run(r: ScanRun) -> dict:
    return {"id": r.id, "trigger": r.trigger, "candle_ts": iso(r.candle_ts), "started_at": iso(r.started_at),
            "finished_at": iso(r.finished_at), "status": r.status, "config_version": r.config_version,
            "error": r.error, "summary": r.summary}


def trade(t: Trade | None) -> dict | None:
    if t is None:
        return None
    return {"id": t.id, "setup_id": t.setup_id, "symbol": t.symbol, "direction": t.direction, "status": t.status,
            "entry_ts": iso(t.entry_ts), "entry_price": t.entry_price, "exit_ts": iso(t.exit_ts), "exit_price": t.exit_price,
            "exit_reason": t.exit_reason, "risk_points": t.risk_points, "pnl_points": t.pnl_points, "pnl_pct": t.pnl_pct,
            "r_multiple": t.r_multiple, "holding_minutes": t.holding_minutes, "config_version": t.config_version,
            "breakout_adx_change": t.breakout_adx_change, "adx5_entry": t.adx5_entry, "adx15_entry": t.adx15_entry,
            "atr_status": t.atr_status, "vix_entry": t.vix_entry}


def setup(s: SignalSetup, events: list[SignalEvent] | None = None, t: Trade | None = None) -> dict:
    d = {"id": s.id, "symbol": s.symbol, "direction": s.direction, "state": s.state, "breakout_ts": iso(s.breakout_ts),
         "detected_at": iso(s.detected_at), "config_version": s.config_version, "breakout": s.breakout,
         "signal_ts": iso(s.signal_ts), "entry_price": s.entry_price, "entry_atr": s.entry_atr, "stop_price": s.stop_price,
         "target_price": s.target_price, "signal_context": s.signal_context, "peak_adx": s.peak_adx,
         "exit_ts": iso(s.exit_ts), "exit_price": s.exit_price, "exit_reason": s.exit_reason,
         "closed_reason": s.closed_reason, "trade": trade(t)}
    if events is not None:
        d["events"] = [{"id": e.id, "event": e.event, "candle_ts": iso(e.candle_ts), "price": e.price, "note": e.note,
                        "data": e.data, "created_at": iso(e.created_at)} for e in events]
    return d

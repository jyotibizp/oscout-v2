from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import SignalEvent, SignalSetup, Trade
from app.signals.lifecycle import apply_result, update_open_signals
from app.strategy import store
from app.strategy.engine import GateResult, StrategyResult
from tests.conftest import ist, make_bars


def _result(state, ts, direction="CALL", entry=100.0):
    g = GateResult("PASS", ["ok"], {})
    bo = {"ts": ist(2026, 10, 7, 10, 0).isoformat(), "adx_before": 17.0, "adx_at": 19.5, "adx_change": 2.5,
          "direction": direction, "compression_candles": 8, "compression_low": 15.0, "di_separation": 10.0,
          "ohlc": {"open": 100, "high": 101, "low": 99, "close": 100}, "candles_since": 0}
    r = StrategyResult("NIFTY", ts, state, "SIGNAL_READY" if state == "QUALIFIED" else "NO_SIGNAL", direction, "why",
                       g, GateResult("PASS" if state == "QUALIFIED" else "FAIL", ["15m"], {}), g, g,
                       entry_price=entry, stop_price=70.0, target_price=145.0, atr_value=10.0, breakout=bo,
                       snapshot={"adx5": 19.5, "adx15": 22.0, "atr_status": "NORMAL", "vix": 14.0})
    return r


def test_setup_lifecycle_breakout_to_exit(db):
    row, cfg = store.get_active(db)
    t0 = ist(2026, 10, 7, 10, 0)
    s, state, _ = apply_result(db, _result("BREAKOUT_DETECTED", t0), cfg, row.id, row.version, t0)
    assert state == "BREAKOUT_DETECTED" and s.state == "BREAKOUT_DETECTED"
    s, state, _ = apply_result(db, _result("WAITING_CONFIRMATION", t0 + timedelta(minutes=5)), cfg, row.id, row.version, t0)
    assert state == "WAITING_CONFIRMATION"
    s, state, _ = apply_result(db, _result("QUALIFIED", t0 + timedelta(minutes=10)), cfg, row.id, row.version, t0)
    assert state == "SIGNAL_GENERATED" and s.entry_price == 100.0
    db.commit()
    bars = make_bars([21.0, 20.0, 19.0], close=[105.0, 108.0, 110.0], start=t0 + timedelta(minutes=15))
    exited = update_open_signals(db, "NIFTY", bars, cfg)
    db.commit()
    assert exited and exited[0].exit_reason == "ADX_EXHAUSTION"
    t = db.scalar(select(Trade))
    assert t.status == "CLOSED" and t.pnl_points == 10.0 and t.r_multiple == round(10 / 30, 3)
    events = [e.event for e in db.scalars(select(SignalEvent).order_by(SignalEvent.id))]
    assert events[:2] == ["COMPRESSION", "BREAKOUT"] and "SIGNAL_GENERATED" in events and events[-1] == "EXIT_TRIGGERED"


def test_pending_setup_expires_when_breakout_gone(db):
    row, cfg = store.get_active(db)
    t0 = ist(2026, 10, 7, 10, 0)
    apply_result(db, _result("BREAKOUT_DETECTED", t0), cfg, row.id, row.version, t0)
    r = _result("WATCHING", t0 + timedelta(minutes=20))
    r.breakout = None
    _, state, note = apply_result(db, r, cfg, row.id, row.version, t0)
    assert state == "EXPIRED" and db.scalar(select(SignalSetup)).state == "EXPIRED"


def test_api_scan_config_and_health(db):
    from app.main import app
    c = TestClient(app)
    r = c.post("/api/scans/run")
    assert r.status_code == 200 and {x["symbol"] for x in r.json()["results"]} == {"NIFTY", "SENSEX"}
    latest = c.get("/api/scans/latest").json()["symbols"]["NIFTY"]
    assert latest["gate1"] in ("PASS", "FAIL", "WAIT")
    assert latest["details"]["commentary"]["headline"]
    assert c.get("/api/scans/history").json()["items"][0]["commentary"]["headline"]
    cfg = c.get("/api/config").json()
    assert cfg["version"] == "1.0.0" and cfg["schema"][0]["key"] == "five_min"
    params = cfg["params"]
    params["five_min"]["compression_threshold"] = 22
    r = c.put("/api/config", json={"params": params})
    assert r.json()["version"] == "1.0.1" and r.json()["changed"][0]["key"] == "compression_threshold"
    params["vix"]["min_vix"] = 50
    assert c.put("/api/config", json={"params": params}).status_code == 422
    assert c.post("/api/config/reset").json()["version"] == "1.0.2"
    h = c.get("/api/system/health").json()
    assert h["provider"] == "mock" and len(h["feeds"]) == 5
    assert c.get("/api/performance/summary").status_code == 200
    assert c.get("/api/performance/analytics").status_code == 200
    assert c.get("/api/signals/active").status_code == 200
    assert c.get("/api/signals/history").json()["total"] >= 0
    hist = c.get("/api/scans/history?symbol=NIFTY").json()
    assert hist["total"] >= 1 and hist["items"][0]["config_version"] == "1.0.0"


def test_kite_callback_paths_exist(db):
    from app.main import app
    paths = {r.path for r in app.routes}
    assert {"/auth/callback", "/api/auth/callback", "/api/system/callback"} <= paths


def test_kite_session_is_valid_for_issue_day_only(monkeypatch):
    from datetime import date
    from app.core.settings import Settings
    from app.market import providers
    p = providers.KiteProvider(Settings(kite_api_key="x"), access_token="tok")
    assert p.is_connected()
    monkeypatch.setattr(providers, "_today_ist", lambda: date(2099, 1, 1))  # next day: token expired
    assert not p.is_connected()
    p.set_token(None)
    assert not p.is_connected()

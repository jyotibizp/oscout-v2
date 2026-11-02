from datetime import date, timedelta

from sqlalchemy import func, select

from app.core.clock import as_utc, session_open
from app.db.models import MarketCandle, ScanResult, ScanRun, SignalEvent, SignalSetup, Trade
from app.db.session import Base, SessionLocal, reset_engine
from app.market.factory import set_provider
from app.market.providers import MockProvider
from app.market.symbols import TRADABLE
from app.scanner import gaps
from app.scanner.service import ingest_all, run_scan
from app.strategy import store
from tests.conftest import client_at, ist

DAY = date(2026, 10, 7)
NOW = ist(2026, 10, 7, 15, 40)
STEP = timedelta(minutes=5)


def _candles():
    t = as_utc(session_open(DAY))
    return [t + i * STEP for i in range(75)]


def _cover(db, skip):
    """Fake AUTO coverage: one scan_runs row per candle except `skip` (detection only reads scan_runs)."""
    row, _ = store.get_active(db)
    for c in _candles():
        if c not in skip:
            db.add(ScanRun(trigger="AUTO", candle_ts=c, dedupe_key=f"AUTO:{c.isoformat()}", started_at=c, status="OK",
                           config_id=row.id, config_version=row.version))
    db.commit()


def _ingest(db, p):
    ingest_all(db, p, store.get_active(db)[1], NOW)


def test_detects_interior_and_latest_blocks(db):
    p = MockProvider()
    _ingest(db, p)
    c = _candles()
    _cover(db, set(c[9:15]) | set(c[69:]))  # 10:00-10:25 interior, 15:00-15:25 latest
    out = gaps.find(db, DAY, DAY, NOW)
    assert out["total_missing"] == 12
    assert [(b["candles"], b["type"], b["data"]) for b in out["blocks"]] == [(6, "INTERIOR", "FULL"), (6, "LATEST", "FULL")]
    assert out["days"] == [{"date": "2026-10-07", "expected": 75, "missing": 12}]


def test_no_data_day_is_not_a_gap(db):
    out = gaps.find(db, DAY, DAY, NOW)  # nothing ingested: holiday-like
    assert out["blocks"] == [] and out["no_data_days"] == ["2026-10-07"]


def test_interior_fill_is_record_only_and_dedupes(db):
    p = MockProvider()
    _ingest(db, p)
    c = _candles()
    _cover(db, set(c[9:15]))
    before = [db.scalar(select(func.count()).select_from(m)) for m in (SignalSetup, SignalEvent, Trade)]
    bid = gaps.find(db, DAY, DAY, NOW)["blocks"][0]["id"]
    res = gaps.fill(db, p, [bid], NOW)
    assert res == [{"id": bid, "status": "FILLED", "mode": "RECORD_ONLY", "scans": 6, "signals": 0}]
    runs = db.scalars(select(ScanRun).where(ScanRun.trigger == "BACKFILL").order_by(ScanRun.candle_ts)).all()
    assert len(runs) == 6 and [r.candle_ts.replace(tzinfo=None) for r in runs] == [x.replace(tzinfo=None) for x in c[9:15]]
    results = db.scalars(select(ScanResult).where(ScanResult.scan_run_id.in_([r.id for r in runs]))).all()
    assert len(results) == 6 * len(TRADABLE) and all(r.final_result == "NO_SIGNAL" for r in results)
    assert all(r.setup_id is None for r in results)
    assert [db.scalar(select(func.count()).select_from(m)) for m in (SignalSetup, SignalEvent, Trade)] == before
    assert gaps.find(db, DAY, DAY, NOW)["blocks"] == []
    assert gaps.fill(db, p, [bid], NOW)[0]["status"] == "SKIPPED"  # filling twice is a no-op


def _setups(db):
    return [(s.direction, s.breakout_ts, s.signal_ts, s.state, s.exit_ts, s.exit_reason)
            for s in db.scalars(select(SignalSetup).order_by(SignalSetup.breakout_ts))]


def _fresh(path):
    engine = reset_engine(f"sqlite:///{path}")
    import app.db.models  # noqa: F401
    Base.metadata.create_all(engine)
    return SessionLocal()


def test_latest_fill_matches_an_unbroken_day(tmp_path):
    p = MockProvider()
    set_provider(p)
    c = _candles()
    a = _fresh(tmp_path / "a.db")  # unbroken: AUTO on every candle
    _ingest(a, p)
    for t in c:
        run_scan(a, p, "AUTO", t + STEP + timedelta(seconds=20), ingest=False)
    want = _setups(a)
    assert any(x[2] for x in want), "mock day should produce at least one signal"
    a.close()

    b = _fresh(tmp_path / "b.db")  # scanner down from 13:00, gap filled after the close
    _ingest(b, p)
    for t in c[:45]:
        run_scan(b, p, "AUTO", t + STEP + timedelta(seconds=20), ingest=False)
    blk = gaps.find(b, DAY, DAY, NOW)["blocks"]
    assert [(x["candles"], x["type"]) for x in blk] == [(30, "LATEST")]
    res = gaps.fill(b, p, [blk[0]["id"]], NOW)
    assert res[0]["mode"] == "FULL" and res[0]["scans"] == 30
    assert _setups(b) == want
    late = gaps.late_setup_ids(b)
    sig_after = {s.id for s in b.scalars(select(SignalSetup).where(SignalSetup.signal_ts >= c[45]))}
    assert late == sig_after and late, "the gap should contain a signal"
    b.close()


def test_gap_api(db):
    p = MockProvider()
    _ingest(db, p)
    c = _candles()
    _cover(db, set(c[69:]))
    cl = client_at("127.0.0.1")
    r = cl.get("/api/scans/gaps", params={"from": "2026-10-07", "to": "2026-10-07"})
    assert r.status_code == 200 and r.json()["blocks"][0]["type"] in ("LATEST", "INTERIOR")
    assert client_at("100.64.0.9").post("/api/scans/gaps/fill", json={"blocks": []}).status_code == 403


def test_manual_scan_inside_a_gap_makes_it_interior(db):
    p = MockProvider()
    _ingest(db, p)
    c = _candles()
    _cover(db, set(c[69:]))
    run_scan(db, p, "MANUAL", c[74] + STEP + timedelta(seconds=20), ingest=False)
    assert [b["type"] for b in gaps.find(db, DAY, DAY, NOW)["blocks"]] == ["INTERIOR"]


def test_index_without_candles_that_day_does_not_blank_the_data_check(db):
    p = MockProvider()
    _ingest(db, p)
    db.query(MarketCandle).filter(MarketCandle.symbol == "BANKNIFTY").delete()  # added later: no history yet
    db.commit()
    c = _candles()
    _cover(db, set(c[9:12]))
    assert [b["data"] for b in gaps.find(db, DAY, DAY, NOW)["blocks"]] == ["FULL"]


def test_history_and_latest_follow_candle_order_after_a_fill(db):
    p = MockProvider()
    set_provider(p)
    _ingest(db, p)
    c = _candles()
    for t in c[:6] + c[8:10]:
        run_scan(db, p, "AUTO", t + STEP + timedelta(seconds=20), ingest=False)
    bid = gaps.find(db, DAY, DAY, ist(2026, 10, 7, 10, 6))["blocks"][0]["id"]
    gaps.fill(db, p, [bid], ist(2026, 10, 7, 10, 6))  # 09:45-09:50 written last
    cl = client_at("127.0.0.1")
    items = cl.get("/api/scans/history", params={"symbol": "NIFTY"}).json()["items"]
    ts = [i["candle_ts"] for i in items]
    assert ts == sorted(ts, reverse=True) and len(ts) == 10
    assert cl.get("/api/scans/latest").json()["symbols"]["NIFTY"]["candle_ts"] == ts[0]

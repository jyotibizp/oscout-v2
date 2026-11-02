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


def test_interior_fill_without_signals_changes_nothing_and_dedupes(db):
    p = MockProvider()
    _ingest(db, p)
    c = _candles()
    _cover(db, set(c[9:15]))
    before = [db.scalar(select(func.count()).select_from(m)) for m in (SignalSetup, SignalEvent, Trade)]
    bid = gaps.find(db, DAY, DAY, NOW)["blocks"][0]["id"]
    res = gaps.fill(db, p, [bid], NOW)
    assert res == [{"id": bid, "status": "FILLED", "mode": "REPLAY", "scans": 6, "signals": 0, "blocked": 0}]
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


def test_scans_on_a_stale_feed_are_gaps_and_a_fill_rescans_them_once(db):
    p = MockProvider()
    set_provider(p)
    _ingest(db, p)
    c = _candles()
    for t in c[:6]:
        run_scan(db, p, "AUTO", t + STEP + timedelta(seconds=20), ingest=False)
    db.query(MarketCandle).filter(MarketCandle.ts > c[5]).delete()  # feed stopped after 09:40 (token not refreshed)
    db.commit()
    now = ist(2026, 10, 7, 10, 1)
    for t in c[6:9]:
        run, _ = run_scan(db, p, "AUTO", t + STEP + timedelta(seconds=20), ingest=False)
        assert {r.candle_ts.replace(tzinfo=None) for r in db.scalars(select(ScanResult).where(ScanResult.scan_run_id == run.id))} \
            == {c[5].replace(tzinfo=None)}  # scanned 09:40 again
    blocks = gaps.find(db, DAY, DAY, now)["blocks"]
    assert [(b["candles"], b["type"], b["data"]) for b in blocks] == [(3, "LATEST", "NONE")]
    _ingest(db, p)  # token refreshed: candles back
    res = gaps.fill(db, p, [blocks[0]["id"]], now)
    assert res[0]["status"] == "FILLED" and res[0]["scans"] == 3 and res[0]["mode"] == "FULL"
    assert gaps.find(db, DAY, DAY, now)["blocks"] == []
    assert gaps.fill(db, p, [blocks[0]["id"]], now)[0]["status"] == "SKIPPED"
    keys = db.scalars(select(ScanRun.dedupe_key).where(ScanRun.trigger == "BACKFILL")).all()
    assert sorted(keys) == sorted(f"BACKFILL:{t.isoformat()}" for t in c[6:9])


def _trades(db, since):
    return [(s.symbol, s.direction, s.signal_ts, s.exit_ts, s.exit_reason, s.exit_price)
            for s in db.scalars(select(SignalSetup).where(SignalSetup.signal_ts >= since).order_by(SignalSetup.signal_ts))]


def _afternoon_gap(path, p):
    """Live AUTO scans until 13:00 and one at 15:25: the afternoon is an Interior block."""
    c = _candles()
    b = _fresh(path)
    _ingest(b, p)
    for t in c[:45]:
        run_scan(b, p, "AUTO", t + STEP + timedelta(seconds=20), ingest=False)
    run_scan(b, p, "AUTO", c[74] + STEP + timedelta(seconds=20), ingest=False)
    blk = gaps.find(b, DAY, DAY, NOW)["blocks"]
    assert [x["type"] for x in blk] == ["INTERIOR"]
    return b, blk[0]["id"]


def test_interior_fill_replays_late_trades_append_only(tmp_path):
    """#23: an Interior fill turns the afternoon's signals into LATE trades that match an unbroken day."""
    p = MockProvider()
    set_provider(p)
    c = _candles()
    a = _fresh(tmp_path / "a.db")
    _ingest(a, p)
    for t in c:
        run_scan(a, p, "AUTO", t + STEP + timedelta(seconds=20), ingest=False)
    want = _trades(a, c[45])
    assert want, "mock afternoon should hold a signal"
    a.close()

    b, bid = _afternoon_gap(tmp_path / "b.db", p)
    live = {s.id: (s.state, s.exit_ts) for s in b.scalars(select(SignalSetup))}
    res = gaps.fill(b, p, [bid], NOW)[0]
    assert res["mode"] == "REPLAY" and res["signals"] == len(want)
    assert {s.id: (s.state, s.exit_ts) for s in b.scalars(select(SignalSetup)) if s.id in live} == live  # untouched
    assert _trades(b, c[45]) == want
    late = gaps.late_setup_ids(b)
    new = [s for s in b.scalars(select(SignalSetup)) if s.id not in live]
    assert new and {s.id for s in new} <= late
    assert all(s.state == "EXIT_TRIGGERED" for s in new if s.signal_ts)
    assert all(t.status == "CLOSED" for t in b.scalars(select(Trade).where(Trade.setup_id.in_([s.id for s in new]))))
    assert gaps.unreplayed(b) == []
    b.close()


def test_late_signal_is_rejected_while_a_trade_was_open(tmp_path):
    p = MockProvider()
    set_provider(p)
    c = _candles()
    b, bid = _afternoon_gap(tmp_path / "b.db", p)
    first = c[45]
    row, _ = store.get_active(b)
    blockers = [SignalSetup(symbol=sym, direction="CALL", state="EXIT_TRIGGERED", breakout_ts=first - STEP,
                            detected_at=first, config_id=row.id, config_version=row.version, signal_ts=first, breakout={},
                            entry_price=1.0, stop_price=0.5, target_price=2.0, exit_ts=c[74], exit_reason="TEST")
                for sym in TRADABLE]
    b.add_all(blockers)
    b.commit()
    ids = {x.id for x in blockers}
    res = gaps.fill(b, p, [bid], NOW)[0]
    late = [s for s in b.scalars(select(SignalSetup).where(SignalSetup.breakout_ts >= first)) if s.id not in ids]
    assert res["signals"] == 0 and res["blocked"] > 0
    assert late and all(s.signal_ts is None and s.state == "REJECTED" for s in late)
    assert all(b.get(SignalSetup, i).exit_reason == "TEST" for i in ids)
    b.close()


def test_open_late_signal_never_blocks_live(db):
    from app.signals.lifecycle import live_open
    row, _ = store.get_active(db)
    s = SignalSetup(symbol="NIFTY", direction="CALL", state="ACTIVE", breakout_ts=NOW, detected_at=NOW,
                    config_id=row.id, config_version=row.version, signal_ts=NOW, entry_price=1.0, breakout={},
                    signal_context={"late": True})
    db.add(s)
    db.commit()
    assert live_open(db, "NIFTY") is None
    s.signal_context = {}
    db.commit()
    assert live_open(db, "NIFTY").id == s.id


def test_replay_catches_up_record_only_fills(tmp_path, monkeypatch):
    """Blocks filled record-only before #23 show as missed; the catch-up replays them once, old rows untouched."""
    from app.api.serializers import LATE_NOTE
    from app.scanner import service
    p = MockProvider()
    set_provider(p)
    c = _candles()
    b, bid = _afternoon_gap(tmp_path / "b.db", p)
    monkeypatch.setattr(service, "create_late_signal", lambda db, res, *a: (None, res.state, LATE_NOTE))
    gaps.fill(b, p, [bid], NOW)
    monkeypatch.undo()
    before = b.scalar(select(func.count()).select_from(SignalSetup))
    pending = gaps.unreplayed(b)
    cl = client_at("127.0.0.1")
    assert pending and cl.get("/api/scans/gaps", params={"from": DAY.isoformat(), "to": DAY.isoformat()}).json()["replay_pending"] == len(pending)
    old = {r.id: (r.state, r.final_result, r.setup_id) for r in b.scalars(select(ScanResult))}
    out = cl.post("/api/scans/gaps/replay").json()
    assert out["breakouts"] == len(pending) and out["signals"] + out["blocked"] + out["skipped"] == len(pending)
    assert out["signals"] > 0 and b.scalar(select(func.count()).select_from(SignalSetup)) > before
    b.expire_all()
    assert {r.id: (r.state, r.final_result, r.setup_id) for r in b.scalars(select(ScanResult))} == old  # append-only
    assert gaps.unreplayed(b) == [] and cl.post("/api/scans/gaps/replay").json()["breakouts"] == 0
    items = cl.get("/api/scans/history", params={"missed": "true"}).json()["items"]
    assert items and all(i.get("replayed") for i in items)
    b.close()

"""#24 account trade log: CSV import, Kite pull, round trips, charges, signal match, overtrading stats."""
from datetime import timedelta

from app.account import analysis, ingest
from app.db.models import AccountOrder, AccountTrade, SignalSetup, StrategyConfiguration, Trade
from tests.conftest import client_at, ist

HEAD = "symbol,isin,trade_date,exchange,segment,series,trade_type,auction,quantity,price,trade_id,order_id,order_execution_time,expiry_date\n"


def row(sym, side, qty, px, tid, t, ex="NFO", oid=None):
    return f"{sym},,2026-10-06,{ex},FO,,{side},false,{qty},{px},{tid},{oid or 'o' + str(tid)},{t},2026-10-07\n"


def test_parse_symbol():
    assert ingest.parse_symbol("NIFTY2511424500CE") == ("NIFTY", "CE")
    assert ingest.parse_symbol("NIFTY25NOV24500PE") == ("NIFTY", "PE")
    assert ingest.parse_symbol("BANKNIFTY25NOV51000CE") == ("BANKNIFTY", "CE")
    assert ingest.parse_symbol("SENSEX25N1381000PE") == ("SENSEX", "PE")
    assert ingest.parse_symbol("NIFTY25NOVFUT") == ("NIFTY", "FUT")
    assert ingest.parse_symbol("RELIANCE") is None


def test_csv_import_dedupes_and_skips_equity(db):
    csv = HEAD + row("NIFTY25O0725000CE", "buy", 75, 100, 1, "2026-10-06T09:20:00") \
        + row("NIFTY25O0725000CE", "sell", 75, 110, 2, "2026-10-06T09:40:00") \
        + "INFY,INE009A01021,2026-10-06,NSE,EQ,EQ,buy,false,1,1500,3,o3,2026-10-06T10:00:00,\n"
    assert ingest.import_csv(db, csv)["added"] == 2
    again = ingest.import_csv(db, csv)
    assert again["added"] == 0 and again["skipped"] == 3
    t = db.query(AccountTrade).order_by(AccountTrade.id).first()
    assert t.fill_ts == ist(2026, 10, 6, 9, 20) and t.underlying == "NIFTY" and t.instrument == "CE"


def test_csv_rejects_other_files(db):
    import pytest
    with pytest.raises(ValueError):
        ingest.import_csv(db, "a,b\n1,2\n")


def fills(*spec):
    out = []
    for i, (side, q, px, t) in enumerate(spec):
        out.append(AccountTrade(trade_id=str(i), order_id=f"o{i}", exchange="NFO", tradingsymbol="NIFTY25O0725000CE",
                                underlying="NIFTY", instrument="CE", side=side, quantity=q, price=px, fill_ts=t, source="CSV"))
    return out


def test_round_trip_scale_in_out_and_avg_down():
    t0 = ist(2026, 10, 6, 9, 20)
    rts = analysis.build_round_trips(fills(("BUY", 75, 100, t0), ("BUY", 75, 90, t0 + timedelta(minutes=1)),
                                           ("SELL", 75, 95, t0 + timedelta(minutes=5)), ("SELL", 75, 105, t0 + timedelta(minutes=9))))
    assert len(rts) == 1
    r = rts[0]
    assert r.closed and r.side == "LONG" and r.qty == 150 and r.avg_down and r.view == "CALL"
    assert r.sell_value - r.buy_value == 75 * (95 + 105 - 100 - 90)


def test_round_trip_cross_zero_splits():
    t0 = ist(2026, 10, 6, 9, 20)
    rts = analysis.build_round_trips(fills(("BUY", 75, 100, t0), ("SELL", 150, 110, t0 + timedelta(minutes=2)),
                                           ("BUY", 75, 105, t0 + timedelta(minutes=4))))
    assert [(r.side, r.closed) for r in rts] == [("LONG", True), ("SHORT", True)]
    assert rts[1].view == "PUT"


def test_charges_estimate():
    f = fills(("SELL", 75, 100, ist(2026, 10, 6, 10, 0)))[0]
    c = analysis.fill_charges(f)
    assert round(c["stt"], 2) == round(7500 * 0.0015, 2)   # after 1 Apr 2026
    f.fill_ts = ist(2026, 3, 2, 10, 0)
    assert round(analysis.fill_charges(f)["stt"], 2) == 7.5


def _signal(db, entry, exit_):
    cfg = StrategyConfiguration(version="t", params={}, is_active=False)
    db.add(cfg)
    db.flush()
    s = SignalSetup(symbol="NIFTY", direction="CALL", state="EXITED", breakout_ts=entry, detected_at=entry,
                    config_id=cfg.id, config_version="t", breakout={})
    db.add(s)
    db.flush()
    db.add(Trade(setup_id=s.id, symbol="NIFTY", direction="CALL", status="CLOSED", entry_ts=entry, entry_price=1,
                 exit_ts=exit_, exit_price=2, r_multiple=0.5, config_version="t"))
    db.commit()


def test_stats_overtrading(db):
    d = "2026-10-06T"
    csv = HEAD
    # 4 round trips: win, loss, quick re-entry loss (2m after), loss
    plan = [("09:20", "09:30", 100, 120), ("09:40", "09:50", 100, 90), ("09:52", "09:53", 100, 80), ("10:30", "10:40", 100, 95)]
    tid = 0
    for a, b, p1, p2 in plan:
        csv += row("NIFTY25O0725000CE", "buy", 75, p1, tid, d + a + ":00")
        csv += row("NIFTY25O0725000CE", "sell", 75, p2, tid + 1, d + b + ":00")
        tid += 2
    ingest.import_csv(db, csv)
    _signal(db, ist(2026, 10, 6, 9, 15), ist(2026, 10, 6, 9, 35))
    st = analysis.stats(db)
    assert st["totals"]["trades"] == 4
    s1 = next(x for x in st["stop_after"] if x["n"] == 1)
    assert s1["vs_actual"] > 0                       # stopping after the winner beats the day
    rows = analysis.round_trips(db)
    assert rows[0]["on_signal"] and not rows[1]["on_signal"]
    assert "QUICK_REENTRY" in rows[2]["flags"] and "SCALP" in rows[2]["flags"]
    assert st["system"]["signals"] == 1 and st["system"]["on_signal"]["trades"] == 1
    assert st["gave_back"]["days"] == 1 and st["gave_back"]["green_to_red"] == 1
    assert st["tilt"]["after_loss_n"] == 2
    assert [b["bucket"] for b in st["by_trade_number"]] == ["1", "2", "3", "4"]


class FakeKite:
    name = "kite"

    def is_connected(self):
        return True

    def account_trades(self):
        from datetime import datetime
        return [{"trade_id": "9", "order_id": "A", "exchange": "NFO", "tradingsymbol": "NIFTY25O0725000PE",
                 "transaction_type": "BUY", "quantity": 75, "average_price": 50.0, "fill_timestamp": datetime(2026, 10, 6, 11, 0)}]

    def account_orders(self):
        from datetime import datetime
        base = {"exchange": "NFO", "tradingsymbol": "NIFTY25O0725000PE", "transaction_type": "BUY", "quantity": 75}
        return [{**base, "order_id": "A", "status": "COMPLETE", "order_timestamp": datetime(2026, 10, 6, 11, 0), "filled_quantity": 75},
                {**base, "order_id": "B", "status": "CANCELLED", "order_timestamp": datetime(2026, 10, 6, 11, 0, 20)}]

    def order_history(self, oid):
        return [{"status": "OPEN"}, {"status": "MODIFIED"}, {"status": "MODIFIED"}]


def test_sync_and_order_stats(db):
    assert ingest.sync(db, FakeKite(), final=True) == {"trades_added": 1, "orders": 2}
    assert ingest.sync(db, FakeKite())["trades_added"] == 0
    assert db.query(AccountOrder).filter_by(order_id="A").one().modifications == 2
    o = analysis.order_stats(db, None, None, None)
    assert o["placed"] == 2 and o["cancelled"] == 1 and o["shortest_gap_sec"] == 20 and o["modified"] == 4


def test_account_api_is_admin_only(db):
    assert client_at("100.64.0.5").get("/api/account/stats").status_code == 403
    r = client_at("127.0.0.1").post("/api/account/import", content=HEAD + row("NIFTY25O0725000CE", "buy", 75, 100, 1, "2026-10-06T09:20:00"))
    assert r.status_code == 200 and r.json()["added"] == 1
    st = client_at("127.0.0.1").get("/api/account/stats").json()
    assert st["totals"]["open"] == 1 and st["totals"]["trades"] == 0
    assert client_at("127.0.0.1").get("/api/account/trades").json()[0]["status"] == "OPEN"

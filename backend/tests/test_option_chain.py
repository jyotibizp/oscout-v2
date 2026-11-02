import math
from datetime import date, datetime

from app.core.clock import IST
from app.market.providers import MockProvider
from app.options import chain, greeks as bs
from tests.conftest import client_at


def test_iv_roundtrip_and_put_call_delta():
    t = 5 / 365
    p = bs.price(22500, 22600, t, 0.15, True)
    assert abs(bs.implied_vol(p, 22500, 22600, t, True) - 0.15) < 1e-4
    c, q = bs.greeks(22500, 22500, t, 0.15, True), bs.greeks(22500, 22500, t, 0.15, False)
    assert abs((c["delta"] - q["delta"]) - 1) < 1e-9 and c["theta"] < 0 and c["gamma"] > 0 and c["vega"] > 0


def test_build_marks_atm_and_signal_strike():
    raw = MockProvider().option_chain("NIFTY", 10)
    out = chain.build(raw, "CALL")
    strikes = [r["strike"] for r in out["rows"]]
    assert len(strikes) == 21 and strikes == sorted(strikes) and strikes[1] - strikes[0] == 50
    assert abs(out["atm"] - out["spot"]) <= 25
    ce = {r["strike"]: r["ce"] for r in out["rows"]}
    assert out["signal"]["option"] == "CE" and out["signal"]["strike"] < out["atm"]  # 0.70 delta call is in the money
    assert abs(ce[out["signal"]["strike"]]["delta"] - 0.70) < 0.15
    assert all(r["pe"]["oi_chg_pct"] is not None for r in out["rows"])


def test_mock_expiries():
    m = MockProvider()
    assert m._expiry("NIFTY", date(2026, 11, 2)) == date(2026, 11, 3)        # Tuesday weekly
    assert m._expiry("SENSEX", date(2026, 11, 2)) == date(2026, 11, 5)       # Thursday weekly
    assert m._expiry("BANKNIFTY", date(2026, 11, 2)) == date(2026, 11, 24)   # last Tuesday of month
    assert m._expiry("BANKNIFTY", date(2026, 11, 25)) == date(2026, 12, 29)


def test_years_to_expiry_floor():
    assert chain.years_to_expiry(date(2026, 11, 3), datetime(2026, 11, 3, 16, 0, tzinfo=IST)) == 60 / bs.YEAR


def test_chain_endpoint(db):
    c = client_at("127.0.0.1")
    r = c.get("/api/options/chain?symbol=sensex")
    assert r.status_code == 200
    body = r.json()
    assert body["symbol"] == "SENSEX" and len(body["rows"]) == 21 and body["signal"] is None
    assert body["rows"][0]["ce"]["iv"] > 0
    assert c.get("/api/options/chain?symbol=INDIAVIX").status_code == 404


def test_banknifty_is_testing_and_has_a_monthly_chain(db):
    c = client_at("127.0.0.1")
    assert {"symbol": "BANKNIFTY", "testing": True} in c.get("/api/market/symbols").json()
    body = c.get("/api/options/chain?symbol=BANKNIFTY").json()
    assert body["rows"][1]["strike"] - body["rows"][0]["strike"] == 100


def test_deep_itm_call_below_bs_floor_still_gets_greeks():
    t = chain.years_to_expiry(date(2026, 11, 3), datetime(2026, 11, 2, 15, 0, tzinfo=IST))
    put = round(bs.price(25600, 25000, t, 0.16, False), 2)
    raw = {"symbol": "NIFTY", "expiry": date(2026, 11, 3), "spot": 25600.0,
           "rows": [{"strike": 25000.0, "ce": {"ltp": 598.0, "prev_close": 600.0, "oi": 1e5, "oi_prev": 1e5},
                     "pe": {"ltp": put, "prev_close": put, "oi": 1e5, "oi_prev": 1e5}}]}
    assert bs.implied_vol(598.0, 25600, 25000, t, True) is None  # below the floor on its own
    row = chain.build(raw, now=datetime(2026, 11, 2, 15, 0, tzinfo=IST))["rows"][0]
    assert abs(row["ce"]["iv"] - 16) < 0.5 and row["ce"]["delta"] > 0.9 and row["pe"]["iv"] == row["ce"]["iv"]


def test_itm_calls_get_greeks_when_options_imply_an_underlying_below_spot():
    # 2 Nov 2026 close: NIFTY spot 23440.8 but the chain priced off ~23345, so ITM calls traded below spot intrinsic
    now, expiry, under = datetime(2026, 11, 2, 15, 30, tzinfo=IST), date(2026, 11, 3), 23345.0
    t = chain.years_to_expiry(expiry, now)
    q = lambda k, call: {"ltp": round(bs.price(under, k, t, 0.12, call), 2), "prev_close": None, "oi": 1, "oi_prev": None}
    rows = [{"strike": k, "ce": q(k, True), "pe": q(k, False)} for k in range(22950, 24000, 50)]
    out = chain.build({"symbol": "NIFTY", "expiry": expiry, "spot": 23440.8, "rows": rows}, now=now)
    assert abs(out["forward"] - under * math.exp(bs.RISK_FREE * t)) < 1
    atmish = [r for r in out["rows"] if abs(r["strike"] - under) <= 300]
    assert all(abs(r[s]["iv"] - 12) < 0.5 and r[s]["delta"] is not None for r in atmish for s in ("ce", "pe"))
    assert all(r["ce"]["delta"] is not None for r in out["rows"] if r["strike"] < under)

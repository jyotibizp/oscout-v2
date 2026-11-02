"""Option chain for one index: nearest expiry, ATM ±N strikes, LTP / OI / OI change, IV and Greeks from Black-Scholes.

Providers return raw quotes (`option_chain(symbol, strikes_each_side)`); this module adds IV, Greeks, ATM and the
signal strike so Kite and Mock look the same to the UI.
"""
from datetime import datetime, time

from app.core.clock import IST, now_utc
from app.options import greeks as bs

TARGET_DELTA = 0.70


def years_to_expiry(expiry, now: datetime | None = None) -> float:
    end = datetime.combine(expiry, time(15, 30), tzinfo=IST)
    secs = (end - (now or now_utc())).total_seconds()
    return max(secs, 60) / bs.YEAR


def _iv(q: dict | None, spot: float, strike: float, t: float, call: bool) -> float | None:
    return bs.implied_vol(q["ltp"], spot, strike, t, call) if q and q.get("ltp") else None


def _side(q: dict | None, spot: float, strike: float, t: float, call: bool, iv: float | None) -> dict | None:
    if not q:
        return None
    ltp, prev, oi, oi_prev = q.get("ltp"), q.get("prev_close"), q.get("oi"), q.get("oi_prev")
    out = {"ltp": ltp, "chg_pct": (ltp - prev) / prev * 100 if ltp is not None and prev else None,
           "oi": oi, "oi_chg_pct": (oi - oi_prev) / oi_prev * 100 if oi is not None and oi_prev else None,
           "iv": None, "delta": None, "theta": None, "gamma": None, "vega": None}
    if iv:
        out.update(iv=iv * 100, **bs.greeks(spot, strike, t, iv, call))
    return out


def _strike_iv(r: dict, spot: float, t: float) -> float | None:
    """One IV per strike, from the out-of-the-money side (liquid, priced on volatility). Deep ITM premiums often trade
    below Black-Scholes' floor (spot - strike·e^-rT: dividends, futures discount, stale last trade), so their own IV is
    undefined; using the OTM side's IV gives them Greeks, the way broker chains do. Falls back to the other side."""
    k = r["strike"]
    ce, pe = _iv(r.get("ce"), spot, k, t, True), _iv(r.get("pe"), spot, k, t, False)
    otm, itm = (ce, pe) if k >= spot else (pe, ce)
    return otm or itm


def build(raw: dict, signal_direction: str | None = None, now: datetime | None = None) -> dict:
    """raw = {symbol, expiry (date), spot, prev_spot?, rows: [{strike, ce: quote|None, pe: quote|None}]}."""
    spot, t = raw["spot"], years_to_expiry(raw["expiry"], now)
    rows = sorted(raw["rows"], key=lambda r: r["strike"])
    out_rows = []
    for r in rows:
        iv = _strike_iv(r, spot, t)
        out_rows.append({"strike": r["strike"], "ce": _side(r.get("ce"), spot, r["strike"], t, True, iv),
                         "pe": _side(r.get("pe"), spot, r["strike"], t, False, iv)})
    atm = min((r["strike"] for r in rows), key=lambda k: abs(k - spot)) if rows else None
    signal = None
    if signal_direction in ("CALL", "PUT"):
        side = "ce" if signal_direction == "CALL" else "pe"
        cands = [(abs(abs(r[side]["delta"]) - TARGET_DELTA), r["strike"]) for r in out_rows if r[side] and r[side]["delta"] is not None]
        if cands:
            signal = {"direction": signal_direction, "option": side.upper(), "strike": min(cands)[1], "target_delta": TARGET_DELTA}
    return {"symbol": raw["symbol"], "expiry": raw["expiry"].isoformat(), "spot": spot, "atm": atm,
            "days_to_expiry": round(t * 365, 2), "rows": out_rows, "signal": signal, "as_of": (now or now_utc()).isoformat()}

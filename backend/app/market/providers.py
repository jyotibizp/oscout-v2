"""Market-data providers. The strategy engine never sees a provider; only the ingestion layer does.

Contract: fetch_5m(symbol, from_utc, to_utc) -> list of {ts (aware UTC, candle START), open, high, low, close, volume}.
May include the still-forming candle; ingestion filters to completed, aligned candles.
"""
import logging
import math
import random
import threading
import time as _time
from datetime import date, datetime, timedelta
from typing import Protocol

from app.core.clock import IST, as_utc, is_weekday, session_close, session_open, to_ist
from app.core.settings import Settings
from app.market.symbols import INSTRUMENTS

log = logging.getLogger(__name__)


def _today_ist() -> date:
    from app.core.clock import now_utc
    return to_ist(now_utc()).date()


class ProviderError(Exception):
    pass


class AuthError(ProviderError):
    pass


class ProviderUnavailable(ProviderError):
    pass


class MarketDataProvider(Protocol):
    name: str

    def is_connected(self) -> bool: ...
    def fetch_5m(self, symbol: str, from_utc: datetime, to_utc: datetime) -> list[dict]: ...


class KiteProvider:
    name = "kite"

    def __init__(self, s: Settings, access_token: str | None = None):
        from kiteconnect import KiteConnect

        self.s = s
        self.kite = KiteConnect(api_key=s.kite_api_key)
        self._token = access_token or s.kite_access_token or None
        self._token_day = _today_ist() if self._token else None
        if self._token:
            self.kite.set_access_token(self._token)

    def is_connected(self) -> bool:
        """A Kite access token is valid for the IST trading day it was issued (it expires early next
        morning), and is dropped as soon as Kite rejects it."""
        return bool(self._token) and self._token_day == _today_ist()

    def login_url(self) -> str:
        return self.kite.login_url()

    def complete_login(self, request_token: str) -> dict:
        try:
            data = self.kite.generate_session(request_token, api_secret=self.s.kite_api_secret)
        except Exception as e:  # noqa: BLE001 - surface any broker failure as a login error
            raise AuthError(f"Kite login failed: {e}") from e
        self.set_token(data["access_token"])
        return data

    def set_token(self, token: str | None) -> None:
        self._token = token
        self._token_day = _today_ist() if token else None
        if token:
            self.kite.set_access_token(token)

    def _call(self, fn, *args, retries: int = 3, **kw):
        from kiteconnect import exceptions as kex

        if not self.is_connected():
            raise AuthError("Broker not connected. Use CONNECT to log in to Kite.")
        delay = 0.5
        for attempt in range(retries):
            try:
                return fn(*args, **kw)
            except kex.TokenException as e:
                self.set_token(None)  # expired / revoked: show Disconnected until the next CONNECT
                raise AuthError(f"Kite session expired or invalid: {e}") from e
            except Exception as e:  # noqa: BLE001 - network/data errors are retried
                if attempt == retries - 1:
                    raise ProviderUnavailable(f"Kite request failed: {e}") from e
                log.warning("kite call failed, retrying", extra={"ctx": {"error": str(e), "delay": delay}})
                _time.sleep(delay)
                delay *= 2

    def fetch_5m(self, symbol: str, from_utc: datetime, to_utc: datetime) -> list[dict]:
        token = INSTRUMENTS[symbol].kite_token
        out, start = [], to_ist(from_utc)
        end_all = to_ist(to_utc)
        while start <= end_all:
            end = min(start + timedelta(days=self.s.max_fetch_days), end_all)
            rows = self._call(self.kite.historical_data, token, start.replace(tzinfo=None),
                              end.replace(tzinfo=None), "5minute") or []
            for r in rows:
                out.append({"ts": as_utc(r["date"]), "open": float(r["open"]), "high": float(r["high"]),
                            "low": float(r["low"]), "close": float(r["close"]), "volume": float(r.get("volume") or 0)})
            start = end + timedelta(seconds=1)
            _time.sleep(0.35)  # historical API limit ~3 req/s
        return out

    # ---------------- option chain (#15) ----------------
    _inst_cache: dict = {}
    _prev_oi: dict = {}
    _prev_oi_pending: set = set()
    _lock = threading.Lock()

    def _instruments(self, exchange: str) -> list[dict]:
        key = (exchange, _today_ist())
        if key not in self._inst_cache:  # ~MBs; once a day per exchange
            for old in [k for k in self._inst_cache if k[1] != key[1]]:
                del self._inst_cache[old]
            self._inst_cache[key] = self._call(self.kite.instruments, exchange) or []
        return self._inst_cache[key]

    def _load_prev_oi(self, tokens: list[int], day) -> None:
        for tok in tokens:
            try:
                rows = self._call(self.kite.historical_data, tok, day - timedelta(days=10), day - timedelta(days=1), "day", oi=True) or []
                self._prev_oi[(day, tok)] = float(rows[-1].get("oi") or 0) if rows else None
            except ProviderError as e:
                log.warning("prev-day OI fetch failed", extra={"ctx": {"token": tok, "error": str(e)}})
            finally:
                with self._lock:
                    self._prev_oi_pending.discard((day, tok))
            _time.sleep(0.35)  # historical API ~3 req/s

    def option_chain(self, symbol: str, each_side: int = 10) -> dict:
        inst = INSTRUMENTS[symbol]
        if not inst.opt_exchange:
            raise ProviderError(f"No options for {symbol}")
        day = _today_ist()
        opts = [r for r in self._instruments(inst.opt_exchange)
                if r.get("name") == inst.opt_name and r.get("instrument_type") in ("CE", "PE") and r["expiry"] >= day]
        if not opts:
            raise ProviderUnavailable(f"No {symbol} options in Kite's instrument list")
        expiry = min(r["expiry"] for r in opts)
        opts = [r for r in opts if r["expiry"] == expiry]
        spot = float(self._call(self.kite.quote, [inst.quote_key])[inst.quote_key]["last_price"])
        strikes = sorted({float(r["strike"]) for r in opts})
        i = min(range(len(strikes)), key=lambda k: abs(strikes[k] - spot))
        keep = set(strikes[max(0, i - each_side): i + each_side + 1])
        picked = [r for r in opts if float(r["strike"]) in keep]
        quotes = self._call(self.kite.quote, [f"{inst.opt_exchange}:{r['tradingsymbol']}" for r in picked]) or {}
        with self._lock:  # previous-day OI: fetched once a day in the background, OI change shows once ready
            todo = [r["instrument_token"] for r in picked if (day, r["instrument_token"]) not in self._prev_oi
                    and (day, r["instrument_token"]) not in self._prev_oi_pending]
            self._prev_oi_pending.update((day, t) for t in todo)
        if todo:
            threading.Thread(target=self._load_prev_oi, args=(todo, day), daemon=True).start()
        rows: dict = {}
        for r in picked:
            q = quotes.get(f"{inst.opt_exchange}:{r['tradingsymbol']}")
            if not q:
                continue
            row = rows.setdefault(float(r["strike"]), {"strike": float(r["strike"]), "ce": None, "pe": None})
            row[r["instrument_type"].lower()] = {
                "ltp": q.get("last_price"), "prev_close": (q.get("ohlc") or {}).get("close"), "oi": q.get("oi"),
                "oi_prev": self._prev_oi.get((day, r["instrument_token"])), "tradingsymbol": r["tradingsymbol"]}
        return {"symbol": symbol, "expiry": expiry, "spot": spot, "rows": list(rows.values())}


class MockProvider:
    """Deterministic synthetic market (random walk with regime shifts) for development and tests.
    The same timestamp always produces the same candle."""
    name = "mock"
    BASE = {"NIFTY": 22500.0, "SENSEX": 74000.0, "BANKNIFTY": 51000.0, "INDIAVIX": 14.0}

    def __init__(self, seed: int = 7):
        self.seed = seed

    def is_connected(self) -> bool:
        return True

    def _day(self, symbol: str, d: date) -> list[dict]:
        rnd = random.Random(f"{self.seed}-{symbol}-{d.isoformat()}")
        drift_day = rnd.gauss(0, 1)
        base = self.BASE[symbol] * (1 + 0.002 * math.sin(d.toordinal() / 9.0) + 0.01 * math.sin(d.toordinal() / 37.0))
        vol = 0.0009 if symbol != "INDIAVIX" else 0.0015
        price = base * (1 + rnd.gauss(0, 0.0008))
        out, t = [], session_open(d)
        trend, ranging = 0.0, True
        while t < session_close(d):
            if rnd.random() < 0.04:  # regime switch: quiet range (ADX compresses) <-> directional move
                ranging = not ranging
                trend = 0.0 if ranging else rnd.choice((-1, 1)) * rnd.uniform(0.15, 0.45) * vol
            v = vol * (0.6 if ranging else 1.0)
            r = trend + rnd.gauss(drift_day * vol * 0.05, v)
            o = price
            c = o * (1 + r)
            h = max(o, c) * (1 + abs(rnd.gauss(0, vol * 0.4)))
            l_ = min(o, c) * (1 - abs(rnd.gauss(0, vol * 0.4)))
            out.append({"ts": as_utc(t), "open": round(o, 2), "high": round(h, 2), "low": round(l_, 2),
                        "close": round(c, 2), "volume": 0.0})
            price = c
            t += timedelta(minutes=5)
        return out

    def fetch_5m(self, symbol: str, from_utc: datetime, to_utc: datetime) -> list[dict]:
        out = []
        d, end = to_ist(from_utc).date(), to_ist(to_utc).date()
        while d <= end:
            if is_weekday(d):
                out += [r for r in self._day(symbol, d) if from_utc <= r["ts"] <= to_utc]
            d += timedelta(days=1)
        return out

    # synthetic chain: Black-Scholes premiums on a smile, OI peaked near ATM (calls above, puts below)
    def _expiry(self, symbol: str, d: date) -> date:
        if symbol == "SENSEX":  # weekly Thursday
            return d + timedelta(days=(3 - d.weekday()) % 7)
        tue = d + timedelta(days=(1 - d.weekday()) % 7)
        if symbol == "NIFTY":  # weekly Tuesday
            return tue
        while True:  # monthly: last Tuesday of the month
            nxt = tue + timedelta(days=7)
            if nxt.month != tue.month:
                if tue >= d:
                    return tue
            tue = nxt

    def option_chain(self, symbol: str, each_side: int = 10) -> dict:
        from app.core.clock import now_utc
        from app.options import greeks as bs
        from app.options.chain import years_to_expiry

        inst = INSTRUMENTS[symbol]
        if not inst.strike_step:
            raise ProviderError(f"No options for {symbol}")
        now = now_utc()
        bars = self.fetch_5m(symbol, now - timedelta(days=5), now)
        spot = bars[-1]["close"] if bars else self.BASE[symbol]
        day = to_ist(now).date()
        expiry = self._expiry(symbol, day)
        t = years_to_expiry(expiry, now)
        step = inst.strike_step
        atm = round(spot / step) * step
        rows = []
        for k in range(-each_side, each_side + 1):
            strike = float(atm + k * step)
            rnd = random.Random(f"{self.seed}-{symbol}-{day}-{strike}")
            iv = 0.13 + 0.6 * abs(strike / spot - 1)
            row = {"strike": strike}
            for side, call in (("ce", True), ("pe", False)):
                ltp = round(max(0.05, bs.price(spot, strike, t, iv, call)), 2)
                far = (strike - spot) / step * (1 if call else -1)  # >0 = out of the money
                oi = round(1e5 * 40 * math.exp(-((far - 2) ** 2) / 30) * rnd.uniform(0.7, 1.3) + 1e5 * rnd.uniform(0.5, 2))
                row[side] = {"ltp": ltp, "prev_close": round(ltp * rnd.uniform(0.75, 1.3), 2), "oi": oi,
                             "oi_prev": round(oi * rnd.uniform(0.7, 1.2)), "tradingsymbol": f"{symbol}{int(strike)}{side.upper()}"}
            rows.append(row)
        return {"symbol": symbol, "expiry": expiry, "spot": spot, "rows": rows}


__all__ = ["MarketDataProvider", "KiteProvider", "MockProvider", "ProviderError", "AuthError", "ProviderUnavailable", "IST"]

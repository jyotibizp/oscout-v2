"""Market-data providers. The strategy engine never sees a provider; only the ingestion layer does.

Contract: fetch_5m(symbol, from_utc, to_utc) -> list of {ts (aware UTC, candle START), open, high, low, close, volume}.
May include the still-forming candle; ingestion filters to completed, aligned candles.
"""
import logging
import math
import random
import time as _time
from datetime import date, datetime, timedelta
from typing import Protocol

from app.core.clock import IST, as_utc, is_weekday, session_close, session_open, to_ist
from app.core.settings import Settings
from app.market.symbols import INSTRUMENTS

log = logging.getLogger(__name__)


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
        if self._token:
            self.kite.set_access_token(self._token)

    def is_connected(self) -> bool:
        return bool(self._token)

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
        if token:
            self.kite.set_access_token(token)

    def _call(self, fn, *args, retries: int = 3, **kw):
        from kiteconnect import exceptions as kex

        if not self._token:
            raise AuthError("Broker not connected. Use CONNECT to log in to Kite.")
        delay = 0.5
        for attempt in range(retries):
            try:
                return fn(*args, **kw)
            except kex.TokenException as e:
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


class MockProvider:
    """Deterministic synthetic market (random walk with regime shifts) for development and tests.
    The same timestamp always produces the same candle."""
    name = "mock"
    BASE = {"NIFTY": 22500.0, "SENSEX": 74000.0, "INDIAVIX": 14.0}

    def __init__(self, seed: int = 7):
        self.seed = seed

    def is_connected(self) -> bool:
        return True

    def _day(self, symbol: str, d: date) -> list[dict]:
        rnd = random.Random(f"{self.seed}-{symbol}-{d.isoformat()}")
        drift_day = rnd.gauss(0, 1)
        base = self.BASE[symbol] * (1 + 0.002 * math.sin(d.toordinal() / 9.0) + 0.01 * math.sin(d.toordinal() / 37.0))
        vol = 0.0009 if symbol != "INDIAVIX" else 0.004
        price = base * (1 + rnd.gauss(0, 0.003))
        out, t = [], session_open(d)
        trend = 0.0
        while t < session_close(d):
            if rnd.random() < 0.08:
                trend = rnd.gauss(0, 1.2) * vol * (1 if symbol != "INDIAVIX" else -0.3)
            r = trend + rnd.gauss(drift_day * vol * 0.05, vol)
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


__all__ = ["MarketDataProvider", "KiteProvider", "MockProvider", "ProviderError", "AuthError", "ProviderUnavailable", "IST"]

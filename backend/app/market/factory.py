"""Builds the configured provider; persists the Kite access token server-side (valid for the IST trading day)."""
from datetime import date

from sqlalchemy import select

from app.core.clock import now_utc, to_ist
from app.core.settings import get_settings
from app.db.models import BrokerSession
from app.db.session import SessionLocal, get_engine

_provider = None


def _today_ist() -> date:
    return to_ist(now_utc()).date()


def load_token() -> str | None:
    get_engine()
    with SessionLocal() as db:
        row = db.scalar(select(BrokerSession).where(BrokerSession.provider == "kite"))
        if row and row.access_token and row.token_date == _today_ist():
            return row.access_token
    return None


def save_token(user_id: str | None, token: str) -> None:
    get_engine()
    with SessionLocal() as db:
        row = db.scalar(select(BrokerSession).where(BrokerSession.provider == "kite"))
        if row is None:
            row = BrokerSession(provider="kite")
            db.add(row)
        row.user_id, row.access_token, row.token_date = user_id, token, _today_ist()
        db.commit()


def get_provider():
    global _provider
    if _provider is None:
        s = get_settings()
        if s.data_provider == "kite":
            from app.market.providers import KiteProvider
            _provider = KiteProvider(s, access_token=s.kite_access_token or load_token())
        else:
            from app.market.providers import MockProvider
            _provider = MockProvider()
    elif _provider.name == "kite" and not _provider.is_connected():
        tok = load_token()
        if tok:
            _provider.set_token(tok)
    return _provider


def set_provider(p) -> None:
    """Tests / tooling: inject a provider."""
    global _provider
    _provider = p

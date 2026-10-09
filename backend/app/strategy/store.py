"""Versioned strategy configurations (immutable rows; exactly one active)."""
import logging

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.clock import now_utc
from app.db.models import StrategyConfiguration, SystemEvent
from app.strategy.config import StrategyConfig

log = logging.getLogger(__name__)


def _next_version(db: Session) -> str:
    versions = db.scalars(select(StrategyConfiguration.version)).all()
    if not versions:
        return "1.0.0"
    major, minor, patch = max(tuple(int(x) for x in v.split(".")) for v in versions)
    return f"{major}.{minor}.{patch + 1}"


def get_active(db: Session) -> tuple[StrategyConfiguration, StrategyConfig]:
    row = db.scalar(select(StrategyConfiguration).where(StrategyConfiguration.is_active.is_(True)))
    if row is None:
        row = save(db, StrategyConfig(), "Initial defaults")
    else:
        # one-time moves for configurations saved before a rule change: the old version stays as it was,
        # one new version is appended with the new behaviour
        five, atr = row.params.get("five_min") or {}, row.params.get("atr") or {}
        cfg, notes = StrategyConfig.model_validate(row.params), []
        if "compression_mode" not in five:
            cfg.five_min.compression_mode = "peak_pct"
            notes.append("Compression as % of recent 5m ADX peak")
        if "mode" not in atr:  # 60-day replay, 9 Oct 2026
            cfg.atr.mode = "warning"
            cfg.fifteen_min.min_adx_slope, cfg.fifteen_min.min_di_consistency, cfg.fifteen_min.max_adx = -1.0, 0.3, 60.0
            notes.append("ATR as warning; 15m slope > -1, DI lean 30%, 15m ADX cap 60")
        if notes:
            row = save(db, cfg, "; ".join(notes))
    return row, StrategyConfig.model_validate(row.params)


def save(db: Session, cfg: StrategyConfig, note: str | None = None) -> StrategyConfiguration:
    db.execute(update(StrategyConfiguration).values(is_active=False))
    row = StrategyConfiguration(version=_next_version(db), params=cfg.model_dump(), is_active=True, note=note)
    db.add(row)
    db.add(SystemEvent(ts=now_utc(), level="INFO", category="CONFIG",
                       message=f"Strategy configuration saved as v{row.version}", data={"note": note}))
    db.commit()
    log.info("config saved", extra={"ctx": {"version": row.version, "note": note}})
    return row


def diff(old: dict, new: dict) -> list[dict]:
    out = []
    for g, vals in new.items():
        for k, v in vals.items():
            if old.get(g, {}).get(k) != v:
                out.append({"group": g, "key": k, "old": old.get(g, {}).get(k), "new": v})
    return out

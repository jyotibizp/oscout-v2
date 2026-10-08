"""Relational schema. History tables (scan_runs, scan_results, signal_events, system_events,
strategy_configurations, market_candles) are insert-only; signal_setups / trades carry the
current lifecycle state and are updated as a setup progresses (every change is also an event)."""
from datetime import date, datetime

from sqlalchemy import (JSON, Boolean, Date, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
                        func)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base, UTCDateTime


class MarketCandle(Base):
    __tablename__ = "market_candles"
    __table_args__ = (UniqueConstraint("symbol", "timeframe", "ts", name="uq_candle"),
                      Index("ix_candle_lookup", "symbol", "timeframe", "ts"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16))
    timeframe: Mapped[str] = mapped_column(String(4))
    ts: Mapped[datetime] = mapped_column(UTCDateTime)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float, default=0)
    source: Mapped[str] = mapped_column(String(8))  # kite | mock | agg
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())


class IndicatorValue(Base):
    """Wilder ADX/DI/ATR per candle, with the smoothing state needed to extend the series exactly."""
    __tablename__ = "indicator_values"
    __table_args__ = (UniqueConstraint("symbol", "timeframe", "period", "ts", name="uq_indicator"),
                      Index("ix_indicator_lookup", "symbol", "timeframe", "period", "ts"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16))
    timeframe: Mapped[str] = mapped_column(String(4))
    period: Mapped[int] = mapped_column(Integer)
    ts: Mapped[datetime] = mapped_column(UTCDateTime)
    n: Mapped[int] = mapped_column(Integer)              # candles seen so far (warm-up counter)
    atr: Mapped[float | None] = mapped_column(Float)
    pdm: Mapped[float | None] = mapped_column(Float)     # smoothed +DM
    mdm: Mapped[float | None] = mapped_column(Float)     # smoothed -DM
    pdi: Mapped[float | None] = mapped_column(Float)
    mdi: Mapped[float | None] = mapped_column(Float)
    dx: Mapped[float | None] = mapped_column(Float)
    adx: Mapped[float | None] = mapped_column(Float)
    tr_sum: Mapped[float] = mapped_column(Float, default=0)  # warm-up accumulators
    pdm_sum: Mapped[float] = mapped_column(Float, default=0)
    mdm_sum: Mapped[float] = mapped_column(Float, default=0)
    dx_sum: Mapped[float] = mapped_column(Float, default=0)
    close: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)


class StrategyConfiguration(Base):
    __tablename__ = "strategy_configurations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(16), unique=True)
    params: Mapped[dict] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())


class ScanRun(Base):
    __tablename__ = "scan_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trigger: Mapped[str] = mapped_column(String(8))           # MANUAL | AUTO
    candle_ts: Mapped[datetime | None] = mapped_column(UTCDateTime)  # latest completed 5m candle evaluated
    dedupe_key: Mapped[str | None] = mapped_column(String(48), unique=True)  # AUTO scans: one per candle
    started_at: Mapped[datetime] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    status: Mapped[str] = mapped_column(String(12), default="RUNNING")  # OK | PARTIAL | ERROR
    config_id: Mapped[int] = mapped_column(ForeignKey("strategy_configurations.id"))
    config_version: Mapped[str] = mapped_column(String(16))
    error: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[dict | None] = mapped_column(JSON)


class ScanResult(Base):
    __tablename__ = "scan_results"
    __table_args__ = (UniqueConstraint("scan_run_id", "symbol", name="uq_scan_symbol"),
                      Index("ix_scan_results_symbol_ts", "symbol", "candle_ts"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_run_id: Mapped[int] = mapped_column(ForeignKey("scan_runs.id"))
    symbol: Mapped[str] = mapped_column(String(16))
    candle_ts: Mapped[datetime | None] = mapped_column(UTCDateTime)
    adx5: Mapped[float | None] = mapped_column(Float)
    pdi5: Mapped[float | None] = mapped_column(Float)
    mdi5: Mapped[float | None] = mapped_column(Float)
    adx15: Mapped[float | None] = mapped_column(Float)
    pdi15: Mapped[float | None] = mapped_column(Float)
    mdi15: Mapped[float | None] = mapped_column(Float)
    atr: Mapped[float | None] = mapped_column(Float)
    atr_status: Mapped[str | None] = mapped_column(String(10))
    vix: Mapped[float | None] = mapped_column(Float)
    vix_change_pct: Mapped[float | None] = mapped_column(Float)
    gate1: Mapped[str] = mapped_column(String(8))
    gate2: Mapped[str] = mapped_column(String(8))
    atr_filter: Mapped[str] = mapped_column(String(8))
    vix_filter: Mapped[str] = mapped_column(String(8))
    final_result: Mapped[str] = mapped_column(String(10))      # SIGNAL | NO_SIGNAL
    state: Mapped[str] = mapped_column(String(24))
    direction: Mapped[str | None] = mapped_column(String(4))   # CALL | PUT
    rejection_reason: Mapped[str | None] = mapped_column(String(200))
    details: Mapped[dict] = mapped_column(JSON)
    config_version: Mapped[str] = mapped_column(String(16))
    setup_id: Mapped[int | None] = mapped_column(ForeignKey("signal_setups.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())


class SignalSetup(Base):
    __tablename__ = "signal_setups"
    __table_args__ = (Index("ix_setup_symbol_state", "symbol", "state"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16))
    direction: Mapped[str] = mapped_column(String(4))
    state: Mapped[str] = mapped_column(String(24))
    breakout_ts: Mapped[datetime] = mapped_column(UTCDateTime)
    detected_at: Mapped[datetime] = mapped_column(UTCDateTime)
    config_id: Mapped[int] = mapped_column(ForeignKey("strategy_configurations.id"))
    config_version: Mapped[str] = mapped_column(String(16))
    breakout: Mapped[dict] = mapped_column(JSON)                # ADX before/at/change, DI, OHLC
    signal_ts: Mapped[datetime | None] = mapped_column(UTCDateTime)
    entry_price: Mapped[float | None] = mapped_column(Float)
    entry_atr: Mapped[float | None] = mapped_column(Float)
    stop_price: Mapped[float | None] = mapped_column(Float)
    target_price: Mapped[float | None] = mapped_column(Float)
    signal_context: Mapped[dict | None] = mapped_column(JSON)   # gate metrics at signal time
    peak_adx: Mapped[float | None] = mapped_column(Float)
    adx_declines: Mapped[int] = mapped_column(Integer, default=0)
    last_evaluated_ts: Mapped[datetime | None] = mapped_column(UTCDateTime)
    exit_ts: Mapped[datetime | None] = mapped_column(UTCDateTime)
    exit_price: Mapped[float | None] = mapped_column(Float)
    exit_reason: Mapped[str | None] = mapped_column(String(40))
    closed_reason: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now(), onupdate=func.now())


class SignalEvent(Base):
    __tablename__ = "signal_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    setup_id: Mapped[int] = mapped_column(ForeignKey("signal_setups.id"), index=True)
    event: Mapped[str] = mapped_column(String(32))
    candle_ts: Mapped[datetime | None] = mapped_column(UTCDateTime)
    price: Mapped[float | None] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(String(300))
    data: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())


class Trade(Base):
    """One closed (or open) trade per generated signal, measured on the underlying."""
    __tablename__ = "trades"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    setup_id: Mapped[int] = mapped_column(ForeignKey("signal_setups.id"), unique=True)
    symbol: Mapped[str] = mapped_column(String(16))
    direction: Mapped[str] = mapped_column(String(4))
    status: Mapped[str] = mapped_column(String(8))  # OPEN | CLOSED
    entry_ts: Mapped[datetime] = mapped_column(UTCDateTime)
    entry_price: Mapped[float] = mapped_column(Float)
    exit_ts: Mapped[datetime | None] = mapped_column(UTCDateTime)
    exit_price: Mapped[float | None] = mapped_column(Float)
    exit_reason: Mapped[str | None] = mapped_column(String(40))
    risk_points: Mapped[float | None] = mapped_column(Float)
    pnl_points: Mapped[float | None] = mapped_column(Float)
    pnl_pct: Mapped[float | None] = mapped_column(Float)
    r_multiple: Mapped[float | None] = mapped_column(Float)
    holding_minutes: Mapped[float | None] = mapped_column(Float)
    config_version: Mapped[str] = mapped_column(String(16))
    breakout_adx_change: Mapped[float | None] = mapped_column(Float)
    adx5_entry: Mapped[float | None] = mapped_column(Float)
    adx15_entry: Mapped[float | None] = mapped_column(Float)
    atr_status: Mapped[str | None] = mapped_column(String(10))
    vix_entry: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())


class SystemEvent(Base):
    __tablename__ = "system_events"
    __table_args__ = (Index("ix_system_events_ts", "ts"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(UTCDateTime)
    level: Mapped[str] = mapped_column(String(8))
    category: Mapped[str] = mapped_column(String(16))   # DATA | SCAN | SIGNAL | CONFIG | CONNECTION
    message: Mapped[str] = mapped_column(String(300))
    data: Mapped[dict | None] = mapped_column(JSON)


class BrokerSession(Base):
    __tablename__ = "broker_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(16), unique=True)
    user_id: Mapped[str | None] = mapped_column(String(32))
    access_token: Mapped[str | None] = mapped_column(String(128))
    token_date: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now(), onupdate=func.now())

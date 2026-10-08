"""Market clock. Timestamps are timezone-aware everywhere; stored as UTC, displayed in Asia/Kolkata.

A candle's timestamp is the START of its interval (09:15 = the 09:15-09:20 5m candle).
A candle is complete only once its end time has passed. Exchange holidays are not
hard-coded: a holiday simply produces no candles (data-health then reports the gap).
"""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
UTC = timezone.utc
SESSION_OPEN = time(9, 15)
SESSION_CLOSE = time(15, 30)
TIMEFRAMES = {"5m": 5, "15m": 15}


def now_utc() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def to_ist(dt: datetime) -> datetime:
    return as_utc(dt).astimezone(IST)


def as_utc(dt: datetime) -> datetime:
    """Aware -> UTC. Naive values are treated as IST (what Kite and the exchange use)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    return dt.astimezone(UTC)


def is_weekday(d: date) -> bool:
    return d.weekday() < 5


def session_open(d: date) -> datetime:
    return datetime.combine(d, SESSION_OPEN, tzinfo=IST)


def session_close(d: date) -> datetime:
    return datetime.combine(d, SESSION_CLOSE, tzinfo=IST)


def is_market_open(now: datetime) -> bool:
    n = to_ist(now)
    return is_weekday(n.date()) and session_open(n.date()) <= n < session_close(n.date())


def tf_delta(tf: str) -> timedelta:
    return timedelta(minutes=TIMEFRAMES[tf])


def is_aligned(ts: datetime, tf: str) -> bool:
    t = to_ist(ts)
    o = session_open(t.date())
    if not is_weekday(t.date()) or t < o or t >= session_close(t.date()) or t.second or t.microsecond:
        return False
    return (t - o) % tf_delta(tf) == timedelta(0)


def latest_completed_start(now: datetime, tf: str = "5m") -> datetime:
    """Start (UTC) of the most recent candle of `tf` that has fully ended at `now`.
    Walks back over weekends; holidays are not known here."""
    n = to_ist(now)
    step = tf_delta(tf)
    d = n.date()
    for _ in range(10):
        if is_weekday(d):
            o, c = session_open(d), session_close(d)
            last_start = o + ((c - o - timedelta(seconds=1)) // step) * step
            if n >= c:
                return as_utc(last_start)
            if n >= o + step:
                k = (n - o) // step
                return as_utc(o + (k - 1) * step)
        d -= timedelta(days=1)
        n = session_close(d) + timedelta(hours=1)
    raise ValueError("no session found")


def next_completion(now: datetime, interval_minutes: int = 5) -> datetime:
    """Next wall-clock instant (UTC) strictly after `now` at which an interval boundary completes in-session."""
    n = to_ist(now)
    step = timedelta(minutes=interval_minutes)
    d = n.date()
    for _ in range(10):
        if is_weekday(d):
            o, c = session_open(d), session_close(d)
            if n < o + step:
                return as_utc(o + step)
            if n < c:
                k = (n - o) // step + 1
                cand = o + k * step
                if cand <= c:
                    return as_utc(cand)
        d += timedelta(days=1)
        n = session_open(d) - timedelta(minutes=1)
    raise ValueError("no session found")


def is_session_last_candle(ts: datetime, tf: str = "5m") -> bool:
    t = to_ist(ts)
    return t + tf_delta(tf) >= session_close(t.date())

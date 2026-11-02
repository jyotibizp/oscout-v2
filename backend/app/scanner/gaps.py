"""Scan gaps (#2): find completed 5m candles that no AUTO/BACKFILL scan covered, and fill the ones the user selects.

Latest block (no scan of any kind after it): full fill, the lifecycle sees the candles in order as if nothing broke.
Interior block (later scans exist): record-only fill, scan_results written, setups / events / trades untouched.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import UTC, as_utc, is_weekday, latest_completed_start, now_utc, session_close, session_open, to_ist
from app.db.models import MarketCandle, ScanRun
from app.market.symbols import TRADABLE
from app.scanner.service import SCAN_LOCK, ingest_all, run_scan
from app.strategy import store

STEP = timedelta(minutes=5)
SCAN_DELAY = timedelta(seconds=20)
COVERING = ("AUTO", "BACKFILL")


class FillBusy(Exception):
    pass


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _expected(d: date, last_done: datetime) -> list[datetime]:
    out, t = [], session_open(d)
    while t < session_close(d) and as_utc(t) <= last_done:
        out.append(as_utc(t))
        t += STEP
    return out


def _data_ts(db: Session, lo: datetime, hi: datetime) -> set[datetime]:
    """Candles every tradable index has stored."""
    sets = []
    for sym in TRADABLE:
        sets.append({_utc(t) for t in db.scalars(select(MarketCandle.ts).where(
            MarketCandle.symbol == sym, MarketCandle.timeframe == "5m", MarketCandle.ts >= lo, MarketCandle.ts <= hi))})
    return set.intersection(*sets) if sets else set()


@dataclass
class Block:
    start: datetime
    end: datetime
    candles: list[datetime]
    data: str  # FULL | PARTIAL | NONE

    def as_dict(self, latest: bool) -> dict:
        return {"id": self.start.isoformat(), "date": to_ist(self.start).date().isoformat(), "start": self.start.isoformat(),
                "end": self.end.isoformat(), "candles": len(self.candles), "type": "LATEST" if latest else "INTERIOR",
                "data": self.data, "selectable": self.data == "FULL"}


def find(db: Session, d_from: date, d_to: date, now: datetime | None = None) -> dict:
    now = now or now_utc()
    last_done = latest_completed_start(now, "5m")
    lo, hi = as_utc(session_open(d_from)), as_utc(session_close(d_to))
    covered = {_utc(t) for t in db.scalars(select(ScanRun.candle_ts).where(
        ScanRun.trigger.in_(COVERING), ScanRun.candle_ts >= lo, ScanRun.candle_ts <= hi))}
    data = _data_ts(db, lo, hi)
    last_scan = db.scalar(select(func.max(ScanRun.candle_ts)))
    last_scan = _utc(last_scan) if last_scan else None
    blocks: list[Block] = []
    days, no_data_days = [], []
    d = d_from
    while d <= d_to:
        exp = _expected(d, last_done) if is_weekday(d) else []
        if exp and not any(t in data for t in exp) and not any(t in covered for t in exp):
            no_data_days.append(d.isoformat())  # holiday, or candles never synced: nothing to scan
        elif exp:
            miss = [t for t in exp if t not in covered]
            days.append({"date": d.isoformat(), "expected": len(exp), "missing": len(miss)})
            run: list[datetime] = []
            for t in miss + [None]:
                if run and (t is None or t - run[-1] != STEP):
                    have = sum(1 for x in run if x in data)
                    blocks.append(Block(run[0], run[-1], run, "FULL" if have == len(run) else "NONE" if have == 0 else "PARTIAL"))
                    run = []
                if t is not None:
                    run.append(t)
        d += timedelta(days=1)
    out = []
    for b in blocks:
        latest = last_scan is None or last_scan < b.start  # any scan (even MANUAL) inside or after it moved the lifecycle on
        out.append(b.as_dict(latest and b is blocks[-1]))
    return {"from": d_from.isoformat(), "to": d_to.isoformat(), "total_missing": sum(x["missing"] for x in days),
            "days": days, "no_data_days": no_data_days, "blocks": out}


def fill(db: Session, provider, block_ids: list[str], now: datetime | None = None) -> list[dict]:
    """Fill the selected blocks in time order. Detection is redone after one ingest, so a stale selection is safe."""
    if not SCAN_LOCK.acquire(blocking=False):
        raise FillBusy("A scan or fill is running; try again in a moment")
    try:
        now = now or now_utc()
        _, cfg = store.get_active(db)
        ingest_all(db, provider, cfg, now)
        wanted = sorted({datetime.fromisoformat(b) for b in block_ids})
        if not wanted:
            return []
        lo = to_ist(wanted[0]).date()
        cur = {b["id"]: b for b in find(db, lo, to_ist(now).date(), now)["blocks"]}
        results = []
        for start in wanted:
            b = cur.get(start.isoformat())
            if b is None:
                results.append({"id": start.isoformat(), "status": "SKIPPED", "message": "No longer missing"})
                continue
            if b["data"] != "FULL":
                results.append({"id": b["id"], "status": "NO_DATA", "message": "Candle data missing for this block"})
                continue
            full = b["type"] == "LATEST"
            t, end, scans, signals = datetime.fromisoformat(b["start"]), datetime.fromisoformat(b["end"]), 0, 0
            while t <= end:
                run, created = run_scan(db, provider, trigger="BACKFILL", now=t + STEP + SCAN_DELAY, ingest=False,
                                        lifecycle=full)
                scans += int(created)
                signals += sum(1 for v in (run.summary or {}).get("symbols", {}).values() if v.get("final") == "SIGNAL")
                t += STEP
            results.append({"id": b["id"], "status": "FILLED", "mode": "FULL" if full else "RECORD_ONLY",
                            "scans": scans, "signals": signals})
        return results
    finally:
        SCAN_LOCK.release()


def late_setup_ids(db: Session) -> set[int]:
    """Setups whose signal came from a BACKFILL scan (found late)."""
    from app.db.models import ScanResult
    q = (select(ScanResult.setup_id).join(ScanRun, ScanRun.id == ScanResult.scan_run_id)
         .where(ScanRun.trigger == "BACKFILL", ScanResult.final_result == "SIGNAL", ScanResult.setup_id.is_not(None)))
    return set(db.scalars(q))

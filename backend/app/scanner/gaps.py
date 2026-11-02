"""Scan gaps (#2): find completed 5m candles that no AUTO/BACKFILL scan covered, and fill the ones the user selects.

Latest block (no scan of any kind after it): full fill, the lifecycle sees the candles in order as if nothing broke.
Interior block (later scans exist): replay fill (#23), append-only. Existing setups / trades are untouched; a qualified
candle becomes a new LATE signal walked to its exit over stored candles (or REJECTED if a trade was open then).
Interior blocks filled record-only before #23 are caught up by replay_filled().
A scan whose results all evaluated an older candle (stale feed) doesn't cover its candle and doesn't move "latest".
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import UTC, as_utc, is_weekday, latest_completed_start, now_utc, session_close, session_open, to_ist
from app.api.serializers import LATE_NOTE
from app.db.models import MarketCandle, ScanResult, ScanRun, SignalEvent, SignalSetup
from app.market.symbols import TRADABLE
from app.scanner.service import SCAN_LOCK, evaluate_symbol, ingest_all, run_scan
from app.signals.lifecycle import LATE_EVENT, create_late_signal
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
    """Candles every tradable index has stored, per day. An index with no candles at all that day (added later,
    e.g. BANKNIFTY before its first sync) is left out of that day's check instead of blanking every block."""
    per_sym = [{_utc(t) for t in db.scalars(select(MarketCandle.ts).where(
        MarketCandle.symbol == sym, MarketCandle.timeframe == "5m", MarketCandle.ts >= lo, MarketCandle.ts <= hi))}
        for sym in TRADABLE]
    by_day: dict = {}
    for ts_set in per_sym:
        days: dict = {}
        for t in ts_set:
            days.setdefault(to_ist(t).date(), set()).add(t)
        for d, ts in days.items():
            by_day[d] = ts if d not in by_day else by_day[d] & ts
    return set().union(*by_day.values()) if by_day else set()


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


def _real_runs(db: Session, lo: datetime) -> list[tuple[str, datetime]]:
    """(trigger, candle) of runs from `lo` on that scanned their own candle: no results, or at least one result on it."""
    rows = db.execute(select(ScanRun.id, ScanRun.trigger, ScanRun.candle_ts, ScanResult.candle_ts)
                      .outerjoin(ScanResult, ScanResult.scan_run_id == ScanRun.id).where(ScanRun.candle_ts >= lo)).all()
    runs: dict[int, list] = {}
    for rid, trig, c, rc in rows:
        r = runs.setdefault(rid, [trig, _utc(c), False, False])
        r[2] |= rc is not None
        r[3] |= rc is not None and _utc(rc) == r[1]
    return [(trig, c) for trig, c, has, fresh in runs.values() if fresh or not has]


def find(db: Session, d_from: date, d_to: date, now: datetime | None = None) -> dict:
    now = now or now_utc()
    last_done = latest_completed_start(now, "5m")
    lo, hi = as_utc(session_open(d_from)), as_utc(session_close(d_to))
    real = _real_runs(db, lo)
    covered = {c for trig, c in real if trig in COVERING and c <= hi}
    data = _data_ts(db, lo, hi)
    last_scan = max((c for _, c in real), default=None)
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
            t, end, scans, signals, blocked = datetime.fromisoformat(b["start"]), datetime.fromisoformat(b["end"]), 0, 0, 0
            while t <= end:
                run, created = run_scan(db, provider, trigger="BACKFILL", now=t + STEP + SCAN_DELAY, ingest=False,
                                        lifecycle=full)
                scans += int(created)
                syms = (run.summary or {}).get("symbols", {}).values() if created else []
                signals += sum(1 for v in syms if v.get("final") == "SIGNAL")
                blocked += sum(1 for v in syms if not full and v.get("state") == "REJECTED" and v.get("late"))
                t += STEP
            results.append({"id": b["id"], "status": "FILLED", "mode": "FULL" if full else "REPLAY",
                            "scans": scans, "signals": signals, "blocked": blocked})
        return results
    finally:
        SCAN_LOCK.release()


def late_setup_ids(db: Session) -> set[int]:
    """Setups found late: signal from a BACKFILL scan, or created by a replay fill (#23)."""
    q = (select(ScanResult.setup_id).join(ScanRun, ScanRun.id == ScanResult.scan_run_id)
         .where(ScanRun.trigger == "BACKFILL", ScanResult.final_result == "SIGNAL", ScanResult.setup_id.is_not(None)))
    return set(db.scalars(q)) | set(db.scalars(select(SignalEvent.setup_id).where(SignalEvent.event == LATE_EVENT)))


def _breakout_key(r: ScanResult):
    bo = (r.details or {}).get("breakout") or {}
    return (r.symbol, bo.get("ts"), r.direction) if bo.get("ts") else None


def _setup_keys(db: Session) -> dict:
    return {(s.symbol, _utc(s.breakout_ts).isoformat(), s.direction): s for s in db.scalars(select(SignalSetup))}


def unreplayed(db: Session) -> list[ScanResult]:
    """First record-only (pre-#23) result per qualified breakout that has no setup yet, in candle order."""
    keys, seen, out = _setup_keys(db), set(), []
    rows = db.scalars(select(ScanResult).where(ScanResult.state == "QUALIFIED", ScanResult.final_result == "NO_SIGNAL",
                                               ScanResult.rejection_reason == LATE_NOTE)
                      .order_by(ScanResult.candle_ts, ScanResult.id)).all()
    for r in rows:
        k = _breakout_key(r)
        if k is None or k in seen:
            continue
        seen.add(k)
        k2 = (k[0], _utc(datetime.fromisoformat(k[1])).isoformat(), k[2])
        if k2 not in keys:
            out.append(r)
    return out


def replay_filled(db: Session) -> dict:
    """Catch-up for blocks filled record-only before #23: re-evaluate each missed breakout as of its candle and replay
    it (append-only). Old scan rows are left as they are. Idempotent: a replayed breakout has a setup and is skipped."""
    if not SCAN_LOCK.acquire(blocking=False):
        raise FillBusy("A scan or fill is running; try again in a moment")
    try:
        row, cfg = store.get_active(db)
        out = {"breakouts": 0, "signals": 0, "blocked": 0, "skipped": 0, "items": []}
        for r in unreplayed(db):
            out["breakouts"] += 1
            t = _utc(r.candle_ts)
            res, _ = evaluate_symbol(db, r.symbol, cfg, t + STEP + SCAN_DELAY, until=t)
            k = _breakout_key(r)
            if res is None or res.state != "QUALIFIED" or not res.breakout or (
                    _utc(datetime.fromisoformat(res.breakout["ts"])) != _utc(datetime.fromisoformat(k[1]))):
                out["skipped"] += 1  # doesn't qualify again under the active config: nothing to replay
                out["items"].append({"scan_result_id": r.id, "symbol": r.symbol, "candle_ts": t.isoformat(), "result": "SKIPPED"})
                continue
            setup, state, note = create_late_signal(db, res, cfg, row.id, row.version, now_utc())
            db.commit()
            out["signals" if state == "SIGNAL_GENERATED" else "blocked"] += 1
            out["items"].append({"scan_result_id": r.id, "symbol": r.symbol, "candle_ts": t.isoformat(),
                                 "result": state, "setup_id": setup.id if setup else None, "note": note})
        return out
    finally:
        SCAN_LOCK.release()

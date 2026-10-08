"""Automatic scanning aligned to candle closes (every N minutes, market hours only) using the SAME run_scan()
as the SCAN NOW button. AUTO scans are unique per candle, so restarts or double triggers cannot duplicate them."""
import asyncio
import logging
from datetime import datetime, timedelta

from starlette.concurrency import run_in_threadpool

from app.core.clock import is_market_open, next_completion, now_utc
from app.db.session import SessionLocal, get_engine
from app.market.factory import get_provider
from app.scanner.service import run_scan
from app.strategy import store

log = logging.getLogger(__name__)


class AutoScanner:
    def __init__(self):
        self.runtime_enabled = True      # header ON/OFF switch (on top of the configured setting)
        self.last_run: datetime | None = None
        self.last_result: str | None = None
        self.last_error: str | None = None
        self.next_run: datetime | None = None
        self._task: asyncio.Task | None = None

    def _cfg(self):
        get_engine()
        with SessionLocal() as db:
            return store.get_active(db)[1].scanner

    def enabled(self) -> bool:
        return self.runtime_enabled and self._cfg().auto_scan_enabled

    def compute_next(self, now: datetime | None = None) -> datetime:
        sc = self._cfg()
        now = now or now_utc()
        base = next_completion(now - timedelta(seconds=sc.scan_delay_seconds), sc.interval_minutes)
        return base + timedelta(seconds=sc.scan_delay_seconds)

    def status(self) -> dict:
        nxt = self.compute_next()
        return {"enabled": self.enabled(), "runtime_enabled": self.runtime_enabled,
                "next_run": nxt.isoformat(), "last_run": self.last_run.isoformat() if self.last_run else None,
                "last_result": self.last_result, "last_error": self.last_error}

    def _scan_once(self) -> str:
        with SessionLocal() as db:
            run, created = run_scan(db, get_provider(), trigger="AUTO")
            return f"#{run.id} {run.status}" if created else f"#{run.id} already scanned"

    async def _loop(self):
        while True:
            try:
                self.next_run = self.compute_next()
                await asyncio.sleep(max((self.next_run - now_utc()).total_seconds(), 0.5))
                sc = self._cfg()
                boundary = self.next_run - timedelta(seconds=sc.scan_delay_seconds) - timedelta(seconds=1)
                if not self.enabled() or (sc.market_hours_only and not is_market_open(boundary)):
                    continue
                self.last_run = now_utc()
                self.last_result = await run_in_threadpool(self._scan_once)
                self.last_error = None
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 - keep the loop alive
                self.last_error = str(e)
                log.exception("auto scan failed")
                await asyncio.sleep(5)

    def start(self):
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


auto_scanner = AutoScanner()

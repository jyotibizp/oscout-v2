import asyncio
from datetime import timedelta

from app.scanner import scheduler
from app.scanner.scheduler import AutoScanner


def test_sleep_until_follows_wall_clock(monkeypatch):
    """Wall clock jumps (machine slept) must end the wait at once, not after the full monotonic duration."""
    from app.core.clock import now_utc
    start = now_utc()
    clock = {"now": start}
    monkeypatch.setattr(scheduler, "now_utc", lambda: clock["now"])
    naps = []
    real_sleep = asyncio.sleep

    async def fake_sleep(s):
        naps.append(s)
        if s:
            clock["now"] += timedelta(hours=18)  # machine hibernated during the first nap
        await real_sleep(0)

    monkeypatch.setattr(scheduler.asyncio, "sleep", fake_sleep)
    asyncio.run(AutoScanner._sleep_until(start + timedelta(hours=17, minutes=50)))
    assert naps == [15.0, 0]

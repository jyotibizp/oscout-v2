"""Account trade log + overtrading stats (#24). Everything here is derived on read from account_trades /
account_orders (nothing stored), so a CSV import or a new pull changes the numbers immediately.

Round trip: fills of one contract from flat -> back to flat (a fill that crosses zero is split).
Charges: Zerodha F&O schedule, estimated per fill (contract notes are not imported)."""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import now_utc, to_ist
from app.db.models import AccountOrder, AccountTrade, Trade

INDEXES = ("NIFTY", "SENSEX", "BANKNIFTY")
STT_CHANGE = date(2026, 4, 1)               # Budget 2026: options 0.1% -> 0.15%, futures 0.02% -> 0.05% (sell side)
BROKERAGE_PER_ORDER = 20.0
TXN = {("NFO", "OPT"): 0.0003503, ("BFO", "OPT"): 0.000325, ("NFO", "FUT"): 0.0000173, ("BFO", "FUT"): 0.0}
SEBI, STAMP_OPT, STAMP_FUT, GST = 1e-6, 0.00003, 0.00002, 0.18
FLIP_MINUTES = 10                           # opposite view (CE <-> PE) entered within this many minutes of an exit
SCALP_MINUTES = 2


def _stt(d: date, kind: str) -> float:
    if kind == "OPT":
        return 0.0015 if d >= STT_CHANGE else 0.001
    return 0.0005 if d >= STT_CHANGE else 0.0002


def fill_charges(f: AccountTrade) -> dict:
    """Statutory charges on one fill (brokerage is per order, added by the caller)."""
    kind = "FUT" if f.instrument == "FUT" else "OPT"
    v = f.quantity * f.price
    d = to_ist(f.fill_ts).date()
    stt = v * _stt(d, kind) if f.side == "SELL" else 0.0
    txn = v * TXN.get((f.exchange, kind), 0.0)
    sebi = v * SEBI
    stamp = v * (STAMP_OPT if kind == "OPT" else STAMP_FUT) if f.side == "BUY" else 0.0
    return {"stt": stt, "txn": txn, "sebi": sebi, "stamp": stamp}


@dataclass
class RoundTrip:
    tradingsymbol: str
    underlying: str
    instrument: str
    exchange: str
    side: str                                # LONG | SHORT
    entry_ts: datetime
    exit_ts: datetime | None = None
    qty: int = 0                             # largest position held
    pos: int = 0
    buy_qty: int = 0
    sell_qty: int = 0
    buy_value: float = 0.0
    sell_value: float = 0.0
    fills: int = 0
    adds: int = 0
    avg_down: bool = False
    orders: set = field(default_factory=set)
    taxes: dict = field(default_factory=lambda: {"stt": 0.0, "txn": 0.0, "sebi": 0.0, "stamp": 0.0})

    @property
    def closed(self) -> bool:
        return self.pos == 0 and self.exit_ts is not None

    @property
    def view(self) -> str | None:
        """Market view: long CE / short PE = CALL; long PE / short CE = PUT."""
        if self.instrument == "FUT":
            return "CALL" if self.side == "LONG" else "PUT"
        bull = (self.instrument == "CE") == (self.side == "LONG")
        return "CALL" if bull else "PUT"


def _avg_entry(rt: RoundTrip) -> float:
    q = rt.buy_qty if rt.side == "LONG" else rt.sell_qty
    v = rt.buy_value if rt.side == "LONG" else rt.sell_value
    return v / q if q else 0.0


def build_round_trips(fills: list[AccountTrade]) -> list[RoundTrip]:
    out: list[RoundTrip] = []
    open_: dict[str, RoundTrip] = {}
    for f in sorted(fills, key=lambda x: (x.fill_ts, x.trade_id)):
        q = f.quantity if f.side == "BUY" else -f.quantity
        tax = fill_charges(f)
        while q:
            rt = open_.get(f.tradingsymbol)
            if rt is None:
                rt = RoundTrip(f.tradingsymbol, f.underlying, f.instrument, f.exchange,
                               "LONG" if q > 0 else "SHORT", f.fill_ts)
                open_[f.tradingsymbol] = rt
                out.append(rt)
            same = (rt.pos >= 0) == (q > 0) if rt.pos else True
            take = q if same else (q if abs(q) <= abs(rt.pos) else -rt.pos)
            share = abs(take) / f.quantity
            if same and rt.pos:  # adding to an open position
                rt.adds += 1
                avg = _avg_entry(rt)
                if (rt.side == "LONG" and f.price < avg) or (rt.side == "SHORT" and f.price > avg):
                    rt.avg_down = True
            if take > 0:
                rt.buy_qty += take
                rt.buy_value += take * f.price
            else:
                rt.sell_qty += -take
                rt.sell_value += -take * f.price
            for k, v in tax.items():
                rt.taxes[k] += v * share
            rt.pos += take
            rt.qty = max(rt.qty, abs(rt.pos))
            rt.fills += 1
            if f.order_id:
                rt.orders.add(f.order_id)
            if rt.pos == 0:
                rt.exit_ts = f.fill_ts
                del open_[f.tradingsymbol]
            q -= take
    return out


def _signals(db: Session, lo: datetime | None) -> list[Trade]:
    from app.scanner.gaps import late_setup_ids
    late = late_setup_ids(db)
    q = select(Trade).order_by(Trade.entry_ts)
    if lo:
        q = q.where(Trade.entry_ts >= lo - timedelta(days=5))
    return [t for t in db.scalars(q) if t.setup_id not in late]


def _match(rt: RoundTrip, sigs: list[Trade]) -> Trade | None:
    """On-signal: same index and view, entered while a live (not late) signal was open."""
    now = now_utc()
    for s in sigs:
        if s.symbol == rt.underlying and s.direction == rt.view and s.entry_ts <= rt.entry_ts <= (s.exit_ts or now):
            return s
    return None


def _day(ts: datetime) -> date:
    return to_ist(ts).date()


def round_trips(db: Session, lo: datetime | None = None, hi: datetime | None = None, symbol: str | None = None) -> list[dict]:
    """Closed and open round trips (newest last) with charges, signal link and flags."""
    fills = list(db.scalars(select(AccountTrade)))
    rts = [r for r in build_round_trips(fills) if (not lo or r.entry_ts >= lo) and (not hi or r.entry_ts <= hi)]
    if symbol:
        sym = symbol.upper()
        rts = [r for r in rts if (r.underlying == sym if sym != "OTHER" else r.underlying not in INDEXES)]
    sigs = _signals(db, lo)
    out: list[dict] = []
    seq: dict[date, int] = defaultdict(int)
    prev_by_day: dict[date, dict] = {}
    prev_by_index: dict[str, dict] = {}
    day_rows: dict[str, list] = defaultdict(list)
    for r in sorted(rts, key=lambda x: x.entry_ts):
        d = _day(r.entry_ts)
        seq[d] += 1
        taxes = sum(r.taxes.values())
        brk = BROKERAGE_PER_ORDER * len(r.orders) if r.orders else BROKERAGE_PER_ORDER * min(r.fills, 2)
        gst = GST * (brk + r.taxes["txn"] + r.taxes["sebi"])
        charges = brk + taxes + gst
        gross = r.sell_value - r.buy_value if r.closed else None
        s = _match(r, sigs)
        prev = prev_by_day.get(d)
        pidx = prev_by_index.get(r.underlying)
        row = {
            "tradingsymbol": r.tradingsymbol, "underlying": r.underlying, "instrument": r.instrument, "side": r.side,
            "view": r.view, "qty": r.qty, "entry_ts": r.entry_ts.isoformat(),
            "exit_ts": r.exit_ts.isoformat() if r.closed else None, "status": "CLOSED" if r.closed else "OPEN",
            "avg_entry": round(_avg_entry(r), 2),
            "avg_exit": round((r.sell_value / r.sell_qty if r.side == "LONG" else r.buy_value / r.buy_qty), 2)
            if r.closed and (r.sell_qty if r.side == "LONG" else r.buy_qty) else None,
            "hold_min": round((r.exit_ts - r.entry_ts).total_seconds() / 60, 1) if r.closed else None,
            "gross": round(gross, 2) if gross is not None else None,
            "charges": round(charges, 2), "brokerage": round(brk, 2), "stt": round(r.taxes["stt"], 2),
            "net": round(gross - charges, 2) if gross is not None else None,
            "orders": len(r.orders), "fills": r.fills, "adds": r.adds, "day": d.isoformat(), "day_seq": seq[d],
            "signal_id": s.setup_id if s else None, "on_signal": s is not None,
            "signal_delay_min": round((r.entry_ts - s.entry_ts).total_seconds() / 60, 1) if s else None,
            "gap_prev_min": round((r.entry_ts - datetime.fromisoformat(prev["entry_ts"])).total_seconds() / 60, 1) if prev else None,
            "_entry": r.entry_ts, "_exit": r.exit_ts if r.closed else None,
        }
        # re-entry after the previous round trip of the day closed: gap from that exit, and whether it lost
        done = [o for o in day_rows[row["day"]] if o["_exit"] and o["_exit"] <= r.entry_ts]
        last = max(done, key=lambda o: o["_exit"]) if done else None
        row["after"] = None if not last else ("LOSS" if (last["net"] or 0) < 0 else "WIN")
        row["gap_after_exit_min"] = round((r.entry_ts - last["_exit"]).total_seconds() / 60, 1) if last else None
        flags = []
        if not row["on_signal"]:
            flags.append("OFF_SIGNAL")
        if r.avg_down:
            flags.append("AVG_DOWN")
        if pidx and pidx["_exit"] and pidx["view"] != row["view"] and \
                timedelta(0) <= r.entry_ts - pidx["_exit"] <= timedelta(minutes=FLIP_MINUTES):
            flags.append("FLIP")
        if row["after"] == "LOSS" and row["gap_after_exit_min"] is not None and row["gap_after_exit_min"] < 5:
            flags.append("QUICK_REENTRY")
        if row["hold_min"] is not None and row["hold_min"] < SCALP_MINUTES:
            flags.append("SCALP")
        row["flags"] = flags
        out.append(row)
        day_rows[row["day"]].append(row)
        prev_by_day[d] = row
        prev_by_index[r.underlying] = row
    return out


def public(rows: list[dict]) -> list[dict]:
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]


# ---------------- stats ----------------
def _agg(rows: list[dict]) -> dict:
    nets = [r["net"] for r in rows]
    wins = [x for x in nets if x > 0]
    losses = [x for x in nets if x <= 0]
    return {"trades": len(nets), "wins": len(wins), "win_rate": round(100 * len(wins) / len(nets), 1) if nets else None,
            "net": round(sum(nets), 2), "avg": round(sum(nets) / len(nets), 2) if nets else None,
            "avg_win": round(sum(wins) / len(wins), 2) if wins else None,
            "avg_loss": round(sum(losses) / len(losses), 2) if losses else None,
            "profit_factor": round(sum(wins) / -sum(losses), 2) if losses and sum(losses) < 0 else None}


def _bucket(rows: list[dict], key, order: list[str]) -> list[dict]:
    g: dict[str, list] = defaultdict(list)
    for r in rows:
        b = key(r)
        if b is not None:
            g[b].append(r)
    return [{"bucket": b, **_agg(g[b])} for b in order if g.get(b)]


def _gap_bucket(m: float | None, edges=((1, "<1m"), (5, "1-5m"), (15, "5-15m"))) -> str:
    if m is None:
        return "1st of day"
    for e, lbl in edges:
        if m < e:
            return lbl
    return f"{edges[-1][0]}m+"


def stats(db: Session, lo: datetime | None = None, hi: datetime | None = None, symbol: str | None = None) -> dict:
    allrows = round_trips(db, lo, hi, symbol)
    rows = [r for r in allrows if r["status"] == "CLOSED"]
    days: dict[str, list] = defaultdict(list)
    for r in rows:
        days[r["day"]].append(r)
    actual = sum(r["net"] for r in rows)

    # 1. if you'd stopped after trade N
    stop_after = []
    for n in (1, 2, 3, 5):
        v = sum(sum(x["net"] for x in sorted(d, key=lambda x: x["day_seq"])[:n]) for d in days.values())
        stop_after.append({"n": n, "net": round(v, 2), "vs_actual": round(v - actual, 2)})

    # 2. gap since the previous entry of the day
    gap = _bucket(rows, lambda r: _gap_bucket(r["gap_prev_min"]), ["1st of day", "<1m", "1-5m", "5-15m", "15m+"])

    # 3. gave it back (realised P&L through the day, by exit time)
    gave_days, gave_total, green_to_red, day_rows = 0, 0.0, 0, []
    for d, rs in sorted(days.items()):
        cum = peak = 0.0
        for r in sorted(rs, key=lambda x: x["_exit"]):
            cum += r["net"]
            peak = max(peak, cum)
        if peak > 0 and cum < peak - 0.01:
            gave_days += 1
            gave_total += peak - cum
            green_to_red += cum < 0
        day_rows.append({"day": d, "trades": len(rs), "net": round(cum, 2), "peak": round(peak, 2)})

    # 4. charges
    gross = sum(r["gross"] for r in rows)
    charges = sum(r["charges"] for r in rows)
    ch = {"gross": round(gross, 2), "charges": round(charges, 2), "net": round(actual, 2),
          "brokerage": round(sum(r["brokerage"] for r in rows), 2), "stt": round(sum(r["stt"] for r in rows), 2),
          "pct_of_gross": round(100 * charges / gross, 1) if gross > 0 else None,
          "per_trade": round(charges / len(rows), 2) if rows else None}

    # 5. system vs you
    sigs = [t for t in _signals(db, lo) if t.status == "CLOSED" and (not lo or t.entry_ts >= lo) and (not hi or t.entry_ts <= hi)
            and (not symbol or t.symbol == symbol.upper())]
    on = [r for r in rows if r["on_signal"]]
    off = [r for r in rows if not r["on_signal"]]
    rs_ = [t.r_multiple for t in sigs if t.r_multiple is not None]
    system = {"signals": len(sigs), "net_r": round(sum(rs_), 2), "win_rate": round(100 * sum(1 for x in rs_ if x > 0) / len(rs_), 1) if rs_ else None,
              "taken": len({r["signal_id"] for r in on}), "on_signal": _agg(on), "off_signal": _agg(off)}

    # 6. tilt clock: minutes to the next entry after a loss vs after a win (same day)
    after_loss = [r["gap_after_exit_min"] for r in rows if r["after"] == "LOSS" and r["gap_after_exit_min"] is not None]
    after_win = [r["gap_after_exit_min"] for r in rows if r["after"] == "WIN" and r["gap_after_exit_min"] is not None]
    tilt = {"after_loss_min": round(median(after_loss), 1) if after_loss else None, "after_loss_n": len(after_loss),
            "after_win_min": round(median(after_win), 1) if after_win else None, "after_win_n": len(after_win)}

    # 7. after 2+ losses in a row (chronological by entry)
    seq = sorted(rows, key=lambda r: r["_entry"])
    nxt, streak = [], 0
    for r in seq:
        if streak >= 2:
            nxt.append(r)
        streak = streak + 1 if r["net"] <= 0 else 0
    after_two = {"next": _agg(nxt), "overall_win_rate": _agg(rows)["win_rate"]}

    # 8. scalp tax
    scalp = _bucket(rows, lambda r: f"<{SCALP_MINUTES}m" if r["hold_min"] < SCALP_MINUTES else f"{SCALP_MINUTES}m+",
                    [f"<{SCALP_MINUTES}m", f"{SCALP_MINUTES}m+"])

    # 10. weekday x hour heatmap (entry time)
    heat: dict[tuple, list] = defaultdict(list)
    for r in rows:
        t = to_ist(r["_entry"])
        heat[(t.weekday(), t.hour)].append(r["net"])
    heatmap = [{"weekday": w, "hour": h, "trades": len(v), "net": round(sum(v), 2)} for (w, h), v in sorted(heat.items())]

    # breakdowns
    by_seq = _bucket(rows, lambda r: str(r["day_seq"]) if r["day_seq"] < 5 else "5+", ["1", "2", "3", "4", "5+"])
    def dbucket(n):
        return "1-2" if n <= 2 else "3-4" if n <= 4 else "5-9" if n <= 9 else "10+"
    by_day_count = []
    for b in ("1-2", "3-4", "5-9", "10+"):
        ds = [d for d in day_rows if dbucket(d["trades"]) == b]
        if ds:
            by_day_count.append({"bucket": b, "days": len(ds), "net": round(sum(d["net"] for d in ds), 2),
                                 "avg_day": round(sum(d["net"] for d in ds) / len(ds), 2),
                                 "green_pct": round(100 * sum(1 for d in ds if d["net"] > 0) / len(ds), 1)})
    reentry = _bucket([r for r in rows if r["after"] == "LOSS"],
                      lambda r: _gap_bucket(r["gap_after_exit_min"], ((5, "<5m"), (15, "5-15m"), (30, "15-30m"))),
                      ["<5m", "5-15m", "15-30m", "30m+"])
    reentry_win = _agg([r for r in rows if r["after"] == "WIN"])
    flags = {f: _agg([r for r in rows if f in r["flags"]]) for f in ("AVG_DOWN", "FLIP", "QUICK_REENTRY", "SCALP", "OFF_SIGNAL")}

    # frequency
    bursts = {}
    for d, rs in days.items():
        ts = sorted(r["_entry"] for r in rs)
        j, best = 0, 0
        for i, t in enumerate(ts):
            while t - ts[j] >= timedelta(minutes=15):
                j += 1
            best = max(best, i - j + 1)
        bursts[d] = best
    by_hour: dict[int, int] = defaultdict(int)
    for r in rows:
        by_hour[to_ist(r["_entry"]).hour] += 1
    orders = order_stats(db, lo, hi, symbol)
    for d in day_rows:
        d["burst15"] = bursts.get(d["day"], 0)
        od = orders["by_day"].get(d["day"])
        d["orders"] = od
    rt_on_order_days = sum(d["trades"] for d in day_rows if d["orders"])
    orders["per_round_trip"] = round(orders["placed"] / rt_on_order_days, 2) if rt_on_order_days else None
    counts = [d["trades"] for d in day_rows]
    freq = {"days": len(day_rows), "trades_per_day": round(sum(counts) / len(counts), 1) if counts else None,
            "max_per_day": max(counts) if counts else None,
            "by_hour": [{"hour": h, "trades": by_hour[h]} for h in sorted(by_hour)],
            "max_burst15": max(bursts.values()) if bursts else None}
    curve, c_all, c_on = [], 0.0, 0.0
    for r in sorted(rows, key=lambda x: x["_exit"]):
        c_all += r["net"]
        c_on += r["net"] if r["on_signal"] else 0
        curve.append({"ts": r["exit_ts"], "cum": round(c_all, 2), "cum_on_signal": round(c_on, 2)})
    return {
        "totals": {**_agg(rows), "open": sum(1 for r in allrows if r["status"] == "OPEN"), "days": len(day_rows),
                   "green_days": sum(1 for d in day_rows if d["net"] > 0),
                   "first": rows[0]["day"] if rows else None, "last": rows[-1]["day"] if rows else None},
        "stop_after": stop_after, "gap_prev": gap,
        "gave_back": {"days": gave_days, "total": round(gave_total, 2), "green_to_red": green_to_red, "of_days": len(day_rows)},
        "charges": ch, "system": system, "tilt": tilt, "after_two_losses": after_two, "scalp": scalp, "heatmap": heatmap,
        "by_trade_number": by_seq, "by_day_count": by_day_count, "reentry_after_loss": reentry, "reentry_after_win": reentry_win,
        "flags": flags, "frequency": freq, "orders": {k: v for k, v in orders.items() if k != "by_day"},
        "days": day_rows, "equity": curve,
    }


def order_stats(db: Session, lo: datetime | None, hi: datetime | None, symbol: str | None) -> dict:
    q = select(AccountOrder).order_by(AccountOrder.placed_ts)
    if lo:
        q = q.where(AccountOrder.placed_ts >= lo)
    if hi:
        q = q.where(AccountOrder.placed_ts <= hi)
    os_ = list(db.scalars(q))
    if symbol:
        sym = symbol.upper()
        os_ = [o for o in os_ if (o.underlying == sym if sym != "OTHER" else o.underlying not in INDEXES)]
    by_day: dict[str, dict] = {}
    by_hour: dict[int, int] = defaultdict(int)
    gaps = []
    for d, grp in _group(os_, lambda o: _day(o.placed_ts).isoformat()).items():
        st = defaultdict(int)
        for o in grp:
            st[o.status] += 1
            by_hour[to_ist(o.placed_ts).hour] += 1
        mods = [o.modifications for o in grp if o.modifications is not None]
        by_day[d] = {"placed": len(grp), "complete": st["COMPLETE"], "cancelled": st["CANCELLED"],
                     "rejected": st["REJECTED"], "modified": sum(mods) if mods else None}
        ts = [o.placed_ts for o in grp]
        gaps += [(b - a).total_seconds() for a, b in zip(ts, ts[1:])]
    tot = lambda k: sum((v[k] or 0) for v in by_day.values())  # noqa: E731
    n = len(os_)
    return {"placed": n, "complete": tot("complete"), "cancelled": tot("cancelled"), "rejected": tot("rejected"),
            "modified": tot("modified") if any(v["modified"] is not None for v in by_day.values()) else None,
            "days": len(by_day), "per_day": round(n / len(by_day), 1) if by_day else None,
            "since": _day(os_[0].placed_ts).isoformat() if os_ else None,
            "shortest_gap_sec": round(min(gaps)) if gaps else None,
            "median_gap_sec": round(median(gaps)) if gaps else None,
            "by_hour": [{"hour": h, "orders": by_hour[h]} for h in sorted(by_hour)], "by_day": by_day}


def _group(items, key) -> dict:
    g: dict = defaultdict(list)
    for x in items:
        g[key(x)].append(x)
    return g


def status(db: Session) -> dict:
    from sqlalchemy import func
    from app.account.ingest import last_sync
    n, first, last = db.execute(select(func.count(AccountTrade.id), func.min(AccountTrade.fill_ts), func.max(AccountTrade.fill_ts))).one()
    no = db.scalar(select(func.count(AccountOrder.id)))
    return {"fills": n, "first_fill": first.isoformat() if first else None, "last_fill": last.isoformat() if last else None,
            "orders": no, "last_sync": last_sync}

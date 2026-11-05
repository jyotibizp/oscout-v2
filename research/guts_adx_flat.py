"""Guts on ADX flat bottom vs P2 naked buy. Read-only on the oscout-v2 SQLite DB.

Usage: python guts_adx_flat.py /path/to/oscout_v2_live.db [peak low flat]
Rules (draft agreed in thread, 2026-11-05):
  Event: 5m ADX (from logged scans) >= PEAK, later <= LOW, then FLAT candles with no new ADX low.
         Entry at that candle's close, 09:30-14:00 IST, one per symbol per day, not on expiry day.
  A guts held : buy 0.70-delta CE + 0.70-delta PE, current weekly, exit both at 15:15.
  B guts->P2  : as A, but when a P2 trade opens later that day, sell the losing leg at P2 entry
                and hold the winner to the P2 trade's exit. No P2 that day -> exit both at 15:15.
  C P2 alone  : buy one 0.70 option at each P2 trade entry, exit at its exit (all P2 trades in DB).
Premiums: Black-Scholes, IV = India VIX logged in the scan, r = 6.5%. Weekly expiry: NIFTY Tue,
SENSEX Thu, 15:30 (holidays ignored). C rolls to next weekly on expiry day.
Costs: 1 pt NIFTY / 3 pts SENSEX per leg.
"""
import csv, sqlite3, sys, statistics as st
from bisect import bisect_right
from datetime import datetime, timedelta, time, timezone
from math import erf, exp, log, sqrt

IST = timezone(timedelta(hours=5, minutes=30))
R, YEAR = 0.065, 365 * 24 * 3600
SYMS = {"NIFTY": dict(step=50, cost=1.0, expiry_wd=1), "SENSEX": dict(step=100, cost=3.0, expiry_wd=3)}
PEAK, LOW, FLAT = (float(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (40.0, 20.0, 3)
OUT = sys.argv[5] if len(sys.argv) > 5 else "."
N = lambda x: 0.5 * (1 + erf(x / sqrt(2)))


def bs(S, K, t, v, call):
    d1 = (log(S / K) + (R + v * v / 2) * t) / (v * sqrt(t)); d2 = d1 - v * sqrt(t)
    return (S * N(d1) - K * exp(-R * t) * N(d2), N(d1)) if call else (K * exp(-R * t) * N(-d2) - S * N(-d1), N(d1) - 1)


def expiry(d, wd, roll=False):
    e = d + timedelta(days=(wd - d.weekday()) % 7)
    return e + timedelta(days=7) if roll and e == d else e


def tte(now, exp_d):
    return max((datetime.combine(exp_d, time(15, 30), IST) - now).total_seconds(), 60) / YEAR


def pick(S, t, v, call, step):
    best = None
    for k in range(int(S // step) - 30, int(S // step) + 31):
        K = k * step; p, d = bs(S, K, t, v, call)
        if best is None or abs(abs(d) - 0.70) < abs(abs(best[1]) - 0.70):
            best = (K, d, p)
    return best[0]


def ist(s):  # sqlite naive UTC string -> aware IST
    return datetime.fromisoformat(str(s)[:19]).replace(tzinfo=timezone.utc).astimezone(IST)


db = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
events, a_rows, b_rows, c_rows = [], [], [], []

for sym, cfg in SYMS.items():
    scans = {}
    for ts, adx, vix, sid in db.execute(
            "SELECT candle_ts, adx5, vix, id FROM scan_results WHERE symbol=? AND adx5 IS NOT NULL ORDER BY candle_ts, id", (sym,)):
        scans[ist(ts)] = (adx, vix)  # last scan per candle wins
    candles = {ist(ts): (h, l, c) for ts, h, l, c in db.execute(
        "SELECT ts, high, low, close FROM market_candles WHERE symbol=? AND timeframe='5m'", (sym,))}
    ser = [(t, a, v, candles[t]) for t, (a, v) in sorted(scans.items()) if t in candles]
    times = [r[0] for r in ser]
    vix_at = lambda t: next((ser[i][2] for i in range(bisect_right(times, t) - 1, -1, -1) if ser[i][2]), None)
    close_at = lambda t: ser[bisect_right(times, t) - 1][3][2]

    def value(K, call, S, now, exp_d, v):
        return bs(S, K, tte(now, exp_d), v / 100, call)[0]

    trades = [(ist(e), p, ist(x) if x else None, xp, d, rm) for e, p, x, xp, d, rm in db.execute(
        "SELECT entry_ts, entry_price, exit_ts, exit_price, direction, r_multiple FROM trades "
        "WHERE symbol=? AND status='CLOSED' ORDER BY entry_ts", (sym,))]

    # C: P2 alone
    for e, p, x, xp, d, rm in trades:
        v0, v1 = vix_at(e), vix_at(x)
        if not (v0 and v1): continue
        ex = expiry(e.date(), cfg["expiry_wd"], roll=True); call = d == "CALL"
        K = pick(p, tte(e, ex), v0 / 100, call, cfg["step"])
        buy, sell = value(K, call, p, e, ex, v0), value(K, call, xp, x, ex, v1)
        c_rows.append(dict(symbol=sym, entry=e.isoformat(), year=e.year, pts=round(sell - buy - 2 * cfg["cost"], 1),
                           premium=round(buy, 1), index_r=rm))

    # events
    armed, low, low_i, used_days = False, None, None, set()
    for i, (t, a, v, (h, l, c)) in enumerate(ser):
        if a >= PEAK: armed, low, low_i = True, None, None; continue
        if not armed: continue
        if a <= LOW and (low is None or a < low): low, low_i = a, i; continue
        if low is not None and a < low: low, low_i = a, i; continue
        if low is None or i - low_i < FLAT: continue
        armed = False
        if any(ser[j][0].date() != t.date() for j in range(low_i, i + 1)): continue
        entry_t = t + timedelta(minutes=5)
        ex = expiry(t.date(), cfg["expiry_wd"])
        if not (time(9, 30) <= entry_t.time() <= time(14, 0)) or ex == t.date() or (sym, t.date()) in used_days or not v:
            continue
        used_days.add((sym, t.date()))
        day = [r for r in ser[i + 1:] if r[0].date() == t.date()]
        fut = ser[i + 1:i + 16]
        ev = dict(symbol=sym, entry=entry_t.isoformat(), year=t.year, adx=round(a, 1), adx_low=round(low, 1), vix=v,
                  new_low_10=any(r[1] < low for r in fut[:10]), new_low_15=any(r[1] < low for r in fut[:15]),
                  adx_rise_6=round(max((r[1] for r in fut[:6]), default=a) - a, 1))
        for n in (6, 12, 24):
            seg = day[:n]
            ev[f"range_{n}"] = round(max(r[3][0] for r in seg) - min(r[3][1] for r in seg), 1) if seg else None
        events.append(ev)

        # A / B
        S = c; t0 = t0v = None
        kc, kp = pick(S, tte(entry_t, ex), v / 100, True, cfg["step"]), pick(S, tte(entry_t, ex), v / 100, False, cfg["step"])
        cost = value(kc, True, S, entry_t, ex, v) + value(kp, False, S, entry_t, ex, v)
        eod = [r for r in day if r[0].time() <= time(15, 10)]
        if not eod: continue
        te = eod[-1][0] + timedelta(minutes=5); Se, ve = eod[-1][3][2], vix_at(eod[-1][0])
        a_pnl = value(kc, True, Se, te, ex, ve) + value(kp, False, Se, te, ex, ve) - cost - 4 * cfg["cost"]
        a_rows.append(dict(symbol=sym, entry=entry_t.isoformat(), year=t.year, cost=round(cost, 1), pts=round(a_pnl, 1),
                           move=round(Se - S, 1)))
        p2 = next((tr for tr in trades if entry_t <= tr[0] < te and tr[0].date() == t.date()), None)
        if p2:
            e, p, x, xp, d, _ = p2; ve0, vx = vix_at(e), vix_at(x)
            win_call = d == "CALL"
            loser = value(kp if win_call else kc, not win_call, p, e, ex, ve0)
            winner = value(kc if win_call else kp, win_call, xp, x, ex, vx)
            b_pnl, how = loser + winner - cost - 4 * cfg["cost"], f"P2 {d}"
        else:
            b_pnl, how = a_pnl, "no P2, 15:15"
        b_rows.append(dict(symbol=sym, entry=entry_t.isoformat(), year=t.year, cost=round(cost, 1), pts=round(b_pnl, 1), exit=how))


def summ(rows, key="pts"):
    out = []
    for sym in SYMS:
        for yr in sorted({r["year"] for r in rows}):
            v = [r[key] for r in rows if r["symbol"] == sym and r["year"] == yr]
            if v:
                out.append(f"| {sym} {yr} | {len(v)} | {100*sum(x>0 for x in v)/len(v):.0f}% | {st.mean(v):+.1f} | {sum(v):+.0f} |")
    return "\n".join(["| Set | Trades | Win | Avg pts | Total pts |", "|---|---|---|---|---|"] + out)


print(f"# Guts on ADX flat bottom (peak>={PEAK}, low<={LOW}, flat {FLAT})\n")
print("## Events")
for sym in SYMS:
    for yr in sorted({e["year"] for e in events}):
        E = [e for e in events if e["symbol"] == sym and e["year"] == yr]
        if not E: continue
        big = 120 if sym == "NIFTY" else 400
        pct = lambda f: f"{100*sum(map(f, E))/len(E):.0f}%"
        med = lambda k: st.median([e[k] for e in E if e[k] is not None])
        print(f"- {sym} {yr}: {len(E)} events. New ADX low within 10 candles {pct(lambda e: e['new_low_10'])}, "
              f"within 15 {pct(lambda e: e['new_low_15'])}. ADX up >=5 within 6 candles {pct(lambda e: e['adx_rise_6']>=5)} "
              f"(median rise {med('adx_rise_6'):+.1f}). Median range 6/12/24 candles {med('range_6'):.0f}/{med('range_12'):.0f}/"
              f"{med('range_24'):.0f}; range >= {big} in 24 candles {pct(lambda e: (e['range_24'] or 0) >= big)}.")
print("\n## A. Guts held to 15:15 (option pts, after costs)\n" + summ(a_rows))
print(f"\nMedian guts cost: {st.median([r['cost'] for r in a_rows]) if a_rows else 0:.0f} pts")
print("\n## B. Guts, drop losing leg when P2 fires\n" + summ(b_rows))
print(f"\nDays where P2 fired after the event: {sum(r['exit'] != 'no P2, 15:15' for r in b_rows)} of {len(b_rows)}")
print("\n## C. P2 alone, one 0.70 option (all closed P2 trades)\n" + summ(c_rows))
cr = [r["index_r"] for r in c_rows if r["index_r"] is not None]
if cr: print(f"\nP2 index R for the same trades: {st.mean(cr):+.3f}R avg over {len(cr)}")
for name, rows in (("events", events), ("a_guts", a_rows), ("b_guts_p2", b_rows), ("c_p2", c_rows)):
    if rows:
        with open(f"{OUT}/{name}.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

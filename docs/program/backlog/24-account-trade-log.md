# #24 Account trade log ("My Trades")

Status: Built (4 Nov 2026), Kite pull needs Mac check · Index: [BACKLOG.md](../../../BACKLOG.md) · Separate from #18 (manual journal)

**Why:** Stop overtrading (orders every 1–5 min). Discipline by showing the numbers, no caps or alerts.

**Data in**
- Kite `trades()` + `orders()` + modifications (`order_history`) pulled once a day at 15:45 IST (pradeep, 4 Nov). "Pull today from Kite" button. Kite has no past dates: a missed day = Console CSV for that range.
- Console tradebook CSV import for history. Dedupe on exchange + trade_id. Equity rows skipped.
- Fills insert-only (`account_trades`); orders keep latest state (`account_orders`). Order stats start from the first pull.

**Round trips:** per contract, flat → flat (a fill crossing zero is split). Net = gross − estimated charges: ₹20/order, STT sell side (options 0.1%, 0.15% from 1 Apr 2026; futures 0.02% / 0.05%), exchange, SEBI, stamp, GST.

**On-signal:** same index and view (long CE / short PE = CALL), entered while a live oscout signal was open (late fills excluded).

**Page (/account, admin only, API too)**
- Totals; 10 cards: stop after N trades/day, re-click within 5 min, gave it back, charges, off-signal ₹ vs system, tilt clock, after 2 losses, scalp tax (<2m), order churn, best/worst hour.
- Equity: all trades vs on-signal only.
- Tables: by trade number, by trades/day, gap since previous entry, re-entry after loss (<5 / 5–15 / 15–30 / 30m+), flags, on vs off signal.
- Frequency: trades/day, busiest 15 min, orders/day, cancelled, modified, order gap; day strip; by hour; weekday × hour heatmap.
- Trade log flags: off-signal, averaged down, CE↔PE flip <10m, re-entry <5m after loss, held <2m. Filters: index, date range.

**Acceptance**
- pytest `test_account.py` (parse, CSV dedupe, round trips, charges, stats, sync, admin-only); vitest `Account.test.tsx`.
- On the Mac: import Console CSV; one day of live pull matches Kite's tradebook and order book.

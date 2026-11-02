# #22 Index chips on the dashboard

Status: Built (2 Nov 2026) · Index: [BACKLOG.md](../../../BACKLOG.md)

**Why:** with 3 indexes the dashboard is long; the "Is there a trade right now?" header repeats what the cards say.

**Scope**
- Remove the header ("Is there a trade right now?" + "No active signal · last scan …"); last scan stays in the top bar.
- Chips NIFTY · SENSEX · BANKNIFTY (from `/api/market/symbols`), single-select: one index's card (full width) and commentary at a time; no all-indexes view.
- Chip shows a green/red dot when that index has an active CE/PE signal (so hiding an index never hides a live trade); TEST tag for testing indexes.
- Default NIFTY; choice remembered per browser (`oscout.dashboardSymbol`), NIFTY if the stored one is gone.

**Out of scope:** per-user server-side preference, other pages' Symbol filters.

**Acceptance**
- Selecting a chip unselects the others and swaps the card and commentary; choice survives reload.
- vitest covers chips; existing tests green.

**Built:** `pages/Dashboard.tsx` (`SymbolChips`, `useSelected`), test in `Dashboard.test.tsx`.

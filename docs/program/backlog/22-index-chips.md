# #22 Index chips on the dashboard

Status: Built (2 Nov 2026) · Index: [BACKLOG.md](../../../BACKLOG.md)

**Why:** with 3 indexes the dashboard is long; the "Is there a trade right now?" header repeats what the cards say.

**Scope**
- Remove the header ("Is there a trade right now?" + "No active signal · last scan …"); last scan stays in the top bar.
- Chips NIFTY · SENSEX · BANKNIFTY (from `/api/market/symbols`), multi-select toggles; cards and commentary show only the selected.
- Chip shows a green/red dot when that index has an active CE/PE signal (so hiding an index never hides a live trade); TEST tag for testing indexes.
- At least one chip stays on; choice remembered per browser (`oscout.dashboardSymbols`), default all.
- Grid columns follow the count: 1 full width, 2 side by side, 3 as before.

**Out of scope:** per-user server-side preference, other pages' Symbol filters.

**Acceptance**
- Toggling a chip hides/shows its card and commentary; last chip can't be turned off; choice survives reload.
- vitest covers chips; existing tests green.

**Built:** `pages/Dashboard.tsx` (`SymbolChips`, `useSelected`), test in `Dashboard.test.tsx`.

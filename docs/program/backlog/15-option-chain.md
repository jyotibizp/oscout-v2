# #15 Option chain tab on each index card

Status: Built, needs Kite spot check (2 Nov 2026) · Index: [BACKLOG.md](../../../BACKLOG.md)

**Why:** when a signal fires I open Kite to see the chain (premiums, OI build-up around ATM). I want that view on the card itself.

**Scope**
- Third tab on each NIFTY / SENSEX card: **Signal / Chart / Chain** (tabs from #11). Maximize works as on Chart. Always available, signal or not.
- Current (nearest) weekly expiry only; expiry date shown in the tab header.
- Table like Kite's chain: Call side | Strike | Put side, strikes centred on ATM (ATM ±10), ATM row highlighted, spot price line between strikes.
- **OI view** (default): per side LTP with day change %, OI in lakhs with OI change % vs previous day close.
- **Greeks view** (toggle): per side IV, delta, theta, gamma, vega, from Black-Scholes on LTP (same `options/greeks` code #1 will use).
- When a signal is open, its strike (≈0.70 delta) is marked.
- Backend: `GET /api/options/chain?symbol=NIFTY`.
  - Kite `instruments("NFO" / "BFO")` once a day, cached: picks expiry and strike tokens.
  - Kite `quote()` for the ~42 strikes in one call (LTP, OI, change).
  - Previous-day OI: daily candle with `oi=1` per strike, fetched once a day, cached.
  - Mock provider returns a synthetic chain so cloud/dev sessions work.
- Live: refreshes with the 15s poll, only while the Chain tab is open.

**Out of scope:** other expiries, storing chain snapshots (Phase 2), OI charts / PCR history (#7), placing orders, Kite's Greeks (not in their API).

**Acceptance**
- NIFTY and SENSEX chains match Kite's chain for LTP and OI (spot check, same minute).
- OI / Greeks toggle works; ATM row and signal strike are marked.
- Works at phone width (side columns trimmed to LTP + OI).
- pytest: chain endpoint on mock data; vitest: tab + toggle render; existing tests green.

**Estimate:** 1 story, ~1 day. Depends on #11 (tabs); shares the Greeks code with #1.

**Built:** `GET /api/options/chain?symbol=&strikes=10` (`api/routes.py`), `options/greeks.py` (BS, IV; r = 6.5%), `options/chain.py`, `option_chain()` in Kite + Mock providers, UI `components/OptionChain.tsx`.
- Kite path not yet run on live data: first chain of the day fetches previous-day OI in the background (~15s), so OI chg% shows "—" until then.
- IV per strike from the OTM side, used for both sides: deep ITM premiums often sit below the BS floor and have no IV of their own (fixed 2 Nov after first live look).
- To do on the Mac: spot-check LTP / OI vs Kite's chain (OI unit: Kite quote `oi` shown ÷ 1e5 as lakhs).

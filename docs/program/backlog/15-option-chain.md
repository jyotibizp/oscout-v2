# #15 Option chain tab on each index card

Status: Groomed (14 Oct 2026) · Index: [BACKLOG.md](../../../BACKLOG.md)

**Why:** when a signal fires I open Kite to see the chain (premiums, OI build-up around ATM). I want that view on the card itself.

**Scope**
- Third tab on each NIFTY / SENSEX card: **Signal / Chart / Chain** (tabs from #11). Maximize works as on Chart.
- Current (nearest) weekly expiry only; expiry date shown in the tab header.
- Table like Kite's chain: Call side | Strike | Put side, strikes centred on ATM (ATM ±10), ATM row highlighted, spot price line between strikes.
- **OI view** (default): per side LTP with day change %, OI in lakhs with OI change % vs previous day close.
- **Greeks view** (toggle): per side IV, delta, theta, gamma, vega, from Black-Scholes on LTP (same `options/greeks` code #1 will use).
- Strikes the open signal would trade (≈0.70 delta) marked.
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

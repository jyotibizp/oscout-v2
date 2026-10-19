# #12 Chat companion (AI in the #16 chat box)

Status: Groomed (19 Oct 2026) · Index: [BACKLOG.md](../../../BACKLOG.md) · Needs: #16, #18

**Why:** chips and the rule-based router (#16) cover known asks; I also want to ask anything ("why no signal on SENSEX since 11?", "how do PE trades do when VIX > 16?") and discuss it, live or after hours.

**Approach: tool calling, not NL2SQL or RAG**
- Claude gets read-only oscout tools; it picks which to call and answers from their results.
- Same code as the pages, so numbers always match; sees live data; can't change anything.
- NL2SQL: later, as one extra tool (below), not the core. Our data needs lifecycle rules a raw schema doesn't carry.
- RAG / vectors: not used. Data is numbers and states (vector search can't sum R or filter dates); strategy docs are small enough to go in the prompt.

**Scope**
- Router fallback: asks #16 can't parse go to `POST /api/chat` (message + last few turns); answer streams into the feed.
- Tools (wrap existing services, no new data):
  - `latest_scan(symbol)`, `scan_history(filters)`, `scan_result(id)`
  - `active_signals()`, `signal(id)` (events, gates, tracking), `signal_history(filters)`
  - `trades(filters)`, `performance(symbol, from, to)`, `analytics()`
  - `candles(symbol, tf, limit)`, `data_health()`, `config()`
  - `journal(from, to)` once #18 exists
- Tool results carry a card type, so the answer shows the existing card/table inline (as #16) beside Claude's text.
- System prompt: strategy rules (workflow.md gates, active config), IST, "explain the rules, never invent a signal or price, say when data is stale".
- Backend calls the Claude API; key in `ANTHROPIC_API_KEY`, model in `CLAUDE_MODEL`. No key → box says "AI off", chips still work.
- Admin only (cost); viewers keep chips + router.
- Each chat turn logged to `system_events` (question, tools called, tokens), nothing else stored.

**Later (separate items once tools prove out)**
- `query_sql`: read-only SQLite connection, SELECT only, row cap, schema + lifecycle notes in the tool description.
- MCP server (`python -m app.mcp`) exposing the same tools, so Claude Desktop / phone can ask oscout directly.

**Out of scope:** AI generating or vetoing signals (Phase 3 review), placing orders, vector store, voice.

**Fit:** amends [workflow.md](../../../workflow.md) §33: chatbot allowed as a read-only explainer; no AI prediction. Roadmap Sprint 4.

**Acceptance**
- 10 sample asks (live, history, performance, "why no signal") answered with numbers matching the pages.
- Never calls a write endpoint; stale feed is stated in the answer.
- Works with no API key (AI off, rest of #16 unchanged).
- pytest: tool registry on mock data, chat endpoint with a stubbed model; vitest: fallback path renders streamed answer.

**Estimate:** 2 stories, ~2 days (tools + endpoint; frontend streaming + cards).

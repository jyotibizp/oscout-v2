import { useState } from "react";
import { api, ScanResult, Setup } from "../api/client";
import { CandleChart, ChartOverlay } from "../components/CandleChart";
import { Sparkline } from "../components/Charts";
import { ChainPanel } from "../components/OptionChain";
import { ScanDetailDrawer, SignalDetailDrawer } from "../components/Details";
import { Badge, Dir, ErrorNote, PageHeader } from "../components/ui";
import { n, signed, timeIST } from "../lib/format";
import { useApi } from "../lib/hooks";
import { useSymbols } from "../lib/symbols";

type Step = { k: string; s: string; v: string };

/** The five checks in pipeline order, each with its status and the one number that matters. */
function steps(r: ScanResult): Step[] {
  const d = r.details;
  const g1 = d?.gate1;
  const m1 = g1?.metrics ?? {};
  const g1Failed = g1?.status === "FAIL" && /invalidated|dead market|Insufficient/.test(g1?.reasons?.[0] ?? "");
  const compressed = g1?.status === "PASS" || g1?.status === "WAIT";
  const atrStatus = d?.atr?.metrics?.atr_status;
  const level = m1.compression_level;
  return [
    { k: "Compression", s: compressed ? "PASS" : g1Failed ? "FAILED" : "WAIT",
      v: `${m1.compression_candles ?? 0} candles${level != null ? ` ≤ ${n(level)}` : ""}` },
    { k: "Breakout", s: g1?.status === "PASS" ? "PASS" : g1Failed ? "FAILED" : "WAIT",
      v: m1.adx_at != null ? `${n(m1.adx_before)} → ${n(m1.adx_at)}` : `5m ADX ${n(r.adx5)}` },
    { k: "15m trend", s: d?.gate2?.status === "PASS" ? "PASS" : d?.gate2?.status === "FAIL" ? "FAILED" : "WAIT",
      v: `ADX ${n(r.adx15)} · slope ${signed(d?.gate2?.metrics?.slope)}` },
    { k: "ATR", s: atrStatus === "EXHAUSTED" ? "EXHAUSTED" : atrStatus === "WARNING" ? "WAIT" : atrStatus ? "PASS" : "WAIT",
      v: atrStatus ? `${n(d?.atr?.metrics?.ratio, 2)}× ${atrStatus.toLowerCase()}${d?.atr?.metrics?.mode === "warning" && atrStatus === "EXHAUSTED" ? " · warning only" : ""}` : "—" },
    { k: "VIX", s: d?.vix?.status === "PASS" ? "PASS" : d?.vix?.status === "FAIL" ? "FAILED" : "WAIT",
      v: `${n(r.vix, 2)} (${signed(r.vix_change_pct)}%)` },
  ];
}

function Stepper({ r }: { r: ScanResult }) {
  return (
    <ol className="grid grid-cols-2 sm:grid-cols-5 gap-2">
      {steps(r).map((x, i) => (
        <li key={x.k} className="rounded-lg border border-line bg-raise/40 px-2.5 py-2">
          <div className="text-xs text-ink-faint">{i + 1}. {x.k}</div>
          <div className="mt-1"><Badge s={x.s} /></div>
          <div className="mt-1 text-xs num text-ink leading-snug">{x.v}</div>
        </li>
      ))}
    </ol>
  );
}

function SignalBlock({ s, onOpen }: { s: Setup; onOpen: () => void }) {
  const up = s.direction === "CALL";
  const t = s.tracking;
  return (
    <div className={`rounded-lg border-l-4 ${up ? "border-l-good" : "border-l-bad"} bg-raise/60 px-4 py-3`}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className={`text-xl font-bold ${up ? "text-good" : "text-bad"}`}>{s.direction} BUY <span className="text-sm font-medium text-ink-faint">({up ? "CE" : "PE"})</span></div>
        <div className="flex items-center gap-2">{t && <Badge s={t.verdict} />}<Badge s={s.state} /><button className="btn" onClick={onOpen}>Lifecycle</button></div>
      </div>
      <dl className="mt-2 grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-1 text-sm">
        <div><dt className="text-xs text-ink-faint">Signal</dt><dd className="num">{timeIST(s.signal_ts)} IST</dd></div>
        <div><dt className="text-xs text-ink-faint">Entry (index)</dt><dd className="num">{n(s.entry_price, 2)}</dd></div>
        <div><dt className="text-xs text-ink-faint">Stop{t?.stop_moved ? " (moved)" : ""}</dt>
          <dd className="num text-bad">{n(t?.stop ?? s.stop_price, 1)}{t?.stop_moved && <span className="text-xs text-ink-faint"> was {n(t.initial_stop, 1)}</span>}</dd></div>
        <div><dt className="text-xs text-ink-faint">Target</dt><dd className="num text-good">{n(s.target_price, 1)}</dd></div>
      </dl>
      {t && (
        <>
          <dl className="mt-3 pt-3 border-t border-line grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-1 text-sm">
            <div><dt className="text-xs text-ink-faint">Now ({timeIST(t.ts)})</dt><dd className="num">{n(t.price, 2)}</dd></div>
            <div><dt className="text-xs text-ink-faint">P&amp;L</dt>
              <dd className={`num font-semibold ${t.pnl_points > 0 ? "text-good" : t.pnl_points < 0 ? "text-bad" : ""}`}>{signed(t.pnl_points, 1)} pts · {signed(t.r, 2)}R</dd></div>
            <div><dt className="text-xs text-ink-faint">To stop / target</dt><dd className="num">{n(t.to_stop, 0)} / {n(t.to_target, 0)}</dd></div>
            <div><dt className="text-xs text-ink-faint">Held · left</dt><dd className="num">{t.held} · {t.candles_left} candles</dd></div>
          </dl>
          <p className="mt-2 text-xs text-ink-soft">
            5m ADX {n(t.adx)} (peak {n(t.peak_adx)}){t.adx_declines ? `, falling ${t.adx_declines}` : ", not falling"}
            {t.reasons.length ? ` · ${t.reasons.join(" · ")}` : ""}
          </p>
        </>
      )}
    </div>
  );
}

const EXIT_LABEL: Record<string, string> = {
  STOP: "Stop loss", TRAIL_STOP: "Trailing stop", TARGET: "Target", ADX_EXHAUSTION: "ADX exhaustion",
  ADX_PEAK_DECLINE: "ADX off peak", DI_REVERSAL: "DI reversal", SESSION_END: "Session end", MAX_HOLD: "Max hold",
};

function LastExit({ s }: { s: Setup }) {
  const r = s.trade?.r_multiple;
  return (
    <p className="mb-2 text-xs text-ink-soft">
      <Badge s="EXIT" /> Last {s.direction === "CALL" ? "CE" : "PE"} exited {timeIST(s.exit_ts)} IST at {n(s.exit_price, 1)}:{" "}
      {EXIT_LABEL[s.exit_reason ?? ""] ?? s.exit_reason}
      {s.trade?.pnl_points != null && <span className={`num font-semibold ${s.trade.pnl_points > 0 ? "text-good" : "text-bad"}`}> {signed(s.trade.pnl_points, 1)} pts{r != null ? ` (${signed(r, 2)}R)` : ""}</span>}
    </p>
  );
}

const CARD_ROWS = 5; // header · verdict · signal or checks · chart · footer, shared by both cards

type Tab = "signal" | "chart" | "chain";
const TABS: { k: Tab; label: string }[] = [{ k: "signal", label: "Signal" }, { k: "chart", label: "Chart" }, { k: "chain", label: "Chain" }];
const tabKey = (sym: string) => `oscout.cardTab.${sym}`;

/** Tab per card, remembered in this browser (storage may be blocked: then it just defaults to Signal). */
function useCardTab(sym: string): [Tab, (t: Tab) => void] {
  const [tab, setTab] = useState<Tab>(() => {
    try { const v = localStorage.getItem(tabKey(sym)); return TABS.some((t) => t.k === v) ? (v as Tab) : "signal"; } catch { return "signal"; }
  });
  return [tab, (t) => { setTab(t); try { localStorage.setItem(tabKey(sym), t); } catch { /* private mode */ } }];
}

function Tabs({ sym, tab, onTab }: { sym: string; tab: Tab; onTab: (t: Tab) => void }) {
  return (
    <div role="tablist" aria-label={`${sym} view`} className="inline-flex rounded-full border border-line p-0.5 text-xs">
      {TABS.map((t) => (
        <button key={t.k} role="tab" aria-selected={tab === t.k} onClick={() => onTab(t.k)}
          className={`rounded-full px-3 py-1 font-medium ${tab === t.k ? "bg-accent-strong text-white" : "text-accent hover:bg-raise"}`}>{t.label}</button>
      ))}
    </div>
  );
}

/** Chart tab body: 5m candles + ADX pane with trade lines and markers; ⤢ opens the full-screen view with more history. */
function ChartTab({ sym, scanId, setups, level }: { sym: string; scanId?: number; setups: Setup[]; level?: number | null }) {
  const [max, setMax] = useState(false);
  const small = useApi(() => api.candles(sym, "5m", 300), [sym, scanId]);
  const big = useApi(() => (max ? api.candles(sym, "5m", 1000) : Promise.resolve(null)), [sym, scanId, max]);
  return (
    <div className="min-w-0">
      <div className="mb-2 flex items-center justify-between text-xs text-ink-faint">
        <span>5m · drag to pan, scroll to zoom</span>
        <button className="btn !px-3 !py-1" onClick={() => setMax(true)} aria-label="Maximize chart">⤢ Maximize</button>
      </div>
      {small.data?.length ? <CandleChart candles={small.data} setups={setups} level={level} height={340} />
        : <p className="text-sm text-ink-faint">{small.error ?? "Loading candles…"}</p>}
      {max && <ChartOverlay sym={sym} candles={big.data ?? small.data ?? []} setups={setups} level={level} onClose={() => setMax(false)} />}
    </div>
  );
}

/** One index card. Its rows sit on the parent grid (subgrid), so both cards line up section by section. */
/** Chain tab body: polls every 15s only while this tab is open (it unmounts otherwise). */
function ChainTab({ sym }: { sym: string }) {
  const { data, error } = useApi(() => api.chain(sym), [sym], 15000);
  return <ChainPanel sym={sym} c={data} error={error} />;
}

function SymbolCard({ sym, testing, r, signal, lastExit, setups, onSignal, onDetails, className = "" }: {
  sym: string; testing?: boolean; r: ScanResult | null; signal?: Setup; lastExit?: Setup; setups: Setup[];
  onSignal: (id: number) => void; onDetails: (id: number) => void; className?: string;
}) {
  const [tab, setTab] = useCardTab(sym);
  const { data: candles } = useApi(() => (tab === "signal" ? api.candles(sym, "5m", 90) : Promise.resolve(null)), [sym, r?.id, tab], 60000);
  const rows = { gridRow: `span ${CARD_ROWS}`, gridTemplateRows: "subgrid" } as const;
  if (!r) return (
    <section className={`card p-5 grid gap-4 ${className}`} style={rows}>
      <h2 className="text-lg font-bold tracking-wide">{sym}</h2>
      <p className="text-sm text-ink-faint">No scan yet. Press SCAN NOW.</p>
    </section>
  );
  const isSignal = r.final_result === "SIGNAL";
  const m1 = r.details?.gate1?.metrics ?? {};
  const level: number | undefined = m1.compression_level ?? undefined;
  const verdict = signal
    ? `${signal.direction === "CALL" ? "CE" : "PE"} signal active since ${timeIST(signal.signal_ts)} IST. New entries wait until it exits.`
    : r.details?.commentary?.headline ?? r.rejection_reason ?? r.details?.reason;
  const header = (
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 className="text-lg font-bold tracking-wide">{sym}{testing && <span className="ml-2 align-middle rounded border border-warn/50 bg-warn/10 px-1.5 py-0.5 text-[11px] font-semibold text-warn" title="On trial: scanned and recorded, no chime, until the 2025 + 2026 backtest passes">TESTING</span>}</h2>
        <div className="text-xs text-ink-faint">Candle {timeIST(r.candle_ts)} IST · config v{r.config_version}</div>
      </div>
      <div className="flex flex-wrap items-center justify-end gap-2">
        <Dir d={r.direction} />
        <Badge s={isSignal ? "SIGNAL" : r.state} label={isSignal ? `${r.direction} BUY` : undefined} />
        <Tabs sym={sym} tab={tab} onTab={setTab} />
      </div>
    </header>
  );
  if (tab !== "signal") return (
    <section className={`card p-5 grid gap-4 ${isSignal || signal ? "border-accent" : ""} ${className}`} style={rows}>
      {header}
      <div style={{ gridRow: `span ${CARD_ROWS - 1}` }} className="min-w-0">
        {tab === "chart" ? <ChartTab sym={sym} scanId={r.id} setups={setups} level={level} /> : <ChainTab sym={sym} />}
      </div>
    </section>
  );
  return (
    <section className={`card p-5 grid gap-4 ${isSignal || signal ? "border-accent" : ""} ${className}`} style={rows}>
      {header}

      <p className="text-base text-ink font-medium leading-snug">{verdict ?? "—"}</p>

      <div>{signal ? <SignalBlock s={signal} onOpen={() => onSignal(signal.id)} /> : <>{lastExit && <LastExit s={lastExit} />}<Stepper r={r} /></>}</div>

      <div className="self-end">
        <Sparkline values={(candles ?? []).map((c) => c.adx)} threshold={level} height={64} />
        <div className="flex justify-between gap-2 text-xs text-ink-faint mt-1">
          <span>5m ADX · last 90 candles</span>
          <span>{level != null ? `dashed = compression level ${n(level)}${m1.adx_peak ? ` (${Math.round((level / m1.adx_peak) * 100)}% of peak ${n(m1.adx_peak)})` : ""}` : ""}</span>
        </div>
      </div>

      <div className="flex justify-end"><button className="btn" onClick={() => onDetails(r.id)}>Full gate details</button></div>
    </section>
  );
}

/** One full-width commentary widget for both indexes, side by side. */
function CommentaryPanel({ syms, active, order }: { syms: Record<string, ScanResult | null | undefined>; active: Setup[]; order: string[] }) {
  return (
    <section className="card p-5">
      <h2 className="text-xs uppercase tracking-widest text-ink-faint mb-4">Commentary</h2>
      <div className="grid gap-6 xl:gap-8 xl:grid-cols-2 2xl:grid-cols-3">
        {order.map((sym, i) => {
          const r = syms[sym];
          const c = r?.details?.commentary;
          const sig = active.find((a) => a.symbol === sym);
          return (
            <div key={sym} className={i ? "border-t border-line pt-6 xl:border-t-0 xl:pt-0" : ""}>
              <div className="flex items-baseline justify-between mb-2">
                <span className="text-sm font-bold tracking-wide">{sym}</span>
                <span className="text-xs text-ink-faint">{c?.candle_close ? `${c.candle_close} IST candle` : ""}</span>
              </div>
              {!c ? <p className="text-sm text-ink-faint">No commentary yet.</p> : (
                <div className="space-y-3">
                  <p className="text-sm text-ink font-medium">
                    {sig ? `${sig.direction === "CALL" ? "CE" : "PE"} signal active since ${timeIST(sig.signal_ts)} IST.` : c.headline}
                  </p>
                  <ul className="space-y-1.5">
                    {c.lines.map((l) => (
                      <li key={l.gate} className="grid grid-cols-[92px_auto_1fr] items-start gap-2 text-xs text-ink-soft leading-relaxed">
                        <span className="text-ink-faint pt-0.5">{l.gate}</span>
                        <Badge s={l.status} />
                        <span>{l.text}</span>
                      </li>
                    ))}
                  </ul>
                  {(c.compression || c.rules.length > 0 || c.outlook) && (
                    <div className="space-y-1.5 border-t border-line/60 pt-3">
                      <div className="flex items-center gap-2">
                        <span className="text-xs uppercase tracking-widest text-ink-faint">What happens next</span>
                        {sig && <Badge s="PAUSED" label="Paused · signal active" />}
                      </div>
                      <div className={`space-y-1.5 ${sig ? "opacity-50" : ""}`} title={sig ? "No new entry on this index until the active signal exits" : undefined}>
                        {c.compression && <p className="text-sm text-ink-soft">{c.compression.text}</p>}
                        {c.rules.map((x) => (
                          <p key={x.direction} className="text-sm text-ink-soft">
                            <span className={`font-semibold ${x.direction === "CALL" ? "text-good" : "text-bad"}`}>{x.option}</span> {x.text}
                          </p>
                        ))}
                        {c.outlook && <p className="text-sm text-ink-soft">{c.outlook}</p>}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

export default function Dashboard() {
  const latest = useApi(api.latest, [], 15000);
  const sig = useApi(api.activeSignals, [], 15000);
  const [openSignal, setOpenSignal] = useState<number | null>(null);
  const [openScan, setOpenScan] = useState<number | null>(null);
  const syms = latest.data?.symbols ?? {};
  const active = sig.data?.active ?? [];
  const run = latest.data?.run;
  const symbols = useSymbols();
  const summary = active.length
    ? `${active.length} active signal${active.length > 1 ? "s" : ""}: ${active.map((s) => `${s.symbol} ${s.direction}`).join(", ")}`
    : sig.data?.pending.length ? `${sig.data.pending.length} setup(s) waiting for 15m confirmation` : "No active signal";
  return (
    <div className="max-w-[1920px]">
      <PageHeader title="Is there a trade right now?"
        sub={run ? `${summary} · last scan #${run.id} (${run.trigger}) at ${timeIST(run.started_at)} IST` : "No scans yet"} />
      <ErrorNote error={latest.error} />
      <div className="grid gap-x-5 gap-y-5 xl:gap-y-0 xl:grid-cols-2 2xl:grid-cols-3">
        {symbols.map(({ symbol: s, testing }, i) => (
          <SymbolCard key={s} sym={s} testing={testing} className={i >= 2 ? "xl:mt-5 2xl:mt-0" : ""}
            r={syms[s] ?? null} signal={active.find((a) => a.symbol === s)}
            lastExit={sig.data?.exited_today.find((x) => x.symbol === s)}
            setups={[...active, ...(sig.data?.pending ?? []), ...(sig.data?.exited_today ?? [])].filter((x) => x.symbol === s)}
            onSignal={setOpenSignal} onDetails={setOpenScan} />
        ))}
      </div>
      <div className="mt-5"><CommentaryPanel syms={syms} active={active} order={symbols.map((x) => x.symbol)} /></div>
      <SignalDetailDrawer id={openSignal} onClose={() => setOpenSignal(null)} />
      <ScanDetailDrawer id={openScan} onClose={() => setOpenScan(null)} />
    </div>
  );
}

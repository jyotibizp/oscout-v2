import { useState } from "react";
import { api, ScanResult, Setup } from "../api/client";
import { Sparkline } from "../components/Charts";
import { ScanDetailDrawer, SignalDetailDrawer } from "../components/Details";
import { Badge, Dir, ErrorNote, PageHeader } from "../components/ui";
import { n, signed, timeIST } from "../lib/format";
import { useApi } from "../lib/hooks";

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
  return (
    <div className={`rounded-lg border-l-4 ${up ? "border-l-good" : "border-l-bad"} bg-raise/60 px-4 py-3`}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className={`text-xl font-bold ${up ? "text-good" : "text-bad"}`}>{s.direction} BUY <span className="text-sm font-medium text-ink-faint">({up ? "CE" : "PE"})</span></div>
        <div className="flex items-center gap-2"><Badge s={s.state} /><button className="btn" onClick={onOpen}>Lifecycle</button></div>
      </div>
      <dl className="mt-2 grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-1 text-sm">
        <div><dt className="text-xs text-ink-faint">Signal</dt><dd className="num">{timeIST(s.signal_ts)} IST</dd></div>
        <div><dt className="text-xs text-ink-faint">Entry (index)</dt><dd className="num">{n(s.entry_price, 2)}</dd></div>
        <div><dt className="text-xs text-ink-faint">Stop</dt><dd className="num text-bad">{n(s.stop_price, 1)}</dd></div>
        <div><dt className="text-xs text-ink-faint">Target</dt><dd className="num text-good">{n(s.target_price, 1)}</dd></div>
      </dl>
    </div>
  );
}

const CARD_ROWS = 5; // header · verdict · signal or checks · chart · footer, shared by both cards

/** One index card. Its rows sit on the parent grid (subgrid), so both cards line up section by section. */
function SymbolCard({ sym, r, signal, onSignal, onDetails }: {
  sym: string; r: ScanResult | null; signal?: Setup; onSignal: (id: number) => void; onDetails: (id: number) => void;
}) {
  const { data: candles } = useApi(() => api.candles(sym, "5m", 90), [sym, r?.id], 60000);
  const rows = { gridRow: `span ${CARD_ROWS}`, gridTemplateRows: "subgrid" } as const;
  if (!r) return (
    <section className="card p-5 grid gap-4" style={rows}>
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
  return (
    <section className={`card p-5 grid gap-4 ${isSignal || signal ? "border-accent" : ""}`} style={rows}>
      <header className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold tracking-wide">{sym}</h2>
          <div className="text-xs text-ink-faint">Candle {timeIST(r.candle_ts)} IST · config v{r.config_version}</div>
        </div>
        <div className="flex items-center gap-2">
          <Dir d={r.direction} />
          <Badge s={isSignal ? "SIGNAL" : r.state} label={isSignal ? `${r.direction} BUY` : undefined} />
        </div>
      </header>

      <p className="text-base text-ink font-medium leading-snug">{verdict ?? "—"}</p>

      <div>{signal ? <SignalBlock s={signal} onOpen={() => onSignal(signal.id)} /> : <Stepper r={r} />}</div>

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
function CommentaryPanel({ syms, active }: { syms: Record<string, ScanResult | null | undefined>; active: Setup[] }) {
  return (
    <section className="card p-5">
      <h2 className="text-xs uppercase tracking-widest text-ink-faint mb-4">Commentary</h2>
      <div className="grid gap-6 xl:grid-cols-2 xl:divide-x xl:divide-line">
        {["NIFTY", "SENSEX"].map((sym, i) => {
          const r = syms[sym];
          const c = r?.details?.commentary;
          const sig = active.find((a) => a.symbol === sym);
          return (
            <div key={sym} className={i ? "xl:pl-6" : ""}>
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
  const summary = active.length
    ? `${active.length} active signal${active.length > 1 ? "s" : ""}: ${active.map((s) => `${s.symbol} ${s.direction}`).join(", ")}`
    : sig.data?.pending.length ? `${sig.data.pending.length} setup(s) waiting for 15m confirmation` : "No active signal";
  return (
    <div className="max-w-7xl">
      <PageHeader title="Is there a trade right now?"
        sub={run ? `${summary} · last scan #${run.id} (${run.trigger}) at ${timeIST(run.started_at)} IST` : "No scans yet"} />
      <ErrorNote error={latest.error} />
      <div className="grid gap-x-5 gap-y-5 xl:gap-y-0 xl:grid-cols-2">
        {["NIFTY", "SENSEX"].map((s) => (
          <SymbolCard key={s} sym={s} r={syms[s] ?? null} signal={active.find((a) => a.symbol === s)}
            onSignal={setOpenSignal} onDetails={setOpenScan} />
        ))}
      </div>
      <div className="mt-5"><CommentaryPanel syms={syms} active={active} /></div>
      <SignalDetailDrawer id={openSignal} onClose={() => setOpenSignal(null)} />
      <ScanDetailDrawer id={openScan} onClose={() => setOpenScan(null)} />
    </div>
  );
}

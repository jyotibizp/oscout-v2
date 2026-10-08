import { useState } from "react";
import { api, ScanResult } from "../api/client";
import { Sparkline } from "../components/Charts";
import { SignalDetailDrawer } from "../components/Details";
import { Pipeline } from "../components/Pipeline";
import { SignalCard } from "../components/SignalCard";
import { Badge, Dir, ErrorNote, PageHeader } from "../components/ui";
import { n, signed, timeIST } from "../lib/format";
import { useApi } from "../lib/hooks";

/** Map the stored scan result to the dashboard rows: PASS / WAIT / FAILED / EXHAUSTED / SIGNAL. */
function rows(r: ScanResult) {
  const d = r.details;
  const g1 = d?.gate1;
  const comp = g1?.metrics?.compression_candles;
  const g1Failed = g1?.status === "FAIL" && /invalidated|dead market|Insufficient/.test(g1?.reasons?.[0] ?? "");
  const compressionStatus = g1?.status === "PASS" || g1?.status === "WAIT" ? "PASS" : g1Failed ? "FAILED" : "WAIT";
  const atrStatus = d?.atr?.metrics?.atr_status;
  return [
    { k: "ADX Status", s: (r.adx5 ?? 0) >= 25 ? "TRENDING" : (r.adx5 ?? 0) <= 20 ? "COMPRESSED" : "NEUTRAL", v: `5m ${n(r.adx5)}  +DI ${n(r.pdi5)} −DI ${n(r.mdi5)}`, plain: true },
    { k: "Compression", s: compressionStatus, v: comp !== undefined ? `${comp} candles` : "" },
    { k: "Breakout", s: g1?.status === "PASS" ? "PASS" : g1Failed ? "FAILED" : "WAIT", v: g1?.metrics?.adx_at ? `${n(g1.metrics.adx_before)} → ${n(g1.metrics.adx_at)}` : "" },
    { k: "15M Confirmation", s: d?.gate2?.status === "PASS" ? "PASS" : d?.gate2?.status === "SKIP" ? "WAIT" : "FAILED", v: `15m ADX ${n(r.adx15)} slope ${signed(d?.gate2?.metrics?.slope)}` },
    { k: "ATR", s: atrStatus === "EXHAUSTED" ? "EXHAUSTED" : atrStatus === "WARNING" ? "WAIT" : atrStatus ? "PASS" : "WAIT", v: atrStatus ? `${atrStatus} · ${n(d?.atr?.metrics?.ratio, 2)}×` : "" },
    { k: "VIX", s: d?.vix?.status === "PASS" ? "PASS" : d?.vix?.status === "FAIL" ? "FAILED" : "WAIT", v: `${n(r.vix, 2)} (${signed(r.vix_change_pct)}%)` },
  ];
}

function SymbolPanel({ sym, r }: { sym: string; r: ScanResult | null }) {
  const { data: candles } = useApi(() => api.candles(sym, "5m", 90), [sym, r?.id], 60000);
  if (!r) return <div className="card p-4"><div className="font-semibold">{sym}</div><p className="text-sm text-ink-faint mt-2">No scan yet — press SCAN NOW.</p></div>;
  const signal = r.final_result === "SIGNAL";
  const finalLabel = signal ? `${r.direction} BUY` : r.state === "ACTIVE" ? `ACTIVE ${r.direction ?? ""}` : "NO SIGNAL";
  return (
    <div className={`card p-4 ${signal ? "border-accent" : ""}`}>
      <div className="flex items-center justify-between">
        <div>
          <div className="text-base font-semibold tracking-wide">{sym}</div>
          <div className="text-xs text-ink-faint">Candle {timeIST(r.candle_ts)} IST · v{r.config_version}</div>
        </div>
        <div className="text-right">
          <Badge s={signal ? "SIGNAL" : r.state} label={finalLabel} />
          <div className="mt-1"><Dir d={r.direction} /></div>
        </div>
      </div>
      <div className="mt-3"><Sparkline values={(candles ?? []).map((c) => c.adx)} threshold={20} /></div>
      <div className="text-[10px] text-ink-faint text-right">5m ADX · dashed = compression threshold</div>
      <table className="w-full mt-2">
        <tbody>
          {rows(r).map((x) => (
            <tr key={x.k} className="border-b border-line/50">
              <td className="py-1.5 text-sm text-ink-soft">{x.k}</td>
              <td className="py-1.5 text-xs num text-ink-faint text-right pr-3">{x.v}</td>
              <td className="py-1.5 text-right w-28">{x.plain ? <span className="text-xs text-ink">{x.s}</span> : <Badge s={x.s} />}</td>
            </tr>
          ))}
          <tr>
            <td className="py-2 text-sm font-semibold">Final Signal</td>
            <td />
            <td className="py-2 text-right">{signal ? <Badge s="SIGNAL" label="SIGNAL" /> : <Badge s={r.state === "ACTIVE" ? "ACTIVE" : "WATCHING"} label={r.state === "ACTIVE" ? "ACTIVE" : "NONE"} />}</td>
          </tr>
        </tbody>
      </table>
      <p className="mt-3 text-xs text-ink-soft leading-relaxed">{r.final_result === "SIGNAL" ? r.details?.reason : r.rejection_reason ?? r.details?.reason}</p>
    </div>
  );
}

export default function Dashboard() {
  const latest = useApi(api.latest, [], 15000);
  const sig = useApi(api.activeSignals, [], 15000);
  const [open, setOpen] = useState<number | null>(null);
  const syms = latest.data?.symbols ?? {};
  const active = sig.data?.active ?? [];
  return (
    <div>
      <PageHeader title="Is there a trade right now?" sub={latest.data?.run ? `Last scan #${latest.data.run.id} (${latest.data.run.trigger}) at ${timeIST(latest.data.run.started_at)} IST` : "No scans yet"} />
      <ErrorNote error={latest.error} />
      {active.length > 0 ? (
        <div className="grid gap-4 lg:grid-cols-2 mb-6">{active.map((s) => <SignalCard key={s.id} s={s} onOpen={() => setOpen(s.id)} />)}</div>
      ) : (
        <div className="card px-4 py-3 mb-6 text-sm text-ink-soft">No active signal. {sig.data?.pending.length ? `${sig.data.pending.length} setup(s) waiting for 15m confirmation.` : "Watching for ADX compression → breakout."}</div>
      )}
      <div className="grid gap-4 xl:grid-cols-2">
        {["NIFTY", "SENSEX"].map((s) => <SymbolPanel key={s} sym={s} r={syms[s] ?? null} />)}
      </div>
      <div className="grid gap-4 xl:grid-cols-2 mt-6">
        {["NIFTY", "SENSEX"].map((s) => syms[s] ? (
          <div key={s} className="card p-4">
            <div className="text-xs uppercase tracking-widest text-ink-faint mb-3">{s} · qualification pipeline</div>
            <Pipeline r={syms[s]!} />
          </div>
        ) : null)}
      </div>
      <SignalDetailDrawer id={open} onClose={() => setOpen(null)} />
    </div>
  );
}

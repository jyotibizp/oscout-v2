import { useState } from "react";
import { api } from "../api/client";
import { ScanDetailDrawer } from "../components/Details";
import { Badge, Dir, ErrorNote, Field, PageHeader } from "../components/ui";
import { dateTimeIST, n } from "../lib/format";
import { useApi } from "../lib/hooks";

const PAGE = 100;

export default function ScanHistory() {
  const [f, setF] = useState<Record<string, string>>({});
  const [page, setPage] = useState(0);
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => { setPage(0); setF({ ...f, [k]: e.target.value }); };
  const { data, error, loading } = useApi(() => api.scanHistory({ ...f, limit: PAGE, offset: page * PAGE }), [JSON.stringify(f), page], 30000);
  const [open, setOpen] = useState<number | null>(null);
  const total = data?.total ?? 0;
  return (
    <div>
      <PageHeader title="Scan History" sub="Every evaluation of every symbol — click a row to see exactly why" />
      <div className="card p-3 mb-4 flex flex-wrap gap-3 items-end">
        <Field label="From"><input type="date" className="input" onChange={set("date_from")} /></Field>
        <Field label="To"><input type="date" className="input" onChange={set("date_to")} /></Field>
        <Field label="Symbol"><select className="input" onChange={set("symbol")}><option value="">All</option><option>NIFTY</option><option>SENSEX</option></select></Field>
        <Field label="Direction"><select className="input" onChange={set("direction")}><option value="">All</option><option>CALL</option><option>PUT</option></select></Field>
        <Field label="Final"><select className="input" onChange={set("final")}><option value="">All</option><option value="SIGNAL">Signal</option><option value="NO_SIGNAL">No signal</option></select></Field>
        <Field label="State"><select className="input" onChange={set("state")}><option value="">All</option>
          {["WATCHING", "COMPRESSION", "BREAKOUT_DETECTED", "WAITING_CONFIRMATION", "QUALIFIED", "SIGNAL_GENERATED", "ACTIVE", "EXIT_TRIGGERED", "EXPIRED", "REJECTED"].map((s) => <option key={s}>{s}</option>)}</select></Field>
        <Field label="Gate failure"><select className="input" onChange={set("gate_failed")}><option value="">Any</option><option value="gate1">Gate 1</option><option value="gate2">Gate 2</option><option value="atr_filter">ATR</option><option value="vix_filter">VIX</option></select></Field>
        <span className="text-xs text-ink-faint ml-auto">{loading ? "Loading…" : `${total} results`}</span>
      </div>
      <ErrorNote error={error} />
      <div className="card overflow-x-auto">
        <table className="w-full">
          <thead><tr>{["Scan", "Candle", "Symbol", "5M ADX", "+DI / −DI", "15M ADX", "ATR", "VIX", "Gate 1", "Gate 2", "ATR", "VIX", "State", "Direction", "Reason", "Cfg"].map((h, i) => <th key={i} className="th">{h}</th>)}</tr></thead>
          <tbody>
            {(data?.items ?? []).map((r) => (
              <tr key={r.id} className="hover:bg-raise cursor-pointer" onClick={() => setOpen(r.id)}>
                <td className="td num text-ink-faint">#{r.scan_run_id}</td>
                <td className="td num">{dateTimeIST(r.candle_ts)}</td>
                <td className="td">{r.symbol}</td>
                <td className="td num">{n(r.adx5)}</td>
                <td className="td num text-ink-soft">{n(r.pdi5)} / {n(r.mdi5)}</td>
                <td className="td num">{n(r.adx15)}</td>
                <td className="td text-xs">{r.atr_status ?? "—"}</td>
                <td className="td num">{n(r.vix, 2)}</td>
                <td className="td"><Badge s={r.gate1} /></td><td className="td"><Badge s={r.gate2} /></td>
                <td className="td"><Badge s={r.atr_filter} /></td><td className="td"><Badge s={r.vix_filter} /></td>
                <td className="td"><Badge s={r.final_result === "SIGNAL" ? "SIGNAL" : r.state} /></td>
                <td className="td"><Dir d={r.direction} /></td>
                <td className="td text-xs text-ink-soft max-w-[320px] truncate" title={r.rejection_reason ?? r.reason ?? ""}>{r.rejection_reason ?? r.reason}</td>
                <td className="td num text-ink-faint text-xs">v{r.config_version}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-end gap-2 mt-3 text-xs text-ink-faint">
        <button className="btn" disabled={page === 0} onClick={() => setPage(page - 1)}>Prev</button>
        <span>Page {page + 1} of {Math.max(1, Math.ceil(total / PAGE))}</span>
        <button className="btn" disabled={(page + 1) * PAGE >= total} onClick={() => setPage(page + 1)}>Next</button>
      </div>
      <ScanDetailDrawer id={open} onClose={() => setOpen(null)} />
    </div>
  );
}

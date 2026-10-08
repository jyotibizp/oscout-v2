import { useState } from "react";
import { api } from "../api/client";
import { SignalDetailDrawer } from "../components/Details";
import { SignalCard } from "../components/SignalCard";
import { Badge, Dir, Empty, ErrorNote, Field, PageHeader } from "../components/ui";
import { dateTimeIST, n, signed } from "../lib/format";
import { useApi } from "../lib/hooks";

export function LiveSignals() {
  const { data, error } = useApi(api.activeSignals, [], 15000);
  const [open, setOpen] = useState<number | null>(null);
  return (
    <div>
      <PageHeader title="Live Signals" sub="Active signals and setups waiting for 15m confirmation" />
      <ErrorNote error={error} />
      <h2 className="text-sm font-semibold text-ink-soft mb-2">Active</h2>
      {data?.active.length ? (
        <div className="grid gap-4 lg:grid-cols-2 mb-6">{data.active.map((s) => <SignalCard key={s.id} s={s} onOpen={() => setOpen(s.id)} />)}</div>
      ) : <div className="mb-6"><Empty>No active signal</Empty></div>}
      <h2 className="text-sm font-semibold text-ink-soft mb-2">Waiting for confirmation</h2>
      {data?.pending.length ? (
        <div className="card overflow-x-auto">
          <table className="w-full"><thead><tr>{["Breakout", "Symbol", "Direction", "ADX", "Compression", "State", ""].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
            <tbody>{data.pending.map((s) => (
              <tr key={s.id} className="hover:bg-raise cursor-pointer" onClick={() => setOpen(s.id)}>
                <td className="td num">{dateTimeIST(s.breakout_ts)}</td><td className="td">{s.symbol}</td><td className="td"><Dir d={s.direction} /></td>
                <td className="td num">{n(s.breakout?.adx_before)} → {n(s.breakout?.adx_at)}</td><td className="td num">{s.breakout?.compression_candles} candles</td>
                <td className="td"><Badge s={s.state} /></td><td className="td text-ink-faint text-xs">details →</td>
              </tr>))}</tbody></table>
        </div>
      ) : <Empty>No pending setups</Empty>}
      <SignalDetailDrawer id={open} onClose={() => setOpen(null)} />
    </div>
  );
}

export function SignalHistory() {
  const [f, setF] = useState<Record<string, string>>({});
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });
  const { data, error, loading } = useApi(() => api.signalHistory({ ...f, limit: 300 }), [JSON.stringify(f)]);
  const [open, setOpen] = useState<number | null>(null);
  return (
    <div>
      <PageHeader title="Signal History" sub="Every setup from breakout to exit — qualified or rejected" />
      <div className="card p-3 mb-4 flex flex-wrap gap-3 items-end">
        <Field label="From"><input type="date" className="input" onChange={set("date_from")} /></Field>
        <Field label="To"><input type="date" className="input" onChange={set("date_to")} /></Field>
        <Field label="Symbol"><select className="input" onChange={set("symbol")}><option value="">All</option><option>NIFTY</option><option>SENSEX</option></select></Field>
        <Field label="Direction"><select className="input" onChange={set("direction")}><option value="">All</option><option>CALL</option><option>PUT</option></select></Field>
        <Field label="Result"><select className="input" onChange={set("outcome")}><option value="">All</option><option value="qualified">Qualified</option><option value="rejected">Rejected / expired</option></select></Field>
        <Field label="Status"><select className="input" onChange={set("status")}><option value="">All</option><option value="active">Active</option><option value="closed">Closed</option></select></Field>
        <Field label="VIX regime"><select className="input" onChange={set("vix_regime")}><option value="">All</option><option value="LOW">Low (&lt;13)</option><option value="NORMAL">Normal (13–18)</option><option value="HIGH">High (18+)</option></select></Field>
        <span className="text-xs text-ink-faint ml-auto">{loading ? "Loading…" : `${data?.total ?? 0} setups`}</span>
      </div>
      <ErrorNote error={error} />
      <div className="card overflow-x-auto">
        <table className="w-full">
          <thead><tr>{["Time", "Symbol", "Direction", "5M ADX", "15M ADX", "ATR", "VIX", "Gate 1", "Gate 2", "ATR", "VIX", "Final Result", "Status", "P&L"].map((h, i) => <th key={i} className="th">{h}</th>)}</tr></thead>
          <tbody>
            {(data?.items ?? []).map((s) => {
              const c = s.signal_context ?? {};
              const q = !!s.signal_ts;
              const rej = s.closed_reason ?? "";
              const g2 = q ? "PASS" : s.state === "EXPIRED" ? "FAIL" : rej.includes("15M") ? "FAIL" : rej ? "PASS" : "WAIT";
              const atrS = q ? "PASS" : rej.startsWith("ATR") ? "FAIL" : rej.startsWith("VIX") ? "PASS" : "SKIP";
              const vixS = q ? "PASS" : rej.startsWith("VIX") ? "FAIL" : "SKIP";
              return (
                <tr key={s.id} className="hover:bg-raise cursor-pointer" onClick={() => setOpen(s.id)}>
                  <td className="td num">{dateTimeIST(s.signal_ts ?? s.breakout_ts)}</td>
                  <td className="td">{s.symbol}</td><td className="td"><Dir d={s.direction} /></td>
                  <td className="td num">{n(c.adx5 ?? s.breakout?.adx_at)}</td><td className="td num">{n(c.adx15)}</td>
                  <td className="td text-xs">{c.atr_status ?? "—"}</td><td className="td num">{n(c.vix, 2)}</td>
                  <td className="td"><Badge s="PASS" /></td><td className="td"><Badge s={g2} /></td>
                  <td className="td"><Badge s={atrS} /></td><td className="td"><Badge s={vixS} /></td>
                  <td className="td">{q ? <Badge s="SIGNAL" label={`${s.direction} BUY`} /> : <span className="text-xs text-ink-faint" title={rej}>{s.state === "EXPIRED" ? "EXPIRED" : "REJECTED"}</span>}</td>
                  <td className="td"><Badge s={s.state} /></td>
                  <td className={`td num ${(s.trade?.pnl_points ?? 0) > 0 ? "text-good" : s.trade?.pnl_points ? "text-bad" : "text-ink-faint"}`}>{s.trade?.pnl_points !== null && s.trade?.pnl_points !== undefined ? `${signed(s.trade.pnl_points)} pts` : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!loading && !data?.items.length && <div className="p-6 text-center text-sm text-ink-faint">No setups match these filters</div>}
      </div>
      <SignalDetailDrawer id={open} onClose={() => setOpen(null)} />
    </div>
  );
}

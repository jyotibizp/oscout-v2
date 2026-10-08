import { useState } from "react";
import { api } from "../api/client";
import { BarList, LineChart } from "../components/Charts";
import { SignalDetailDrawer } from "../components/Details";
import { Badge, Dir, Empty, ErrorNote, PageHeader, Stat } from "../components/ui";
import { dateTimeIST, minutes, n, signed } from "../lib/format";
import { useApi } from "../lib/hooks";

export function PerformanceOverview() {
  const sum = useApi(() => api.summary(), [], 60000);
  const eq = useApi(api.equity, [], 60000);
  const an = useApi(api.analytics, [], 60000);
  const t = sum.data?.trading;
  const s = sum.data?.signals;
  const fu = sum.data?.funnel;
  const bucket = (k: string) => (an.data?.[k] ?? []).map((r: any) => ({ label: r.bucket, value: r.net_points ?? 0, sub: `${r.trades} trades · win ${r.win_rate ?? "—"}%` }));
  return (
    <div>
      <PageHeader title="Performance" sub="Measured on the underlying index move (points / R), per closed signal" />
      <ErrorNote error={sum.error} />
      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-3 mb-5">
        <Stat label="Signals" value={s?.total_signals ?? "—"} sub={`${s?.call_signals ?? 0} CALL · ${s?.put_signals ?? 0} PUT`} />
        <Stat label="Win Rate" value={t?.trades ? `${t.win_rate}%` : "—"} sub={`${t?.wins ?? 0}W / ${t?.losses ?? 0}L`} />
        <Stat label="Profit Factor" value={n(t?.profit_factor, 2)} />
        <Stat label="Expectancy" value={t?.trades ? `${signed(t.expectancy_points)} pts` : "—"} sub={t?.expectancy_r !== undefined && t?.expectancy_r !== null ? `${signed(t.expectancy_r, 3)} R` : undefined} />
        <Stat label="Net P&L" value={t?.trades ? `${signed(t.net_points)} pts` : "—"} sub={t?.net_r !== undefined && t?.net_r !== null ? `${signed(t.net_r, 2)} R` : undefined} />
        <Stat label="Max Drawdown" value={t?.trades ? `${n(t.max_drawdown_points)} pts` : "—"} />
        <Stat label="Avg Holding" value={minutes(t?.avg_holding_minutes)} />
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <div className="card p-4 xl:col-span-2">
          <div className="text-xs uppercase tracking-widest text-ink-faint mb-2">Cumulative P&L (index points)</div>
          <LineChart label="Cumulative P&L" points={(eq.data ?? []).map((p) => ({ x: dateTimeIST(p.ts), y: p.cum_points, tip: `${p.symbol} ${signed(p.pnl_points)} pts` }))} />
        </div>
        <div className="card p-4">
          <div className="text-xs uppercase tracking-widest text-ink-faint mb-3">Gate rejection funnel</div>
          {fu && fu.evaluations ? (
            <BarList rows={[
              { label: "Evaluations", value: fu.evaluations },
              { label: "Gate 1 pass", value: fu.gate1_pass, sub: `${fu.rejection_rate.gate1 ?? "—"}% rejected` },
              { label: "Gate 2 pass", value: fu.gate2_pass, sub: `${fu.rejection_rate.gate2 ?? "—"}% rejected` },
              { label: "ATR pass", value: fu.atr_pass, sub: `${fu.rejection_rate.atr ?? "—"}% rejected` },
              { label: "VIX pass", value: fu.vix_pass, sub: `${fu.rejection_rate.vix ?? "—"}% rejected` },
              { label: "Signals", value: fu.signals },
            ]} />
          ) : <p className="text-sm text-ink-faint">No scans yet</p>}
        </div>
        <div className="card p-4">
          <div className="text-xs uppercase tracking-widest text-ink-faint mb-3">Win / loss distribution (R)</div>
          <BarList rows={(an.data?.r_distribution ?? []).map((r: any) => ({ label: `${r.r > 0 ? "+" : ""}${r.r}R`, value: r.count }))} />
        </div>
        <div className="card p-4">
          <div className="text-xs uppercase tracking-widest text-ink-faint mb-3">Signals by hour (IST)</div>
          <BarList rows={(an.data?.signals_by_hour ?? []).map((r: any) => ({ label: r.hour, value: r.count }))} />
        </div>
        <div className="card p-4">
          <div className="text-xs uppercase tracking-widest text-ink-faint mb-3">NIFTY vs SENSEX · CALL vs PUT (net pts)</div>
          <BarList signedColors format={(v) => signed(v)} rows={[...bucket("symbol"), ...bucket("direction")]} />
        </div>
      </div>
    </div>
  );
}

export function Trades() {
  const [sym, setSym] = useState("");
  const { data, error } = useApi(() => api.trades({ symbol: sym || undefined }), [sym], 60000);
  const [open, setOpen] = useState<number | null>(null);
  return (
    <div>
      <PageHeader title="Trades" sub="One trade per generated signal (underlying entry → exit)"
        right={<select className="input" value={sym} onChange={(e) => setSym(e.target.value)}><option value="">All symbols</option><option>NIFTY</option><option>SENSEX</option></select>} />
      <ErrorNote error={error} />
      {data && data.length === 0 ? <Empty>No trades yet</Empty> : (
        <div className="card overflow-x-auto">
          <table className="w-full">
            <thead><tr>{["Entry", "Symbol", "Direction", "Entry px", "Exit", "Exit px", "Exit reason", "P&L pts", "P&L %", "R", "Held", "ADX 5m/15m", "ATR", "VIX", "Status", "Cfg"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
            <tbody>
              {(data ?? []).map((t) => (
                <tr key={t.id} className="hover:bg-raise cursor-pointer" onClick={() => setOpen(t.setup_id)}>
                  <td className="td num">{dateTimeIST(t.entry_ts)}</td><td className="td">{t.symbol}</td><td className="td"><Dir d={t.direction} /></td>
                  <td className="td num">{n(t.entry_price, 2)}</td><td className="td num">{dateTimeIST(t.exit_ts)}</td><td className="td num">{n(t.exit_price, 2)}</td>
                  <td className="td text-xs">{t.exit_reason ?? "—"}</td>
                  <td className={`td num ${(t.pnl_points ?? 0) > 0 ? "text-good" : t.pnl_points ? "text-bad" : ""}`}>{signed(t.pnl_points)}</td>
                  <td className="td num">{signed(t.pnl_pct, 2)}</td><td className="td num">{signed(t.r_multiple, 2)}</td>
                  <td className="td num">{minutes(t.holding_minutes)}</td><td className="td num">{n(t.adx5_entry)} / {n(t.adx15_entry)}</td>
                  <td className="td text-xs">{t.atr_status ?? "—"}</td><td className="td num">{n(t.vix_entry, 2)}</td>
                  <td className="td"><Badge s={t.status} /></td><td className="td text-xs text-ink-faint">v{t.config_version}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <SignalDetailDrawer id={open} onClose={() => setOpen(null)} />
    </div>
  );
}

const DIMS: { key: string; title: string }[] = [
  { key: "symbol", title: "NIFTY vs SENSEX" }, { key: "direction", title: "CALL vs PUT" }, { key: "hour", title: "Time of day (IST)" },
  { key: "weekday", title: "Day of week" }, { key: "breakout_strength", title: "5m ADX breakout strength (pts)" },
  { key: "adx15", title: "15m ADX at entry" }, { key: "atr_status", title: "ATR state" }, { key: "vix_regime", title: "VIX regime" },
];

export function Analytics() {
  const { data, error } = useApi(api.analytics, [], 60000);
  return (
    <div>
      <PageHeader title="Analytics" sub="Closed trades broken down by the strategy's own dimensions" />
      <ErrorNote error={error} />
      <div className="grid gap-4 lg:grid-cols-2">
        {DIMS.map((d) => (
          <div key={d.key} className="card overflow-x-auto">
            <div className="px-4 pt-3 text-xs uppercase tracking-widest text-ink-faint">{d.title}</div>
            <table className="w-full mt-1">
              <thead><tr>{["Bucket", "Trades", "Win %", "Avg gain", "Avg loss", "Expectancy", "Net pts", "PF"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
              <tbody>
                {(data?.[d.key] ?? []).map((r: any) => (
                  <tr key={r.bucket}>
                    <td className="td">{r.bucket}</td><td className="td num">{r.trades}</td><td className="td num">{n(r.win_rate)}</td>
                    <td className="td num">{n(r.avg_gain_points)}</td><td className="td num">{n(r.avg_loss_points)}</td>
                    <td className="td num">{signed(r.expectancy_points)}</td>
                    <td className={`td num ${(r.net_points ?? 0) > 0 ? "text-good" : "text-bad"}`}>{signed(r.net_points)}</td><td className="td num">{n(r.profit_factor, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!(data?.[d.key] ?? []).length && <div className="p-4 text-sm text-ink-faint">No closed trades yet</div>}
          </div>
        ))}
      </div>
    </div>
  );
}

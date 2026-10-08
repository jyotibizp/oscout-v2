import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import { api, Health } from "../api/client";
import { Badge, ErrorNote, PageHeader } from "../components/ui";
import { dateTimeIST, relative } from "../lib/format";
import { useApi } from "../lib/hooks";

export function DataHealth() {
  const { data, error } = useApi(api.health, [], 15000);
  return (
    <div>
      <PageHeader title="Data Health" sub="Signals are never generated from stale or missing data" />
      <ErrorNote error={error} />
      <div className="card overflow-x-auto">
        <table className="w-full">
          <thead><tr>{["Feed", "Status", "Last candle", "Expected", "Stored candles", "Last update", "Last sync", "Connection", "Error"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
          <tbody>
            {(data?.feeds ?? []).map((f) => (
              <tr key={f.feed} className={f.status !== "HEALTHY" ? "bg-bad/5" : ""}>
                <td className="td font-medium">{f.feed}</td>
                <td className="td"><Badge s={f.status} /></td>
                <td className="td num">{dateTimeIST(f.last_candle)}</td>
                <td className="td num text-ink-faint">{dateTimeIST(f.expected_candle)}</td>
                <td className="td num">{f.candles.toLocaleString()}</td>
                <td className="td num">{f.last_update ? relative(f.last_update) : "—"}</td>
                <td className="td num">{f.last_sync ? relative(f.last_sync) : "—"}</td>
                <td className="td text-xs">{data?.connected ? "Connected" : "Disconnected"} · {data?.provider}</td>
                <td className="td text-xs text-bad max-w-xs truncate" title={f.last_error ?? f.reason ?? ""}>{f.last_error ?? f.reason ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-ink-faint">15m candles are built from three stored 5m candles. Exchange holidays produce no candles; stale checks apply during market hours only.</p>
    </div>
  );
}

export function Settings() {
  const { health } = useOutletContext<{ health: Health | null }>();
  const [cat, setCat] = useState("");
  const ev = useApi(() => api.events(cat || undefined), [cat], 30000);
  return (
    <div>
      <PageHeader title="Settings" sub="System status and audit log. Strategy parameters live under Strategy → ADX Configuration." />
      <div className="grid gap-4 md:grid-cols-3 mb-6">
        <div className="card p-4 text-sm space-y-1">
          <div className="text-xs uppercase tracking-widest text-ink-faint mb-2">Broker</div>
          <div>Provider: <b>{health?.provider ?? "—"}</b></div>
          <div>Session: <b className={health?.connected ? "text-good" : "text-bad"}>{health?.connected ? "Connected" : "Disconnected"}</b></div>
          <div className="text-xs text-ink-faint">Kite sessions expire daily; use CONNECT each morning.</div>
        </div>
        <div className="card p-4 text-sm space-y-1">
          <div className="text-xs uppercase tracking-widest text-ink-faint mb-2">Auto scan</div>
          <div>Status: <b>{health?.auto_scan.enabled ? "ON" : "OFF"}</b>{health && !health.auto_scan.runtime_enabled && " (switched off in header)"}</div>
          <div>Next: <span className="num">{dateTimeIST(health?.auto_scan.next_run)}</span></div>
          <div>Last: <span className="num">{dateTimeIST(health?.auto_scan.last_run)}</span> {health?.auto_scan.last_result}</div>
          {health?.auto_scan.last_error && <div className="text-bad text-xs">{health.auto_scan.last_error}</div>}
        </div>
        <div className="card p-4 text-sm space-y-1">
          <div className="text-xs uppercase tracking-widest text-ink-faint mb-2">Market</div>
          <div>Session: <b>{health?.market_open ? "OPEN" : "CLOSED"}</b> (09:15–15:30 IST)</div>
          <div>Server time: <span className="num">{dateTimeIST(health?.now)}</span></div>
        </div>
      </div>
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm font-semibold text-ink-soft">System events</h2>
        <select className="input" value={cat} onChange={(e) => setCat(e.target.value)}>
          <option value="">All</option>{["DATA", "SCAN", "SIGNAL", "CONFIG", "CONNECTION"].map((c) => <option key={c}>{c}</option>)}
        </select>
      </div>
      <ErrorNote error={ev.error} />
      <div className="card overflow-x-auto">
        <table className="w-full">
          <thead><tr>{["Time", "Level", "Category", "Message"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
          <tbody>{(ev.data ?? []).map((e) => (
            <tr key={e.id}>
              <td className="td num">{dateTimeIST(e.ts)}</td>
              <td className={`td text-xs ${e.level === "ERROR" ? "text-bad" : e.level === "WARNING" ? "text-warn" : "text-ink-soft"}`}>{e.level}</td>
              <td className="td text-xs">{e.category}</td><td className="td text-sm whitespace-normal">{e.message}</td>
            </tr>))}</tbody>
        </table>
      </div>
    </div>
  );
}

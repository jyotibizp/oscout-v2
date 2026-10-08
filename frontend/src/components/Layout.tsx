import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { api, Health } from "../api/client";
import { relative, timeIST } from "../lib/format";
import { useApi, useRefresh } from "../lib/hooks";

const NAV: { title: string; items: { to: string; label: string }[] }[] = [
  { title: "", items: [{ to: "/", label: "Dashboard" }] },
  { title: "Signals", items: [{ to: "/signals/live", label: "Live Signals" }, { to: "/signals/history", label: "Signal History" }] },
  { title: "Scans", items: [{ to: "/scans", label: "Scan History" }] },
  { title: "Performance", items: [{ to: "/performance", label: "Overview" }, { to: "/performance/trades", label: "Trades" }, { to: "/performance/analytics", label: "Analytics" }] },
  { title: "Strategy", items: [{ to: "/strategy", label: "ADX Configuration" }] },
  { title: "Market Data", items: [{ to: "/data-health", label: "Data Health" }] },
  { title: "System", items: [{ to: "/settings", label: "Settings" }] },
];

function Sidebar() {
  return (
    <aside className="hidden md:flex w-56 shrink-0 flex-col border-r border-line bg-panel">
      <div className="px-5 h-14 flex items-center border-b border-line">
        <span className="text-accent font-bold tracking-tight">oscout</span>
        <span className="ml-2 text-xs text-ink-faint uppercase tracking-widest">ADX</span>
      </div>
      <nav className="flex-1 overflow-y-auto py-3">
        {NAV.map((g) => (
          <div key={g.title || "root"} className="mb-3">
            {g.title && <div className="px-5 pb-1 text-xs uppercase tracking-widest text-ink-faint">{g.title}</div>}
            {g.items.map((i) => (
              <NavLink key={i.to} to={i.to} end
                className={({ isActive }) =>
                  `block px-5 py-1.5 text-sm border-l-2 ${isActive ? "border-accent text-ink bg-raise" : "border-transparent text-ink-soft hover:text-ink hover:bg-raise/60"}`}>
                {i.label}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
      <div className="px-5 py-3 border-t border-line text-xs text-ink-faint">One strategy · ADX only</div>
    </aside>
  );
}

function Toggle({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button onClick={() => onChange(!on)} className="flex items-center gap-2 text-xs text-ink-soft hover:text-ink" aria-pressed={on}>
      <span className={`relative h-4 w-7 rounded-full transition-colors ${on ? "bg-accent" : "bg-line"}`}>
        <span className={`absolute top-0.5 h-3 w-3 rounded-full bg-white transition-all ${on ? "left-3.5" : "left-0.5"}`} />
      </span>
      {label}
    </button>
  );
}

function Header({ health, reload }: { health: Health | null; reload: () => void }) {
  const { autoRefresh, setAutoRefresh, bump } = useRefresh();
  const [scanning, setScanning] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const scan = async () => {
    setScanning(true);
    setMsg(null);
    try {
      const r = await api.scanNow();
      setMsg(`Scan #${r.run.id} ${r.run.status}`);
      bump();
      reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setScanning(false);
    }
  };
  const connect = async () => {
    try {
      const r = await api.connect();
      if (r.login_url) window.open(r.login_url, "_blank");
      else setMsg(r.message ?? "Connected");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  };
  const feeds = health?.feeds ?? [];
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-panel/95 backdrop-blur">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 px-5 py-2.5 min-h-14">
        <div className="flex items-center gap-2 text-sm">
          <span className={`h-2 w-2 rounded-full ${health?.connected ? "bg-good" : "bg-bad"}`} />
          <span className={health?.connected ? "text-ink" : "text-bad"}>{health ? (health.connected ? "Connected" : "Disconnected") : "…"}</span>
          {health && <span className="text-xs text-ink-faint uppercase">{health.provider}</span>}
        </div>
        <div className="flex flex-wrap gap-1.5">
          {feeds.map((f) => (
            <span key={f.feed} title={f.reason ?? `Last candle ${f.last_candle ?? "—"}`}
              className={`rounded border px-1.5 py-0.5 text-xs font-medium ${f.status === "HEALTHY" ? "border-line text-ink-soft" : "border-bad/50 text-bad"}`}>
              {f.feed} {f.status === "HEALTHY" ? "✓" : "✕"}
            </span>
          ))}
        </div>
        <div className="flex items-center gap-4 text-xs text-ink-soft">
          <span>Market <b className={health?.market_open ? "text-good" : "text-ink-faint"}>{health?.market_open ? "OPEN" : "CLOSED"}</b></span>
          <span>Last scan <b className="num text-ink">{timeIST(health?.last_scan?.started_at)}</b></span>
          <span>Next <b className="num text-ink">{health?.auto_scan.enabled ? timeIST(health.auto_scan.next_run) : "off"}</b>
            {health?.auto_scan.enabled && <span className="text-ink-faint"> ({relative(health.auto_scan.next_run)})</span>}</span>
        </div>
        <div className="ml-auto flex items-center gap-4">
          <Toggle on={!!health?.auto_scan.runtime_enabled} label="Auto Scan"
            onChange={async (v) => { await api.setAutoScan(v); reload(); }} />
          <Toggle on={autoRefresh} label="Auto Refresh" onChange={setAutoRefresh} />
          <button className="btn" onClick={connect}>CONNECT</button>
          <button className="btn-primary px-5" onClick={scan} disabled={scanning}>{scanning ? "SCANNING…" : "SCAN NOW"}</button>
        </div>
      </div>
      {msg && <div className="px-5 pb-2 text-xs text-ink-soft">{msg}</div>}
    </header>
  );
}

export default function Layout() {
  const { data, reload } = useApi(api.health, [], 15000);
  return (
    <div className="flex h-full">
      <Sidebar />
      <div className="flex-1 min-w-0 flex flex-col">
        <Header health={data} reload={reload} />
        <main className="flex-1 overflow-y-auto px-5 py-5 md:px-7">
          <Outlet context={{ health: data }} />
        </main>
      </div>
    </div>
  );
}

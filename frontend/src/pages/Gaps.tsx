import { useState } from "react";
import { api, GapBlock, GapFillResult, ReplayResult } from "../api/client";
import { Badge, Empty, ErrorNote, PageHeader, Stat } from "../components/ui";
import { dateIST, timeIST } from "../lib/format";
import { useApi } from "../lib/hooks";
import { useRole } from "../lib/role";

const MODE: Record<string, string> = { LATEST: "full fill", INTERIOR: "replay" };

/** Scan gaps (#2): completed 5m candles no scan covered, grouped into blocks; I choose which to fill. */
export default function Gaps() {
  const [range, setRange] = useState<{ from?: string; to?: string }>({});
  const gaps = useApi(() => api.gaps(range.from, range.to), [range.from, range.to]);
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<GapFillResult[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [replayed, setReplayed] = useState<ReplayResult | null>(null);
  const admin = useRole() === "admin";
  const d = gaps.data;
  const blocks = d?.blocks ?? [];
  const chosen = blocks.filter((b) => sel.has(b.id));

  const toggle = (id: string) => setSel((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const fill = async () => {
    const lines = chosen.map((b) => `${dateIST(b.start)} ${timeIST(b.start)}–${timeIST(b.end)}: ${b.candles} candles, ${MODE[b.type]}`);
    if (!window.confirm(`Fill ${chosen.length} block(s)?\n\n${lines.join("\n")}\n\nLatest = scanned in order with the signal lifecycle (signals found are marked late, no chime).\nInterior = replayed: qualified setups become LATE trades run to their own exit; existing signals and trades are not changed.`)) return;
    setBusy(true); setError(null); setResults(null);
    try {
      const r = await api.fillGaps(chosen.map((b) => b.id));
      setResults(r.results);
      setSel(new Set());
      gaps.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const replay = async () => {
    const n = d?.replay_pending ?? 0;
    if (!window.confirm(`Replay ${n} missed breakout(s) from blocks filled before replay existed?\n\nEach becomes a LATE trade run to its own exit (or rejected if a trade on that index was open). Only adds rows; old scan rows stay as they are.`)) return;
    setBusy(true); setError(null); setReplayed(null);
    try {
      setReplayed(await api.replayFilled());
      gaps.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-5xl">
      <PageHeader title="Scan gaps" sub="Completed 5m candles that no auto scan covered (app down, Mac asleep, feed error, token expired). Nothing fills by itself." />
      <div className="mb-4 flex flex-wrap items-center gap-2 text-sm text-ink-soft">
        <span>Range</span>
        <input type="date" aria-label="From" className="input" value={range.from ?? d?.from ?? ""} onChange={(e) => setRange({ ...range, from: e.target.value })} />
        <span>to</span>
        <input type="date" aria-label="To" className="input" value={range.to ?? d?.to ?? ""} onChange={(e) => setRange({ ...range, to: e.target.value })} />
        {(range.from || range.to) && <button className="btn !px-3 !py-1" onClick={() => setRange({})}>Last 5 days</button>}
      </div>
      <ErrorNote error={gaps.error ?? error} />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
        <Stat label="Missing candles" value={d?.total_missing ?? "—"} />
        <Stat label="Blocks" value={blocks.length} />
        <Stat label="Days scanned" value={d?.days.length ?? "—"} sub={d?.days.filter((x) => x.missing).map((x) => `${dateIST(x.date)}: ${x.missing}`).join(" · ") || "no gaps"} />
        <Stat label="Days without candles" value={d?.no_data_days.length ?? "—"} sub="holidays, or never synced" />
      </div>

      {admin && !!d?.replay_pending && (
        <div className="card p-4 mb-5 flex flex-wrap items-center justify-between gap-3 text-sm">
          <p className="text-ink-soft">{d.replay_pending} missed breakout(s) in blocks filled record-only (before replay). Replay them into LATE trades for Performance.</p>
          <button className="btn-primary" disabled={busy} onClick={replay}>{busy ? "Replaying…" : `Replay filled blocks (${d.replay_pending})`}</button>
        </div>
      )}
      {replayed && (
        <p className="card p-4 mb-5 text-sm" aria-label="Replay results">Replayed {replayed.breakouts} breakout(s): {replayed.signals} LATE trade(s), {replayed.blocked} rejected (trade already open), {replayed.skipped} no longer qualify.</p>
      )}

      {results && (
        <div className="card p-4 mb-5 text-sm space-y-1" aria-label="Fill results">
          {results.map((r) => (
            <p key={r.id}><Badge s={r.status === "FILLED" ? "PASS" : "WAIT"} label={r.status.replace("_", " ")} />{" "}
              {dateIST(r.id)} {timeIST(r.id)}: {r.status === "FILLED" ? `${r.scans} scans written (${r.mode === "FULL" ? `full fill, ${r.signals} signal(s)` : `replay, ${r.signals} LATE trade(s), ${r.blocked ?? 0} rejected (trade already open)`})` : r.message}</p>
          ))}
        </div>
      )}

      {!blocks.length ? <Empty>{gaps.loading ? "Checking…" : "No gaps in this range."}</Empty> : (
        <div className="card overflow-x-auto">
          <table className="w-full">
            <thead><tr><th className="th w-8" /><th className="th">Date</th><th className="th">From – to (IST)</th><th className="th">Candles</th><th className="th">Type</th><th className="th">Data</th></tr></thead>
            <tbody>
              {blocks.map((b: GapBlock) => (
                <tr key={b.id} className={b.selectable ? "" : "opacity-60"}>
                  <td className="td"><input type="checkbox" aria-label={`Select ${b.id}`} disabled={!b.selectable || !admin || busy} checked={sel.has(b.id)} onChange={() => toggle(b.id)} /></td>
                  <td className="td">{dateIST(b.start)}</td>
                  <td className="td num">{timeIST(b.start)} – {timeIST(b.end)}</td>
                  <td className="td num">{b.candles}</td>
                  <td className="td"><Badge s={b.type === "LATEST" ? "ACTIVE" : "WATCHING"} label={`${b.type === "LATEST" ? "Latest" : "Interior"} · ${MODE[b.type]}`} /></td>
                  <td className="td">{b.data === "FULL" ? <Badge s="PASS" label="present" /> : <Badge s="MISSING" label={b.data === "NONE" ? "no data" : "partial"} />}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex flex-wrap items-center justify-between gap-3 p-4">
            <p className="text-xs text-ink-faint">Latest: no scans after it, so it is scanned in order with the full signal lifecycle. Interior: later scans exist, so it is replayed: qualified setups become LATE trades run to their own exit, nothing existing is changed.</p>
            {admin && <button className="btn-primary" disabled={!chosen.length || busy} onClick={fill}>{busy ? "Filling…" : `Fill selected (${chosen.length})`}</button>}
          </div>
        </div>
      )}
    </div>
  );
}

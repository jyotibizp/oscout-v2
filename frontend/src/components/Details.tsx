import { api, ScanResult, Setup } from "../api/client";
import { dateTimeIST, n, signed } from "../lib/format";
import { useApi } from "../lib/hooks";
import { Pipeline } from "./Pipeline";
import { Badge, Dir, Drawer } from "./ui";

function Metrics({ m }: { m?: Record<string, any> | null }) {
  if (!m) return null;
  const entries = Object.entries(m).filter(([, v]) => v !== null && typeof v !== "object");
  return (
    <dl className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-1 text-xs">
      {entries.map(([k, v]) => (
        <div key={k} className="flex justify-between gap-2 border-b border-line/50 py-0.5">
          <dt className="text-ink-faint">{k.replace(/_/g, " ")}</dt>
          <dd className="num text-ink">{typeof v === "number" ? (Number.isInteger(v) ? String(v) : n(v, 2)) : String(v)}</dd>
        </div>
      ))}
    </dl>
  );
}

export function ScanDetailDrawer({ id, onClose }: { id: number | null; onClose: () => void }) {
  const { data: r } = useApi(() => (id ? api.scanResult(id) : Promise.resolve(null as unknown as ScanResult)), [id]);
  return (
    <Drawer open={id !== null} onClose={onClose} title={r ? `${r.symbol} · scan #${r.scan_run_id} · ${dateTimeIST(r.candle_ts)}` : "Scan"}>
      {r && (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <Badge s={r.state} /> <Dir d={r.direction} /> <span className="text-ink-faint">config v{r.config_version}</span>
          </div>
          <p className="text-sm text-ink-soft">{r.details?.reason}</p>
          {r.details?.note && <p className="text-sm text-warn">{r.details.note}</p>}
          <Pipeline r={r} />
          {(["gate1", "gate2", "atr", "vix"] as const).map((k) => (
            <div key={k}>
              <div className="text-xs uppercase tracking-wider text-ink-faint mb-1">{k} metrics</div>
              <Metrics m={r.details?.[k]?.metrics} />
            </div>
          ))}
          <div>
            <div className="text-xs uppercase tracking-wider text-ink-faint mb-1">market snapshot</div>
            <Metrics m={r.details?.snapshot} />
          </div>
        </div>
      )}
    </Drawer>
  );
}

export function SignalDetailDrawer({ id, onClose }: { id: number | null; onClose: () => void }) {
  const { data: s } = useApi(() => (id ? api.signal(id) : Promise.resolve(null as unknown as Setup)), [id]);
  return (
    <Drawer open={id !== null} onClose={onClose} title={s ? `${s.symbol} ${s.direction} · setup #${s.id}` : "Signal"}>
      {s && (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <Badge s={s.state} /> <Dir d={s.direction} /> <span className="text-ink-faint">config v{s.config_version}</span>
          </div>
          {s.closed_reason && <p className="text-sm text-ink-soft">{s.closed_reason}</p>}
          <div>
            <div className="text-xs uppercase tracking-wider text-ink-faint mb-2">Lifecycle</div>
            <ol className="relative border-l border-line ml-2 space-y-3">
              {(s.events ?? []).map((e) => (
                <li key={e.id} className="ml-4">
                  <span className="absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full border border-line bg-raise" />
                  <div className="flex items-center gap-2 text-xs">
                    <span className="num text-ink-faint">{dateTimeIST(e.candle_ts)}</span>
                    <Badge s={e.event} label={e.event.replace(/_/g, " ")} />
                    {e.price !== null && <span className="num text-ink-soft">@ {n(e.price, 2)}</span>}
                  </div>
                  {e.note && <div className="text-xs text-ink-soft mt-0.5">{e.note}</div>}
                </li>
              ))}
            </ol>
          </div>
          {s.trade && (
            <div>
              <div className="text-xs uppercase tracking-wider text-ink-faint mb-1">Trade (underlying)</div>
              <Metrics m={{ entry: s.trade.entry_price, exit: s.trade.exit_price, exit_reason: s.trade.exit_reason,
                pnl_points: s.trade.pnl_points, r_multiple: s.trade.r_multiple, holding_minutes: s.trade.holding_minutes }} />
              {s.trade.pnl_points !== null && (
                <p className={`mt-2 text-sm num ${(s.trade.pnl_points ?? 0) > 0 ? "text-good" : "text-bad"}`}>{signed(s.trade.pnl_points)} pts · {signed(s.trade.r_multiple, 2)}R</p>
              )}
            </div>
          )}
          <div>
            <div className="text-xs uppercase tracking-wider text-ink-faint mb-1">Breakout</div>
            <Metrics m={s.breakout} />
          </div>
        </div>
      )}
    </Drawer>
  );
}

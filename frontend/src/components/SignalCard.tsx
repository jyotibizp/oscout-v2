import { Setup } from "../api/client";
import { dateTimeIST, n, signed, timeIST } from "../lib/format";
import { Badge, Dir } from "./ui";

/** Prominent card for a generated / active signal, with the reason it exists. */
export function SignalCard({ s, onOpen }: { s: Setup; onOpen?: () => void }) {
  const c = s.signal_context ?? {};
  const bo = s.breakout ?? {};
  const g2 = c.gate2 ?? {};
  const atr = c.atr ?? {};
  const vix = c.vix_filter ?? {};
  const t = s.trade;
  return (
    <div className={`card p-4 border-l-4 ${s.direction === "CALL" ? "border-l-good" : "border-l-bad"}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-widest text-ink-faint">{s.symbol}</div>
          <div className={`text-2xl font-bold ${s.direction === "CALL" ? "text-good" : "text-bad"}`}>{s.direction} BUY</div>
          <div className="text-xs text-ink-soft mt-0.5">ADX BREAKOUT CONFIRMED · v{s.config_version}</div>
        </div>
        <Badge s={s.state} />
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
        <dt className="text-ink-faint">5M ADX</dt><dd className="num text-right">{n(bo.adx_at)} <span className="text-good">↑</span></dd>
        <dt className="text-ink-faint">15M ADX</dt><dd className="num text-right">{n(g2.adx)} <span className={(g2.slope ?? 0) > 0 ? "text-good" : "text-bad"}>{(g2.slope ?? 0) > 0 ? "↑" : "↓"}</span></dd>
        <dt className="text-ink-faint">ATR</dt><dd className="text-right">{atr.atr_status ?? "—"} <span className="num text-ink-faint">({n(atr.ratio, 2)}×)</span></dd>
        <dt className="text-ink-faint">INDIA VIX</dt><dd className="num text-right">{n(vix.vix, 2)}</dd>
        <dt className="text-ink-faint">DIRECTION</dt><dd className="text-right"><Dir d={s.direction} /></dd>
        <dt className="text-ink-faint">SIGNAL TIME</dt><dd className="num text-right">{timeIST(s.signal_ts)}</dd>
        <dt className="text-ink-faint">ENTRY (index)</dt><dd className="num text-right">{n(s.entry_price, 2)}</dd>
        <dt className="text-ink-faint">STOP / TARGET</dt><dd className="num text-right">{n(s.stop_price, 1)} / {n(s.target_price, 1)}</dd>
        {t && t.status === "CLOSED" && (<>
          <dt className="text-ink-faint">EXIT</dt><dd className="num text-right">{n(t.exit_price, 2)} · {t.exit_reason}</dd>
          <dt className="text-ink-faint">RESULT</dt><dd className={`num text-right ${(t.pnl_points ?? 0) > 0 ? "text-good" : "text-bad"}`}>{signed(t.pnl_points)} pts · {signed(t.r_multiple, 2)}R</dd>
        </>)}
      </dl>
      <div className="mt-3 flex flex-wrap gap-1.5">
        <Badge s="PASS" label="Gate 1" /><Badge s="PASS" label="Gate 2" /><Badge s="PASS" label="ATR Filter" /><Badge s="PASS" label="VIX Filter" />
      </div>
      {c.reason && <p className="mt-3 text-xs text-ink-soft leading-relaxed"><span className="text-ink-faint">Why: </span>{c.reason}</p>}
      {onOpen && <button className="btn mt-3" onClick={onOpen}>Lifecycle · {dateTimeIST(s.breakout_ts)}</button>}
    </div>
  );
}

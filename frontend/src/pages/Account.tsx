import { ReactNode, useRef, useState } from "react";
import { AcctAgg, AcctBucket, AcctFilter, AcctStats, AcctTrade, api } from "../api/client";
import { BarList, LineChart } from "../components/Charts";
import { Badge, Empty, ErrorNote, PageHeader, Stat } from "../components/ui";
import { dateIST, dateTimeIST, minutes, n } from "../lib/format";
import { useApi } from "../lib/hooks";
import { useRole } from "../lib/role";

/** #24 Account trade log: my own Kite fills, and what overtrading costs me. Admin only. */

export const inr = (v?: number | null, sign = true) =>
  v === null || v === undefined ? "—" : `${sign ? (v > 0 ? "+" : v < 0 ? "−" : "") : v < 0 ? "−" : ""}₹${Math.abs(Math.round(v)).toLocaleString("en-IN")}`;
const tone = (v?: number | null) => (v === null || v === undefined ? "" : v > 0 ? "text-good" : v < 0 ? "text-bad" : "");
const pct = (v?: number | null) => (v === null || v === undefined ? "—" : `${v}%`);
const DOW = ["Mon", "Tue", "Wed", "Thu", "Fri"];
const FLAG_LABEL: Record<string, string> = {
  OFF_SIGNAL: "Off-signal", AVG_DOWN: "Averaged down", FLIP: "CE↔PE flip <10m", QUICK_REENTRY: "Re-entry <5m after loss", SCALP: "Held <2m",
};

function Wow({ title, big, line, tone: t = "" }: { title: string; big: ReactNode; line: ReactNode; tone?: string }) {
  return (
    <div className="card px-4 py-3">
      <div className="text-xs uppercase tracking-wider text-ink-faint">{title}</div>
      <div className={`num text-xl font-semibold mt-1 ${t}`}>{big}</div>
      <div className="text-xs text-ink-soft mt-1 leading-snug">{line}</div>
    </div>
  );
}

function wowCards(s: AcctStats): ReactNode[] {
  const t = s.totals;
  const best = [...s.stop_after].sort((a, b) => b.vs_actual - a.vs_actual)[0];
  const fast = s.gap_prev.filter((b) => b.bucket === "<1m" || b.bucket === "1-5m");
  const fastAgg = fast.reduce((a, b) => ({ trades: a.trades + b.trades, net: a.net + b.net, wins: a.wins + b.wins }), { trades: 0, net: 0, wins: 0 });
  const slow = s.gap_prev.find((b) => b.bucket === "15m+");
  const scalp = s.scalp.find((b) => b.bucket.startsWith("<"));
  const hold = s.scalp.find((b) => !b.bucket.startsWith("<"));
  const hours = new Map<number, number>();
  s.heatmap.forEach((h) => hours.set(h.hour, (hours.get(h.hour) ?? 0) + h.net));
  const hs = [...hours.entries()].sort((a, b) => b[1] - a[1]);
  const worst = hs[hs.length - 1];
  const o = s.orders;
  return [
    <Wow key="stop" title="If you'd stopped after N trades a day" tone={tone(best?.vs_actual)}
      big={best ? `${inr(best.vs_actual)}` : "—"}
      line={best ? <>Stopping after <b>{best.n}</b> trade{best.n > 1 ? "s" : ""} vs your actual {inr(t.net)}. {s.stop_after.map((x) => `${x.n}: ${inr(x.net)}`).join(" · ")}</> : "No closed trades yet"} />,
    <Wow key="gap" title="Clicking again within 5 min" tone={tone(fastAgg.net)}
      big={fastAgg.trades ? inr(fastAgg.net) : "—"}
      line={fastAgg.trades ? <>{fastAgg.trades} trades entered &lt;5 min after the previous one, win {Math.round((100 * fastAgg.wins) / fastAgg.trades)}%. Waited 15m+: {slow ? `${inr(slow.net)}, win ${pct(slow.win_rate)}` : "none"}.</> : "No back-to-back entries"} />,
    <Wow key="gave" title="Gave it back" tone={s.gave_back.total ? "text-bad" : ""}
      big={inr(-s.gave_back.total)}
      line={<>On {s.gave_back.days} of {s.gave_back.of_days} days you were up and closed lower. {s.gave_back.green_to_red} went green → red.</>} />,
    <Wow key="cut" title="Zerodha + taxes' cut" tone="text-bad"
      big={inr(-s.charges.charges)}
      line={<>{s.charges.pct_of_gross === null ? "On a gross loss. " : s.charges.pct_of_gross > 100 ? `${n(s.charges.pct_of_gross / 100, 1)}× your gross profit. ` : `${s.charges.pct_of_gross}% of your gross profit. `}STT {inr(s.charges.stt, false)}, brokerage {inr(s.charges.brokerage, false)}, gross {inr(s.charges.gross)}. {inr(s.charges.per_trade, false)} per round trip.</>} />,
    <Wow key="sys" title="Your extra (off-signal) trades" tone={tone(s.system.off_signal.net)}
      big={inr(s.system.off_signal.net)}
      line={<>{s.system.off_signal.trades} off-signal trades, win {pct(s.system.off_signal.win_rate)}. On-signal: {s.system.on_signal.trades} trades {inr(s.system.on_signal.net)}. oscout gave {s.system.signals} signals ({s.system.net_r > 0 ? "+" : ""}{s.system.net_r}R), you took {s.system.taken}.</>} />,
    <Wow key="tilt" title="Tilt clock" tone={(s.tilt.after_loss_min ?? 99) < (s.tilt.after_win_min ?? 0) ? "text-bad" : ""}
      big={s.tilt.after_loss_min !== null ? minutes(s.tilt.after_loss_min) : "—"}
      line={<>Median wait before the next entry after a loss. After a win: {minutes(s.tilt.after_win_min)} ({s.tilt.after_win_n} cases vs {s.tilt.after_loss_n} after losses).</>} />,
    <Wow key="two" title="After 2 losses in a row" tone={tone((s.after_two_losses.next.win_rate ?? 0) - (s.after_two_losses.overall_win_rate ?? 0))}
      big={s.after_two_losses.next.trades ? `win ${pct(s.after_two_losses.next.win_rate)}` : "—"}
      line={<>Next trade, {s.after_two_losses.next.trades} times: {inr(s.after_two_losses.next.net)}. Your overall win rate is {pct(s.after_two_losses.overall_win_rate)}.</>} />,
    <Wow key="scalp" title="Scalp tax (held under 2 min)" tone={tone(scalp?.net)}
      big={scalp ? inr(scalp.net) : "—"}
      line={<>{scalp?.trades ?? 0} quick trades, win {pct(scalp?.win_rate)}. Held 2m+: {hold ? `${inr(hold.net)}, win ${pct(hold.win_rate)}` : "none"}.</>} />,
    <Wow key="churn" title="Order churn" big={o.placed ? `${n(o.per_round_trip, 1)} orders / trade` : "—"}
      line={o.placed ? <>{o.placed} orders since {dateIST(o.since)}: {o.cancelled} cancelled, {o.rejected} rejected{o.modified !== null ? `, ${o.modified} modified` : ""}. Fastest gap {o.shortest_gap_sec ?? "—"}s.</> : "Starts with the first daily Kite pull (Kite gives today's orders only)."} />,
    <Wow key="hour" title="Best hour / worst hour" tone={tone(worst?.[1])}
      big={worst ? `${worst[0]}:00 ${inr(worst[1])}` : "—"}
      line={hs.length ? <>Best: {hs[0][0]}:00 {inr(hs[0][1])}. Entries by hour, IST.</> : "No closed trades yet"} />,
  ];
}

function BucketTable({ title, rows, extra }: { title: string; rows: AcctBucket[]; extra?: AcctBucket }) {
  const all = extra ? [...rows, extra] : rows;
  return (
    <div className="card overflow-x-auto">
      <div className="px-4 pt-3 text-xs uppercase tracking-widest text-ink-faint">{title}</div>
      {all.length ? (
        <table className="w-full mt-1">
          <thead><tr>{["", "Trades", "Win %", "Avg", "Net"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
          <tbody>{all.map((r) => (
            <tr key={r.bucket}><td className="td">{r.bucket}</td><td className="td num">{r.trades}</td><td className="td num">{n(r.win_rate)}</td>
              <td className={`td num ${tone(r.avg)}`}>{inr(r.avg)}</td><td className={`td num ${tone(r.net)}`}>{inr(r.net)}</td></tr>
          ))}</tbody>
        </table>
      ) : <div className="p-4 text-sm text-ink-faint">No data yet</div>}
    </div>
  );
}

function Heatmap({ cells }: { cells: AcctStats["heatmap"] }) {
  const hours = [9, 10, 11, 12, 13, 14, 15];
  const max = Math.max(1, ...cells.map((c) => Math.abs(c.net)));
  const at = (w: number, h: number) => cells.find((c) => c.weekday === w && c.hour === h);
  return (
    <div className="card p-4 overflow-x-auto">
      <div className="text-xs uppercase tracking-widest text-ink-faint mb-3">P&L by entry time (IST)</div>
      <table className="text-xs">
        <thead><tr><th />{hours.map((h) => <th key={h} className="px-1 pb-1 font-normal text-ink-faint">{h}:00</th>)}</tr></thead>
        <tbody>{DOW.map((d, w) => (
          <tr key={d}><td className="pr-2 text-ink-faint">{d}</td>{hours.map((h) => {
            const c = at(w, h);
            const a = c ? 0.15 + (0.85 * Math.abs(c.net)) / max : 0;
            return (
              <td key={h} className="p-0.5">
                <div title={c ? `${d} ${h}:00 · ${c.trades} trades · ${inr(c.net)}` : ""}
                  className="h-8 w-14 rounded grid place-items-center num"
                  style={{ background: c ? (c.net >= 0 ? `rgba(74,222,128,${a})` : `rgba(248,113,113,${a})`) : "transparent", border: c ? "none" : "1px solid #3a3a3a" }}>
                  {c ? c.trades : ""}
                </div>
              </td>
            );
          })}</tr>
        ))}</tbody>
      </table>
      <div className="mt-2 text-xs text-ink-faint">Cell = trades entered; colour = net (green profit, red loss).</div>
    </div>
  );
}

function DayStrip({ days }: { days: AcctStats["days"] }) {
  if (!days.length) return <div className="text-sm text-ink-faint">No days yet</div>;
  const max = Math.max(1, ...days.map((d) => d.trades));
  return (
    <div>
      <div className="flex items-end gap-px h-28 overflow-x-auto">
        {days.map((d) => (
          <div key={d.day} className="flex-1 min-w-[6px] max-w-[18px] rounded-t-sm"
            title={`${d.day} · ${d.trades} trades · ${inr(d.net)} · busiest 15m: ${d.burst15}${d.orders ? ` · ${d.orders.placed} orders, ${d.orders.cancelled} cancelled` : ""}`}
            style={{ height: `${(100 * d.trades) / max}%`, background: d.net >= 0 ? "#4ade80" : "#f87171" }} />
        ))}
      </div>
      <div className="mt-1 flex justify-between text-xs text-ink-faint"><span>{days[0].day}</span><span>bar = trades that day, colour = net</span><span>{days[days.length - 1].day}</span></div>
    </div>
  );
}

function TradeList({ rows }: { rows: AcctTrade[] }) {
  if (!rows.length) return <Empty>No trades yet. Import your Kite Console tradebook CSV, or let the daily pull run.</Empty>;
  return (
    <div className="card overflow-x-auto">
      <table className="w-full">
        <thead><tr>{["Entry", "#", "Contract", "Side", "Qty", "Entry px", "Exit px", "Held", "Gross", "Charges", "Net", "Signal", "Flags"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => (
          <tr key={`${r.tradingsymbol}-${r.entry_ts}-${i}`} className="hover:bg-raise">
            <td className="td num">{dateTimeIST(r.entry_ts)}</td><td className="td num text-ink-faint">{r.day_seq}</td>
            <td className="td">{r.tradingsymbol}</td>
            <td className={`td text-xs font-semibold ${r.view === "CALL" ? "text-good" : "text-bad"}`}>{r.side === "LONG" ? "BUY" : "SELL"} {r.instrument}</td>
            <td className="td num">{r.qty}{r.adds ? <span className="text-ink-faint"> (+{r.adds})</span> : null}</td>
            <td className="td num">{n(r.avg_entry, 2)}</td><td className="td num">{n(r.avg_exit, 2)}</td>
            <td className="td num">{r.status === "OPEN" ? <Badge s="OPEN" /> : minutes(r.hold_min)}</td>
            <td className={`td num ${tone(r.gross)}`}>{inr(r.gross)}</td><td className="td num text-ink-faint">{inr(r.charges, false)}</td>
            <td className={`td num font-semibold ${tone(r.net)}`}>{inr(r.net)}</td>
            <td className="td text-xs">{r.on_signal ? <span className="text-good">#{r.signal_id} · +{n(r.signal_delay_min, 0)}m</span> : <span className="text-ink-faint">—</span>}</td>
            <td className="td text-xs">{r.flags.filter((f) => f !== "OFF_SIGNAL").map((f) => (
              <span key={f} className="mr-1 rounded border border-warn/40 bg-warn/10 px-1 text-warn">{FLAG_LABEL[f] ?? f}</span>))}</td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

const Section = ({ title, children }: { title: string; children: ReactNode }) => (
  <section className="mt-7"><h2 className="text-sm uppercase tracking-widest text-ink-soft mb-3">{title}</h2>{children}</section>
);

export default function Account() {
  const admin = useRole() === "admin";
  const [f, setF] = useState<AcctFilter>({});
  const [msg, setMsg] = useState<string | null>(null);
  const file = useRef<HTMLInputElement>(null);
  const k = [f.symbol, f.date_from, f.date_to];
  const st = useApi(() => api.acctStatus(), [], 60000);
  const s = useApi(() => api.acctStats(f), k, 60000);
  const tr = useApi(() => api.acctTrades(f), k, 60000);
  const reload = () => { st.reload(); s.reload(); tr.reload(); };

  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const fl = e.target.files?.[0];
    e.target.value = "";
    if (!fl) return;
    setMsg("Importing…");
    try {
      const r = await api.acctImport(await fl.text());
      setMsg(`Imported ${r.added} fills, ${r.skipped} skipped (duplicates / equity)${r.error_count ? `, ${r.error_count} bad rows: ${r.errors[0]}` : ""}`);
      reload();
    } catch (err) { setMsg(err instanceof Error ? err.message : String(err)); }
  };
  const sync = async () => {
    setMsg("Pulling from Kite…");
    try {
      const r = await api.acctSync();
      setMsg(r.skipped ?? `Kite: ${r.trades_added} new fills, ${r.orders} orders today`);
      reload();
    } catch (err) { setMsg(err instanceof Error ? err.message : String(err)); }
  };

  if (!admin) return <Empty>My Trades is private to the Mac.</Empty>;
  const d = s.data;
  const status = st.data;
  return (
    <div>
      <PageHeader title="My Trades" sub="My Kite fills as round trips, after estimated charges. The numbers are the discipline."
        right={<div className="flex flex-wrap items-center gap-2 text-sm text-ink-soft">
          <select aria-label="Index" className="input" value={f.symbol ?? ""} onChange={(e) => setF({ ...f, symbol: e.target.value || undefined })}>
            <option value="">All</option>{["NIFTY", "SENSEX", "BANKNIFTY", "OTHER"].map((x) => <option key={x}>{x}</option>)}
          </select>
          <input type="date" aria-label="From" className="input" value={f.date_from ?? ""} onChange={(e) => setF({ ...f, date_from: e.target.value || undefined })} />
          <span>to</span>
          <input type="date" aria-label="To" className="input" value={f.date_to ?? ""} onChange={(e) => setF({ ...f, date_to: e.target.value || undefined })} />
          {(f.date_from || f.date_to) && <button className="btn !px-3 !py-1" onClick={() => setF({ symbol: f.symbol })}>All time</button>}
          <input ref={file} type="file" accept=".csv,text/csv" className="hidden" aria-label="Tradebook CSV" onChange={onFile} />
          <button className="btn" onClick={() => file.current?.click()}>Import tradebook CSV</button>
          <button className="btn" onClick={sync}>Pull today from Kite</button>
        </div>} />
      <div className="mb-4 text-xs text-ink-faint">
        {status ? <>{status.fills} fills{status.first_fill ? ` from ${dateIST(status.first_fill)} to ${dateIST(status.last_fill)}` : ""} · {status.orders} orders
          · last Kite pull (daily 15:45 IST) {status.last_sync.at ? dateTimeIST(status.last_sync.at) : "not yet"}{status.last_sync.error ? ` (error: ${status.last_sync.error})` : ""}</> : "…"}
        {msg && <span className="ml-3 text-ink-soft">{msg}</span>}
      </div>
      <ErrorNote error={s.error} />
      {d && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-6 gap-3">
            <Stat label="Round trips" value={d.totals.trades} sub={`${d.totals.days} days${d.totals.open ? ` · ${d.totals.open} open` : ""}`} />
            <Stat label="Net P&L" value={<span className={tone(d.totals.net)}>{inr(d.totals.net)}</span>} sub={`gross ${inr(d.charges.gross)}`} />
            <Stat label="Win rate" value={pct(d.totals.win_rate)} sub={`${d.totals.wins}W / ${d.totals.trades - d.totals.wins}L`} />
            <Stat label="Avg win / loss" value={`${inr(d.totals.avg_win, false)} / ${inr(d.totals.avg_loss, false)}`} sub={`PF ${n(d.totals.profit_factor, 2)}`} />
            <Stat label="Green days" value={`${d.totals.green_days} / ${d.totals.days}`} />
            <Stat label="Trades / day" value={n(d.frequency.trades_per_day)} sub={`max ${d.frequency.max_per_day ?? "—"}`} />
          </div>

          <Section title="The hard truths">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">{wowCards(d)}</div>
          </Section>

          <Section title="Equity: you vs on-signal trades only">
            <div className="card p-4">
              <LineChart label="Cumulative net ₹" format={(v) => inr(v)} y2Label="On-signal only" y2={d.equity.map((p) => p.cum_on_signal)}
                points={d.equity.map((p) => ({ x: dateTimeIST(p.ts), y: p.cum }))} />
              <div className="mt-1 text-xs text-ink-faint">Solid = all your trades · dashed = only trades taken on an oscout signal</div>
            </div>
          </Section>

          <Section title="What overtrading costs">
            <div className="grid gap-4 lg:grid-cols-2">
              <BucketTable title="By trade number in the day" rows={d.by_trade_number} />
              <div className="card overflow-x-auto">
                <div className="px-4 pt-3 text-xs uppercase tracking-widest text-ink-faint">By trades per day</div>
                <table className="w-full mt-1">
                  <thead><tr>{["Trades/day", "Days", "Green %", "Avg day", "Net"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
                  <tbody>{d.by_day_count.map((r) => (
                    <tr key={r.bucket}><td className="td">{r.bucket}</td><td className="td num">{r.days}</td><td className="td num">{n(r.green_pct)}</td>
                      <td className={`td num ${tone(r.avg_day)}`}>{inr(r.avg_day)}</td><td className={`td num ${tone(r.net)}`}>{inr(r.net)}</td></tr>))}</tbody>
                </table>
              </div>
              <BucketTable title="Time since your previous entry" rows={d.gap_prev} />
              <BucketTable title="Re-entry after a loss (time since exit)" rows={d.reentry_after_loss}
                extra={d.reentry_after_win.trades ? { ...d.reentry_after_win, bucket: "after a win" } : undefined} />
              <BucketTable title="Flags" rows={Object.entries(d.flags).filter(([, a]) => a.trades).map(([k2, a]) => ({ ...(a as AcctAgg), bucket: FLAG_LABEL[k2] ?? k2 }))} />
              <BucketTable title="On-signal vs off-signal" rows={[{ ...d.system.on_signal, bucket: "On-signal" }, { ...d.system.off_signal, bucket: "Off-signal" }].filter((r) => r.trades)} />
            </div>
          </Section>

          <Section title="Frequency">
            <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 mb-4">
              <Stat label="Trades / day" value={n(d.frequency.trades_per_day)} sub={`max ${d.frequency.max_per_day ?? "—"}`} />
              <Stat label="Busiest 15 min" value={d.frequency.max_burst15 ?? "—"} sub="entries in one 15-min window" />
              <Stat label="Orders / day" value={n(d.orders.per_day)} sub={d.orders.since ? `since ${dateIST(d.orders.since)}` : "from first Kite pull"} />
              <Stat label="Cancelled" value={d.orders.placed ? `${d.orders.cancelled}` : "—"} sub={d.orders.placed ? `${Math.round((100 * d.orders.cancelled) / d.orders.placed)}% of orders` : undefined} />
              <Stat label="Modified" value={d.orders.modified ?? "—"} sub={`rejected ${d.orders.rejected}`} />
              <Stat label="Order gap" value={d.orders.shortest_gap_sec !== null ? `${d.orders.shortest_gap_sec}s` : "—"} sub={d.orders.median_gap_sec !== null ? `median ${d.orders.median_gap_sec}s` : undefined} />
            </div>
            <div className="grid gap-4 xl:grid-cols-3">
              <div className="card p-4 xl:col-span-2">
                <div className="text-xs uppercase tracking-widest text-ink-faint mb-3">Every day</div>
                <DayStrip days={d.days} />
              </div>
              <div className="card p-4">
                <div className="text-xs uppercase tracking-widest text-ink-faint mb-3">Trades / orders by hour</div>
                <BarList rows={d.frequency.by_hour.map((h) => {
                  const o = d.orders.by_hour.find((x) => x.hour === h.hour);
                  return { label: `${h.hour}:00`, value: h.trades, sub: o ? `${o.orders} orders` : undefined };
                })} />
              </div>
            </div>
            <div className="mt-4"><Heatmap cells={d.heatmap} /></div>
          </Section>
        </>
      )}

      <Section title="Trade log">
        <ErrorNote error={tr.error} />
        <TradeList rows={tr.data ?? []} />
      </Section>
      <p className="mt-3 text-xs text-ink-faint">Charges are estimates: ₹20 per order + STT (options 0.1%, 0.15% from 1 Apr 2026, sell side) + exchange, SEBI, stamp, GST. On-signal = same index and direction, entered while an oscout signal was open (late fills excluded).</p>
    </div>
  );
}

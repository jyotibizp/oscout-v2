import { ReactNode, useEffect, useLayoutEffect, useRef, useState } from "react";
import type { ChainSide, OptionChain } from "../api/client";
import { dateIST, n, signed, timeIST } from "../lib/format";

type View = "oi" | "greeks";
const lakhs = (v: number | null | undefined) => (v == null ? "—" : (v / 1e5).toFixed(2));
const tone = (v: number | null | undefined) => (v == null || v === 0 ? "" : v > 0 ? "text-good" : "text-bad");
const WIDE = "hidden sm:table-cell"; // trimmed at phone width

type Col = { h: string; wide?: boolean; cell: (s: ChainSide) => ReactNode };
const OI_COLS: Col[] = [
  { h: "OI chg%", wide: true, cell: (s) => <span className={tone(s.oi_chg_pct)}>{signed(s.oi_chg_pct, 1)}</span> },
  { h: "OI (L)", cell: (s) => lakhs(s.oi) },
  { h: "LTP chg%", wide: true, cell: (s) => <span className={tone(s.chg_pct)}>{signed(s.chg_pct, 1)}</span> },
  { h: "LTP", cell: (s) => n(s.ltp, 2) },
];
const GREEK_COLS: Col[] = [
  { h: "Vega", wide: true, cell: (s) => n(s.vega, 2) },
  { h: "Gamma", wide: true, cell: (s) => n(s.gamma, 4) },
  { h: "Theta", wide: true, cell: (s) => n(s.theta, 1) },
  { h: "Delta", cell: (s) => n(s.delta, 2) },
  { h: "IV", cell: (s) => n(s.iv, 1) },
];

/** Kite-style chain: Calls | Strike | Puts. ATM row highlighted, ITM sides shaded, spot line between strikes, signal strike marked. */
export function ChainTable({ c, view, fill = false }: { c: OptionChain; view: View; fill?: boolean }) {
  const cols = view === "oi" ? OI_COLS : GREEK_COLS;
  const callCols = cols, putCols = [...cols].reverse();
  const box = useRef<HTMLDivElement>(null);
  const atmRow = useRef<HTMLTableRowElement>(null);
  const centred = useRef(false);
  useLayoutEffect(() => { // centre on ATM once, inside the box only (never scroll the page)
    if (centred.current || !box.current || !atmRow.current) return;
    box.current.scrollTop = atmRow.current.offsetTop - box.current.clientHeight / 2;
    centred.current = true;
  });
  const spotAfter = c.rows.findIndex((r, i) => r.strike <= c.spot && (c.rows[i + 1]?.strike ?? Infinity) > c.spot);
  const narrow = cols.filter((x) => !x.wide).length;
  // colSpan must match the visible columns, or hidden phone columns leave a phantom one
  const spanned = (full: number, small: number, cls: string, body: ReactNode, key: string) => [
    <th key={`${key}w`} colSpan={full} className={`${WIDE} ${cls}`}>{body}</th>,
    <th key={`${key}n`} colSpan={small} className={`sm:hidden ${cls}`}>{body}</th>,
  ];
  const cell = (s: ChainSide | null, col: Col, itm: boolean, k: string) => (
    <td key={k} className={`px-2 py-1 text-right num ${col.wide ? WIDE : ""} ${itm ? "bg-warn/5" : ""}`}>{s ? col.cell(s) : "—"}</td>
  );
  return (
    <div ref={box} className={`overflow-auto rounded-lg border border-line ${fill ? "h-full" : "max-h-[420px]"}`}>
      <table className="w-full text-xs">
        <thead className="sticky top-0 z-10 bg-panel text-ink-faint">
          <tr>
            {spanned(cols.length, narrow, "px-2 py-1 text-center font-semibold text-good", "CALLS", "c")}
            <th className="px-2 py-1" />
            {spanned(cols.length, narrow, "px-2 py-1 text-center font-semibold text-bad", "PUTS", "p")}
          </tr>
          <tr className="border-b border-line">
            {callCols.map((x) => <th key={`c${x.h}`} className={`px-2 py-1 text-right font-medium ${x.wide ? WIDE : ""}`}>{x.h}</th>)}
            <th className="px-2 py-1 text-center font-medium">Strike</th>
            {putCols.map((x) => <th key={`p${x.h}`} className={`px-2 py-1 text-right font-medium ${x.wide ? WIDE : ""}`}>{x.h}</th>)}
          </tr>
        </thead>
        <tbody>
          {c.rows.map((r, i) => {
            const atm = r.strike === c.atm;
            const sig = c.signal?.strike === r.strike ? c.signal : null;
            return [
              <tr key={r.strike} ref={atm ? atmRow : undefined} className={`border-b border-line/50 ${atm ? "bg-accent-soft" : ""}`}>
                {callCols.map((x) => cell(r.ce, x, r.strike < c.spot, `c${x.h}`))}
                <td className="px-2 py-1 text-center font-semibold num whitespace-nowrap">
                  {sig?.option === "CE" && <span className="mr-1 rounded bg-good/20 px-1 text-good" title={`Signal strike (≈${sig.target_delta} delta)`}>CE ●</span>}
                  {r.strike}{atm && <span className="ml-1 text-[10px] text-accent">ATM</span>}
                  {sig?.option === "PE" && <span className="ml-1 rounded bg-bad/20 px-1 text-bad" title={`Signal strike (≈${sig.target_delta} delta)`}>● PE</span>}
                </td>
                {putCols.map((x) => cell(r.pe, x, r.strike > c.spot, `p${x.h}`))}
              </tr>,
              i === spotAfter && (
                <tr key={`spot${r.strike}`} aria-label="spot">
                  {spanned(cols.length * 2 + 1, narrow * 2 + 1, "p-0 font-normal",
                    <div className="flex items-center gap-2 text-[11px] text-warn"><span className="h-px flex-1 bg-warn/70" />Spot {n(c.spot, 2)}<span className="h-px flex-1 bg-warn/70" /></div>, "s")}
                </tr>
              ),
            ];
          })}
        </tbody>
      </table>
    </div>
  );
}

function ViewToggle({ view, onView }: { view: View; onView: (v: View) => void }) {
  return (
    <div role="group" aria-label="Chain view" className="inline-flex rounded-full border border-line p-0.5 text-xs">
      {(["oi", "greeks"] as View[]).map((v) => (
        <button key={v} aria-pressed={view === v} onClick={() => onView(v)}
          className={`rounded-full px-3 py-1 font-medium ${view === v ? "bg-accent-strong text-white" : "text-accent hover:bg-raise"}`}>{v === "oi" ? "OI" : "Greeks"}</button>
      ))}
    </div>
  );
}

/** Chain tab body: expiry header, OI / Greeks toggle, table; ⤢ opens it full screen. */
export function ChainPanel({ sym, c, error }: { sym: string; c: OptionChain | null; error: string | null }) {
  const [view, setView] = useState<View>("oi");
  const [max, setMax] = useState(false);
  useEffect(() => {
    if (!max) return;
    const key = (e: KeyboardEvent) => e.key === "Escape" && setMax(false);
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [max]);
  if (!c) return <p className="text-sm text-ink-faint">{error ?? "Loading chain…"}</p>;
  const head = (full: boolean) => (
    <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-xs text-ink-faint">
      <span>Expiry <b className="text-ink">{dateIST(c.expiry)}</b> · {n(c.days_to_expiry, 1)}d · as of {timeIST(c.as_of)} IST</span>
      <div className="flex items-center gap-2">
        <ViewToggle view={view} onView={setView} />
        {full ? <button className="btn !px-3 !py-1" aria-label="Close" onClick={() => setMax(false)}>✕</button>
          : <button className="btn !px-3 !py-1" aria-label="Maximize chain" onClick={() => setMax(true)}>⤢ Maximize</button>}
      </div>
    </div>
  );
  return (
    <div className="min-w-0">
      {head(false)}
      {error && <p className="mb-2 text-xs text-bad">{error}</p>}
      <ChainTable c={c} view={view} />
      {max && (
        <div role="dialog" aria-modal="true" aria-label={`${sym} option chain`} className="fixed inset-0 z-50 flex flex-col bg-canvas p-4">
          <div className="mb-1 text-sm font-bold tracking-wide">{sym} · option chain</div>
          {head(true)}
          <div className="min-h-0 flex-1"><ChainTable c={c} view={view} fill /></div>
        </div>
      )}
    </div>
  );
}

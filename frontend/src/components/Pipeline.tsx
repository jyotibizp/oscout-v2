import { Gate, ScanResult } from "../api/client";
import { Badge } from "./ui";

const STEPS: { key: "gate1" | "gate2" | "atr" | "vix"; title: string; sub: string }[] = [
  { key: "gate1", title: "GATE 1", sub: "5M ADX BREAKOUT" },
  { key: "gate2", title: "GATE 2", sub: "15M ADX PATTERN" },
  { key: "atr", title: "ATR FILTER", sub: "EXHAUSTION CHECK" },
  { key: "vix", title: "VIX FILTER", sub: "INDIA VIX" },
];

/** Qualification pipeline: every gate with its status and the actual reasons. */
export function Pipeline({ r, compact = false }: { r: ScanResult; compact?: boolean }) {
  const d = r.details;
  const gate = (k: (typeof STEPS)[number]["key"]): Gate | undefined => d?.[k];
  const signal = r.final_result === "SIGNAL" || d?.state === "QUALIFIED";
  return (
    <ol className="space-y-1.5">
      {STEPS.map((s) => {
        const g = gate(s.key);
        const st = g?.status ?? "SKIP";
        const exhausted = s.key === "atr" && g?.metrics?.atr_status === "EXHAUSTED";
        return (
          <li key={s.key} className={`rounded-md border px-3 py-2 ${st === "PASS" ? "border-good/30" : st === "FAIL" ? "border-bad/40" : st === "WAIT" ? "border-warn/40" : "border-line"} bg-raise/40`}>
            <div className="flex items-center justify-between gap-3">
              <div className="text-xs">
                <span className="font-semibold text-ink">{s.title}</span>
                <span className="ml-2 text-ink-faint">{s.sub}</span>
              </div>
              <Badge s={exhausted ? "EXHAUSTED" : st} />
            </div>
            {!compact && g?.reasons?.length ? (
              <ul className="mt-1.5 space-y-0.5 text-xs text-ink-soft">
                {g.reasons.slice(0, 5).map((x, i) => <li key={i}>• {x}</li>)}
              </ul>
            ) : null}
          </li>
        );
      })}
      <li className={`rounded-md border px-3 py-2 flex items-center justify-between ${signal ? "border-accent bg-accent/10" : "border-line bg-raise/40"}`}>
        <span className="text-xs font-semibold">FINAL</span>
        {signal ? <Badge s="SIGNAL" label={`${r.direction} BUY`} /> : <span className="text-xs text-ink-faint">NO SIGNAL</span>}
      </li>
    </ol>
  );
}

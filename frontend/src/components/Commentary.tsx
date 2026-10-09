import type { Commentary as C } from "../api/client";
import { Badge } from "./ui";

/** Plain-language read-out stored with each scan: gate distances, earliest setup time and one CE / PE rule. */
export function Commentary({ c }: { c?: C | null }) {
  if (!c) return null;
  return (
    <div className="space-y-2">
      <div className="text-xs uppercase tracking-widest text-ink-faint">Commentary{c.candle_close ? ` · ${c.candle_close} IST candle` : ""}</div>
      <p className="text-sm text-ink font-medium">{c.headline}</p>
      <ul className="space-y-1.5">
        {c.lines.map((l) => (
          <li key={l.gate} className="flex gap-2 text-xs text-ink-soft leading-relaxed">
            <span className="w-24 shrink-0 text-ink-faint">{l.gate}</span>
            <span className="shrink-0"><Badge s={l.status} /></span>
            <span>{l.text}</span>
          </li>
        ))}
      </ul>
      {c.compression && <p className="text-xs text-ink-soft"><span className="text-ink font-medium">Setup:</span> {c.compression.text}</p>}
      {c.rules.map((v) => <p key={v.direction} className="text-xs text-ink-soft"><span className="text-ink font-medium">{v.option}:</span> {v.text}</p>)}
      {c.outlook && <p className="text-xs text-ink">{c.outlook}</p>}
    </div>
  );
}

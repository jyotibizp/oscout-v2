import { ReactNode } from "react";

/** Status → tone. Status colours are reserved for state and always carry a text label. */
const TONE: Record<string, string> = {
  PASS: "text-good border-good/40 bg-good/10",
  SIGNAL: "text-white border-accent-strong bg-accent-strong",
  SIGNAL_GENERATED: "text-white border-accent-strong bg-accent-strong",
  QUALIFIED: "text-good border-good/40 bg-good/10",
  ACTIVE: "text-accent border-accent/50 bg-accent/10",
  WAIT: "text-warn border-warn/40 bg-warn/10",
  WARNING: "text-warn border-warn/40 bg-warn/10",
  COMPRESSION: "text-warn border-warn/40 bg-warn/10",
  BREAKOUT_DETECTED: "text-warn border-warn/40 bg-warn/10",
  WAITING_CONFIRMATION: "text-warn border-warn/40 bg-warn/10",
  FAIL: "text-bad border-bad/40 bg-bad/10",
  FAILED: "text-bad border-bad/40 bg-bad/10",
  REJECTED: "text-bad border-bad/40 bg-bad/10",
  EXHAUSTED: "text-bad border-bad/40 bg-bad/10",
  STALE: "text-bad border-bad/40 bg-bad/10",
  ERROR: "text-bad border-bad/40 bg-bad/10",
  MISSING: "text-bad border-bad/40 bg-bad/10",
  HEALTHY: "text-good border-good/40 bg-good/10",
  NORMAL: "text-good border-good/40 bg-good/10",
  EXIT_TRIGGERED: "text-ink-soft border-line bg-raise",
  EXPIRED: "text-ink-faint border-line bg-raise",
  WATCHING: "text-ink-soft border-line bg-raise",
  SKIP: "text-ink-faint border-line bg-transparent",
  CLOSED: "text-ink-soft border-line bg-raise",
  OPEN: "text-accent border-accent/50 bg-accent/10",
};
const ICON: Record<string, string> = { PASS: "✓", FAIL: "✕", FAILED: "✕", WAIT: "…", SKIP: "—", SIGNAL: "●", EXHAUSTED: "!", REJECTED: "✕" };

export function Badge({ s, label, className = "" }: { s?: string | null; label?: string; className?: string }) {
  const key = s ?? "SKIP";
  const text = label ?? (key === "SKIP" ? "—" : key.replace(/_/g, " "));
  return (
    <span className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs font-semibold tracking-wide ${TONE[key] ?? TONE.WATCHING} ${className}`}>
      {ICON[key] && key !== "SKIP" && <span aria-hidden>{ICON[key]}</span>}
      {text}
    </span>
  );
}

export function Dir({ d }: { d?: string | null }) {
  if (!d) return <span className="text-ink-faint">—</span>;
  return <span className={`font-semibold ${d === "CALL" ? "text-good" : "text-bad"}`}>{d === "CALL" ? "▲ CALL" : "▼ PUT"}</span>;
}

export function PageHeader({ title, sub, right }: { title: string; sub?: string; right?: ReactNode }) {
  return (
    <div className="flex items-end justify-between gap-4 mb-5">
      <div>
        <h1 className="text-lg font-semibold text-ink">{title}</h1>
        {sub && <p className="text-sm text-ink-faint mt-0.5">{sub}</p>}
      </div>
      {right}
    </div>
  );
}

export function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="card px-4 py-3">
      <div className="text-xs uppercase tracking-wider text-ink-faint">{label}</div>
      <div className="num text-xl text-ink mt-1">{value}</div>
      {sub && <div className="text-xs text-ink-faint mt-0.5">{sub}</div>}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="card px-4 py-10 text-center text-sm text-ink-faint">{children}</div>;
}

export function ErrorNote({ error }: { error: string | null }) {
  if (!error) return null;
  return <div className="card border-bad/40 px-4 py-3 text-sm text-bad mb-4">Could not load data: {error}</div>;
}

export function Drawer({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 flex justify-end" role="dialog" aria-modal>
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative h-full w-full max-w-2xl overflow-y-auto bg-panel border-l border-line p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="text-base font-semibold">{title}</div>
          <button className="btn" onClick={onClose}>Close</button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-xs uppercase tracking-wider text-ink-faint">
      {label}
      {children}
    </label>
  );
}

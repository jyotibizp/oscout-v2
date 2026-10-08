import { useState } from "react";

/** Minimal, dependency-free SVG charts: one hue, recessive grid, hover tooltips. */

export function LineChart({ points, height = 220, format = (v: number) => v.toFixed(1), label }: {
  points: { x: string; y: number; tip?: string }[]; height?: number; format?: (v: number) => string; label: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  if (points.length === 0) return <div className="h-40 grid place-items-center text-sm text-ink-faint">No closed trades yet</div>;
  const W = 640, H = height, m = { l: 48, r: 12, t: 12, b: 24 };
  const ys = points.map((p) => p.y).concat(0);
  const lo = Math.min(...ys), hi = Math.max(...ys);
  const span = hi - lo || 1;
  const X = (i: number) => m.l + ((W - m.l - m.r) * i) / Math.max(points.length - 1, 1);
  const Y = (v: number) => m.t + (H - m.t - m.b) * (1 - (v - lo) / span);
  const ticks = [lo, lo + span / 2, hi];
  const path = points.map((p, i) => `${i ? "L" : "M"}${X(i)},${Y(p.y)}`).join("");
  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label={label}
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
          const sx = ((e.clientX - r.left) * W) / r.width;
          const i = Math.round(((sx - m.l) / (W - m.l - m.r)) * (points.length - 1));
          setHover(Math.max(0, Math.min(points.length - 1, i)));
        }}>
        {ticks.map((t, i) => (
          <g key={i}>
            <line x1={m.l} x2={W - m.r} y1={Y(t)} y2={Y(t)} stroke="#22304a" />
            <text x={m.l - 6} y={Y(t) + 4} textAnchor="end" fontSize="10" fill="#71809a">{format(t)}</text>
          </g>
        ))}
        <line x1={m.l} x2={W - m.r} y1={Y(0)} y2={Y(0)} stroke="#71809a" strokeDasharray="3 3" />
        <path d={path} fill="none" stroke="#3b82f6" strokeWidth="2" />
        {hover !== null && (
          <g>
            <line x1={X(hover)} x2={X(hover)} y1={m.t} y2={H - m.b} stroke="#a9b4c6" strokeWidth="1" />
            <circle cx={X(hover)} cy={Y(points[hover].y)} r="4" fill="#3b82f6" stroke="#111a2b" strokeWidth="2" />
          </g>
        )}
      </svg>
      {hover !== null && (
        <div className="pointer-events-none absolute top-2 right-2 rounded border border-line bg-canvas/95 px-2 py-1 text-xs">
          <div className="text-ink-faint">{points[hover].x}</div>
          <div className="num text-ink">{format(points[hover].y)}</div>
          {points[hover].tip && <div className="text-ink-soft">{points[hover].tip}</div>}
        </div>
      )}
    </div>
  );
}

export function BarList({ rows, format = (v: number) => String(v), signedColors = false }: {
  rows: { label: string; value: number; sub?: string }[]; format?: (v: number) => string; signedColors?: boolean;
}) {
  if (rows.length === 0) return <div className="text-sm text-ink-faint py-6 text-center">No data yet</div>;
  const max = Math.max(...rows.map((r) => Math.abs(r.value)), 1e-9);
  return (
    <div className="space-y-1.5">
      {rows.map((r) => (
        <div key={r.label} className="grid grid-cols-[96px_1fr_72px] items-center gap-2 text-xs" title={r.sub}>
          <span className="text-ink-soft truncate">{r.label}</span>
          <div className="h-3 rounded-sm bg-raise">
            <div className={`h-3 rounded-sm ${signedColors ? (r.value >= 0 ? "bg-accent" : "bg-ink-faint") : "bg-accent"}`}
              style={{ width: `${(Math.abs(r.value) / max) * 100}%` }} />
          </div>
          <span className="num text-right text-ink">{format(r.value)}</span>
        </div>
      ))}
    </div>
  );
}

export function Sparkline({ values, height = 40, threshold }: { values: (number | null)[]; height?: number; threshold?: number }) {
  const v = values.filter((x): x is number => x !== null);
  if (v.length < 2) return null;
  const W = 240, H = height;
  const lo = Math.min(...v, threshold ?? Infinity) - 1, hi = Math.max(...v, threshold ?? -Infinity) + 1;
  const X = (i: number) => (W * i) / (v.length - 1);
  const Y = (y: number) => H - ((y - lo) / (hi - lo)) * H;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height }} role="img" aria-label="5m ADX">
      {threshold !== undefined && <line x1={0} x2={W} y1={Y(threshold)} y2={Y(threshold)} stroke="#71809a" strokeDasharray="3 3" />}
      <path d={v.map((y, i) => `${i ? "L" : "M"}${X(i)},${Y(y)}`).join("")} fill="none" stroke="#3b82f6" strokeWidth="1.5" />
    </svg>
  );
}

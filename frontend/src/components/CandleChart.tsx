import { createChart, LineStyle, type IChartApi, type ISeriesApi, type SeriesMarker, type UTCTimestamp } from "lightweight-charts";
import { useEffect, useRef, useState } from "react";
import type { Candle, Setup } from "../api/client";

// lightweight-charts shows times as UTC; shifting by +5:30 makes the axis read IST.
const IST_OFFSET = 19800;
const toTime = (iso: string) => (Math.floor(Date.parse(iso) / 1000) + IST_OFFSET) as UTCTimestamp;
const BAR = 300;

const C = { bg: "#1e1e1e", text: "#ebebeb", grid: "#2a2a2a", line: "#3a3a3a", good: "#3ecf8e", bad: "#ff6b6b", warn: "#f5b14c", accent: "#a99bff", ink: "#ffffff" };

const EXIT_SHORT: Record<string, string> = {
  STOP: "Stop", TRAIL_STOP: "Trail stop", TARGET: "Target", ADX_EXHAUSTION: "ADX exhaust", ADX_PEAK_DECLINE: "ADX off peak",
  DI_REVERSAL: "DI reversal", SESSION_END: "Session end", MAX_HOLD: "Max hold",
};

/** Markers for breakout, signal and exit, snapped to the 5m candle that contains each event. */
export function markersFor(setups: Setup[], first: number, last: number): SeriesMarker<UTCTimestamp>[] {
  const snap = (iso: string | null) => {
    if (!iso) return null;
    const t = toTime(iso);
    const s = (t - (t % BAR)) as UTCTimestamp;
    return s >= first && s <= last ? s : null;
  };
  const out: SeriesMarker<UTCTimestamp>[] = [];
  for (const s of setups) {
    const up = s.direction === "CALL";
    const b = snap(s.breakout_ts);
    if (b) out.push({ time: b, position: up ? "belowBar" : "aboveBar", color: C.warn, shape: "circle", text: "Breakout" });
    const g = snap(s.signal_ts);
    if (g) out.push({ time: g, position: up ? "belowBar" : "aboveBar", color: up ? C.good : C.bad, shape: up ? "arrowUp" : "arrowDown", text: up ? "CE" : "PE" });
    const x = snap(s.exit_ts);
    if (x) out.push({ time: x, position: up ? "aboveBar" : "belowBar", color: C.accent, shape: "square", text: `Exit · ${EXIT_SHORT[s.exit_reason ?? ""] ?? s.exit_reason ?? ""}` });
  }
  return out.sort((a, b) => a.time - b.time);
}

const baseOptions = {
  autoSize: true,
  layout: { background: { color: C.bg }, textColor: C.text, fontFamily: "Inter, system-ui", fontSize: 11 },
  grid: { vertLines: { color: C.grid }, horzLines: { color: C.grid } },
  rightPriceScale: { borderColor: C.line, minimumWidth: 64 },
  timeScale: { borderColor: C.line, timeVisible: true, secondsVisible: false },
  crosshair: { mode: 0 },
  handleScroll: { vertTouchDrag: false },  // let the page scroll on phones
};

/**
 * 5m candles with an ADX/+DI/−DI pane (optional ATR pane), synced time scales, live trade lines and lifecycle markers.
 * `setups` = this index's open, pending and today's closed setups; the open one (no exit) draws Entry / Stop / Target.
 */
export function CandleChart({ candles, setups, level, height, showAtr = false, visible = 75 }: {
  candles: Candle[]; setups: Setup[]; level?: number | null; height: number; showAtr?: boolean; visible?: number;
}) {
  const mainEl = useRef<HTMLDivElement>(null);
  const adxEl = useRef<HTMLDivElement>(null);
  const atrEl = useRef<HTMLDivElement>(null);
  const charts = useRef<IChartApi[]>([]);
  const series = useRef<{ candle?: ISeriesApi<"Candlestick">; adx?: ISeriesApi<"Line">; pdi?: ISeriesApi<"Line">; mdi?: ISeriesApi<"Line">; atr?: ISeriesApi<"Line"> }>({});
  const placed = useRef(false);

  useEffect(() => {
    const els = [mainEl.current, adxEl.current, showAtr ? atrEl.current : null].filter((e): e is HTMLDivElement => !!e);
    const list = els.map((el, i) => createChart(el, {
      ...baseOptions, layout: { ...baseOptions.layout, attributionLogo: i === 0 },
      timeScale: { ...baseOptions.timeScale, visible: i === els.length - 1 },
    }));
    charts.current = list;
    const [main, adx, atr] = list;
    series.current = {
      candle: main.addCandlestickSeries({ upColor: C.good, downColor: C.bad, borderVisible: false, wickUpColor: C.good, wickDownColor: C.bad }),
      adx: adx.addLineSeries({ color: C.ink, lineWidth: 2, priceLineVisible: false, lastValueVisible: true, title: "ADX" }),
      pdi: adx.addLineSeries({ color: C.good, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, title: "+DI" }),
      mdi: adx.addLineSeries({ color: C.bad, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, title: "−DI" }),
      atr: atr?.addLineSeries({ color: C.warn, lineWidth: 2, priceLineVisible: false, title: "ATR" }),
    };
    let syncing = false;
    list.forEach((src) => src.timeScale().subscribeVisibleLogicalRangeChange((r) => {
      if (!r || syncing) return;
      syncing = true;
      list.forEach((t) => t !== src && t.timeScale().setVisibleLogicalRange(r));
      syncing = false;
    }));
    placed.current = false;
    return () => { list.forEach((c) => c.remove()); charts.current = []; series.current = {}; };
  }, [showAtr]);

  useEffect(() => {
    const s = series.current;
    if (!s.candle || !candles.length) return;
    const times = candles.map((c) => toTime(c.ts));
    s.candle.setData(candles.map((c, i) => ({ time: times[i], open: c.open, high: c.high, low: c.low, close: c.close })));
    const line = (k: "adx" | "pdi" | "mdi" | "atr") =>
      candles.flatMap((c, i) => (c[k] == null ? [] : [{ time: times[i], value: c[k] as number }]));
    s.adx?.setData(line("adx"));
    s.pdi?.setData(line("pdi"));
    s.mdi?.setData(line("mdi"));
    s.atr?.setData(line("atr"));
    s.candle.setMarkers(markersFor(setups, times[0], times[times.length - 1]));

    const open = setups.find((x) => x.signal_ts && !x.exit_ts);
    const lines = open ? [
      { price: open.entry_price, color: C.ink, style: LineStyle.Dashed, title: "Entry" },
      { price: open.tracking?.stop ?? open.stop_price, color: C.bad, style: LineStyle.Solid, title: open.tracking?.stop_moved ? "Stop (moved)" : "Stop" },
      { price: open.target_price, color: C.good, style: LineStyle.Solid, title: "Target" },
    ].filter((l) => l.price != null).map((l) => s.candle!.createPriceLine({ price: l.price as number, color: l.color, lineWidth: 1, lineStyle: l.style, title: l.title })) : [];
    const lvl = level != null && s.adx ? s.adx.createPriceLine({ price: level, color: C.warn, lineWidth: 1, lineStyle: LineStyle.Dashed, title: "" }) : null;

    if (!placed.current) {
      const last = candles.length - 1;
      charts.current.forEach((c) => c.timeScale().setVisibleLogicalRange({ from: Math.max(0, last - visible), to: last + 2 }));
      placed.current = true;
    }
    return () => {
      lines.forEach((l) => s.candle?.removePriceLine(l));
      if (lvl) s.adx?.removePriceLine(lvl);
    };
  }, [candles, setups, level, visible, showAtr]);

  const mainH = Math.round(height * (showAtr ? 0.56 : 0.66));
  const paneH = Math.round((height - mainH) / (showAtr ? 2 : 1));
  return (
    <div className="w-full" data-testid="candle-chart">
      <div ref={mainEl} style={{ height: mainH }} aria-label="5-minute candles" />
      <div className="relative border-t border-line">
        <div ref={adxEl} style={{ height: paneH }} aria-label="ADX, +DI, −DI" />
        <span className="pointer-events-none absolute left-2 top-1 text-[11px] text-ink-faint">ADX · <span className="text-good">+DI</span> · <span className="text-bad">−DI</span></span>
      </div>
      {showAtr && (
        <div className="relative border-t border-line">
          <div ref={atrEl} style={{ height: paneH }} aria-label="ATR" />
          <span className="pointer-events-none absolute left-2 top-1 text-[11px] text-ink-faint">ATR</span>
        </div>
      )}
    </div>
  );
}

const TV_SYMBOL: Record<string, string> = { NIFTY: "NSE:NIFTY", SENSEX: "BSE:SENSEX", BANKNIFTY: "NSE:BANKNIFTY" };

/** TradingView's free Advanced Chart widget, for free exploration (their data feed, none of our lines). */
export function TradingViewChart({ sym }: { sym: string }) {
  const el = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const host = el.current;
    if (!host) return;
    host.innerHTML = '<div class="tradingview-widget-container__widget" style="height:100%;width:100%"></div>';
    const s = document.createElement("script");
    s.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    s.async = true;
    s.innerHTML = JSON.stringify({
      symbol: TV_SYMBOL[sym] ?? sym, interval: "5", timezone: "Asia/Kolkata", theme: "dark", style: "1", locale: "en",
      autosize: true, allow_symbol_change: true, hide_side_toolbar: false, support_host: "https://www.tradingview.com",
    });
    host.appendChild(s);
    return () => { host.innerHTML = ""; };
  }, [sym]);
  return <div ref={el} className="tradingview-widget-container h-full w-full" />;
}

/** Full-screen chart: same chart with more history, ATR pane toggle and a TradingView switch. Esc / ✕ closes. */
export function ChartOverlay({ sym, candles, setups, level, onClose }: {
  sym: string; candles: Candle[]; setups: Setup[]; level?: number | null; onClose: () => void;
}) {
  const [tv, setTv] = useState(false);
  const [atr, setAtr] = useState(true);
  const [h, setH] = useState(() => (typeof window === "undefined" ? 700 : window.innerHeight - 64));
  useEffect(() => {
    const key = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    const size = () => setH(window.innerHeight - 64);
    window.addEventListener("keydown", key);
    window.addEventListener("resize", size);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", key); window.removeEventListener("resize", size); document.body.style.overflow = prev; };
  }, [onClose]);
  return (
    <div role="dialog" aria-modal="true" aria-label={`${sym} chart`} className="fixed inset-0 z-50 flex flex-col bg-canvas">
      <div className="flex items-center justify-between gap-2 border-b border-line px-4 py-2">
        <span className="text-sm font-bold tracking-wide">{sym} · 5m</span>
        <div className="flex items-center gap-2">
          {!tv && <button className="btn" aria-pressed={atr} onClick={() => setAtr((v) => !v)}>ATR {atr ? "on" : "off"}</button>}
          <button className="btn" onClick={() => setTv((v) => !v)}>{tv ? "Our chart" : "TradingView"}</button>
          <button className="btn" aria-label="Close" onClick={onClose}>✕</button>
        </div>
      </div>
      <div className="flex-1 min-h-0">
        {tv ? <TradingViewChart sym={sym} />
          : <CandleChart candles={candles} setups={setups} level={level} height={h} showAtr={atr} visible={225} />}
      </div>
      {tv && <p className="px-4 py-1 text-xs text-ink-faint">TradingView data feed (may be delayed for NSE/BSE); our signal lines are on "Our chart".</p>}
    </div>
  );
}

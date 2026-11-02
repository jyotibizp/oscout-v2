import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import type { Setup } from "../api/client";
import { ChartOverlay, markersFor } from "./CandleChart";

// canvas charts don't run in jsdom: stub the library, test our wiring
vi.mock("lightweight-charts", () => {
  const series = () => ({ setData: vi.fn(), setMarkers: vi.fn(), createPriceLine: vi.fn(() => ({})), removePriceLine: vi.fn() });
  const chart = () => ({
    addCandlestickSeries: series, addLineSeries: series, remove: vi.fn(),
    timeScale: () => ({ subscribeVisibleLogicalRangeChange: vi.fn(), setVisibleLogicalRange: vi.fn() }),
  });
  return { createChart: vi.fn(chart), LineStyle: { Solid: 0, Dashed: 2 } };
});

const setup = (over: Partial<Setup> = {}): Setup => ({
  id: 1, symbol: "NIFTY", direction: "CALL", state: "ACTIVE", breakout_ts: "2026-11-02T04:30:00+00:00", detected_at: "", config_version: "1.0.2",
  breakout: {}, signal_ts: "2026-11-02T04:42:10+00:00", entry_price: 22500, entry_atr: 20, stop_price: 22440, target_price: 22590,
  signal_context: null, peak_adx: null, exit_ts: null, exit_price: null, exit_reason: null, closed_reason: null, trade: null, ...over,
});
const t = (iso: string) => Date.parse(iso) / 1000 + 19800;

test("markers snap to the 5m candle in IST and skip events outside the chart", () => {
  const m = markersFor([setup({ exit_ts: "2026-11-02T06:00:00+00:00", exit_reason: "TARGET" })], t("2026-11-02T04:00:00Z"), t("2026-11-02T05:30:00Z"));
  expect(m.map((x) => x.text)).toEqual(["Breakout", "CE"]);
  expect(m[1].time).toBe(t("2026-11-02T04:40:00Z"));
  expect(m[1].shape).toBe("arrowUp");
});

test("overlay closes on Esc and switches to TradingView", () => {
  const close = vi.fn();
  const candles = [{ ts: "2026-11-02T04:30:00+00:00", open: 1, high: 2, low: 0.5, close: 1.5, adx: 20, pdi: 25, mdi: 15, atr: 10 }];
  render(<ChartOverlay sym="NIFTY" candles={candles} setups={[setup()]} level={18} onClose={close} />);
  expect(screen.getByTestId("candle-chart")).toBeInTheDocument();
  fireEvent.click(screen.getByText("TradingView"));
  expect(screen.queryByTestId("candle-chart")).not.toBeInTheDocument();
  expect(screen.getByText("Our chart")).toBeInTheDocument();
  fireEvent.keyDown(window, { key: "Escape" });
  expect(close).toHaveBeenCalled();
});

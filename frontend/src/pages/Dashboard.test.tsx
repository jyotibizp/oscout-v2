import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import { api } from "../api/client";
import Dashboard from "./Dashboard";

vi.mock("lightweight-charts", () => {
  const series = () => ({ setData: vi.fn(), setMarkers: vi.fn(), createPriceLine: vi.fn(() => ({})), removePriceLine: vi.fn() });
  const chart = () => ({
    addCandlestickSeries: series, addLineSeries: series, remove: vi.fn(),
    timeScale: () => ({ subscribeVisibleLogicalRangeChange: vi.fn(), setVisibleLogicalRange: vi.fn() }),
  });
  return { createChart: vi.fn(chart), LineStyle: { Solid: 0, Dashed: 2 } };
});

const result = (symbol: string) => ({
  id: 1, scan_run_id: 1, symbol, candle_ts: "2026-11-02T04:30:00+00:00", final_result: "NO_SIGNAL", state: "WATCHING", direction: null,
  config_version: "1.0.2", details: { gate1: { status: "WAIT", reasons: [], metrics: {} }, gate2: { status: "WAIT", reasons: [], metrics: {} },
    atr: { status: "WAIT", reasons: [], metrics: {} }, vix: { status: "WAIT", reasons: [], metrics: {} } },
});

beforeEach(() => {
  localStorage.clear();
  vi.spyOn(api, "latest").mockResolvedValue({ run: null, symbols: { NIFTY: result("NIFTY"), SENSEX: result("SENSEX") } } as any);
  vi.spyOn(api, "activeSignals").mockResolvedValue({ active: [], pending: [], exited_today: [] });
  vi.spyOn(api, "candles").mockResolvedValue([{ ts: "2026-11-02T04:30:00+00:00", open: 1, high: 2, low: 0.5, close: 1.5, adx: 20, pdi: 25, mdi: 15, atr: 10 }]);
});
afterEach(() => vi.restoreAllMocks());

test("card switches to the Chart tab, remembers it, and maximizes", async () => {
  render(<Dashboard />);
  const chartTabs = await screen.findAllByRole("tab", { name: "Chart" });
  fireEvent.click(chartTabs[0]);
  expect(await screen.findByTestId("candle-chart")).toBeInTheDocument();
  expect(localStorage.getItem("oscout.cardTab.NIFTY")).toBe("chart");
  fireEvent.click(screen.getByRole("button", { name: "Maximize chart" }));
  expect(screen.getByRole("dialog", { name: "NIFTY chart" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Close" }));
  expect(screen.queryByRole("dialog")).toBeNull();
});

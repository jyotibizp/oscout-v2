import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import { api } from "../api/client";
import { resetSymbolsCache } from "../lib/symbols";
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
  resetSymbolsCache();
  vi.spyOn(api, "symbols").mockResolvedValue([{ symbol: "NIFTY", testing: false }, { symbol: "SENSEX", testing: false }, { symbol: "BANKNIFTY", testing: true }]);
  vi.spyOn(api, "latest").mockResolvedValue({ run: null, symbols: { NIFTY: result("NIFTY"), SENSEX: result("SENSEX"), BANKNIFTY: result("BANKNIFTY") } } as any);
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

test("Chain tab shows the chain with ATM and signal strike, and toggles to Greeks", async () => {
  const side = (ltp: number, delta: number) => ({ ltp, chg_pct: 1, oi: 2e6, oi_chg_pct: 5, iv: 13, delta, theta: -20, gamma: 0.002, vega: 3 });
  vi.spyOn(api, "chain").mockResolvedValue({
    symbol: "NIFTY", expiry: "2026-11-03", spot: 22469, atm: 22450, days_to_expiry: 0.7, as_of: "2026-11-02T10:00:00+00:00",
    rows: [22400, 22450, 22500].map((k, i) => ({ strike: k, ce: side(90 - i * 30, 0.7 - i * 0.15), pe: side(25 + i * 20, -0.3 - i * 0.15) })),
    signal: { direction: "CALL", option: "CE", strike: 22400, target_delta: 0.7 },
  });
  render(<Dashboard />);
  fireEvent.click((await screen.findAllByRole("tab", { name: "Chain" }))[0]);
  expect(await screen.findByText("ATM")).toBeInTheDocument();
  expect(screen.getByText("CE ●")).toBeInTheDocument();
  expect(screen.getAllByText(/Spot 22469/).length).toBeGreaterThan(0);
  expect(screen.queryAllByText("Delta")).toHaveLength(0);
  fireEvent.click(screen.getByRole("button", { name: "Greeks" }));
  expect(screen.getAllByText("Delta").length).toBe(2);
});

test("BANKNIFTY gets a third card tagged TESTING", async () => {
  render(<Dashboard />);
  expect(await screen.findByText("TESTING")).toBeInTheDocument();
  expect(await screen.findAllByRole("tab", { name: "Chain" })).toHaveLength(3);
});

test("index chips replace the header and show only the selected cards and commentary", async () => {
  render(<Dashboard />);
  expect(screen.queryByText("Is there a trade right now?")).toBeNull();
  expect(await screen.findAllByRole("tab", { name: "Chain" })).toHaveLength(3);
  fireEvent.click(screen.getByRole("button", { name: /^SENSEX/ }));
  expect(await screen.findAllByRole("tab", { name: "Chain" })).toHaveLength(2);
  expect(screen.queryByRole("heading", { name: "SENSEX" })).toBeNull();
  expect(JSON.parse(localStorage.getItem("oscout.dashboardSymbols")!)).toEqual(["NIFTY", "BANKNIFTY"]);
  fireEvent.click(screen.getByRole("button", { name: /^NIFTY/ }));
  fireEvent.click(screen.getByRole("button", { name: /^BANKNIFTY/ }));  // last one stays: never an empty dashboard
  expect(screen.getAllByRole("tab", { name: "Chain" })).toHaveLength(1);
  expect(screen.getByRole("button", { name: /^BANKNIFTY/ })).toHaveAttribute("aria-pressed", "true");
});

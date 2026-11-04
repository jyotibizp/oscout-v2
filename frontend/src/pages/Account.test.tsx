import { render, screen } from "@testing-library/react";
import { vi } from "vitest";
import { api } from "../api/client";
import { resetRoleCache } from "../lib/role";
import Account, { inr } from "./Account";

afterEach(() => { vi.restoreAllMocks(); resetRoleCache(); });

const agg = { trades: 0, wins: 0, win_rate: null, net: 0, avg: null, avg_win: null, avg_loss: null, profit_factor: null };
const stats = {
  totals: { ...agg, trades: 3, wins: 1, net: -900, open: 0, days: 1, green_days: 0, first: "2026-10-06", last: "2026-10-06" },
  stop_after: [{ n: 1, net: 1400, vs_actual: 2300 }, { n: 2, net: 600, vs_actual: 1500 }],
  adds: [{ ...agg, bucket: "10+", trades: 2, wins: 0, net: -5000 }], hold: [],
  gap_prev: [{ ...agg, bucket: "<1m", trades: 2, net: -1500 }], gave_back: { days: 1, total: 2300, green_to_red: 1, of_days: 1 },
  charges: { gross: -700, charges: 200, net: -900, brokerage: 120, stt: 30, pct_of_gross: null, per_trade: 66 },
  system: { signals: 1, net_r: 0.5, win_rate: 100, taken: 1, on_signal: { ...agg, trades: 1, net: 1400 }, off_signal: { ...agg, trades: 2, net: -2300 } },
  tilt: { after_loss_min: 2, after_loss_n: 1, after_win_min: 10, after_win_n: 1 }, after_two_losses: { next: agg, overall_win_rate: 33.3 },
  scalp: [], heatmap: [{ weekday: 0, hour: 9, trades: 3, net: -900 }], by_trade_number: [], by_day_count: [], reentry_after_loss: [],
  reentry_after_win: agg, flags: {}, frequency: { days: 1, trades_per_day: 3, max_per_day: 3, by_hour: [], max_burst15: 3 },
  orders: { placed: 0, complete: 0, cancelled: 0, rejected: 0, modified: null, days: 0, per_day: null, since: null, shortest_gap_sec: null, median_gap_sec: null, per_round_trip: null, by_hour: [] },
  days: [{ day: "2026-10-06", trades: 3, net: -900, peak: 1400, burst15: 3, orders: null }], equity: [],
};

test("rupee format", () => {
  expect(inr(-2300)).toBe("−₹2,300");
  expect(inr(150000)).toBe("+₹1,50,000");
});

test("admin sees the hard-truth cards", async () => {
  vi.spyOn(api, "whoami").mockResolvedValue({ role: "admin" });
  vi.spyOn(api, "acctStatus").mockResolvedValue({ fills: 6, first_fill: null, last_fill: null, orders: 0, last_sync: { at: null, trades_added: 0, orders: 0, error: null } });
  vi.spyOn(api, "acctStats").mockResolvedValue(stats as any);
  vi.spyOn(api, "acctTrades").mockResolvedValue([]);
  render(<Account />);
  expect(await screen.findByText("If you'd stopped after N trades a day")).toBeInTheDocument();
  expect(screen.getByText("Your extra (off-signal) trades")).toBeInTheDocument();
  expect(screen.getByText("Adds per position (10+ adds)")).toBeInTheDocument();
  expect(screen.getByText("Held over 1 hour")).toBeInTheDocument();
  expect(screen.getAllByText("−₹2,300").length).toBeGreaterThan(0);
});

test("viewers don't see it", async () => {
  vi.spyOn(api, "whoami").mockResolvedValue({ role: "viewer" });
  render(<Account />);
  expect(await screen.findByText(/private to the Mac/)).toBeInTheDocument();
});

import { render, screen } from "@testing-library/react";
import type { ScanResult, Setup } from "../api/client";
import { Commentary } from "./Commentary";
import { Pipeline } from "./Pipeline";
import { SignalCard } from "./SignalCard";
import { Badge } from "./ui";

const gate = (status: "PASS" | "FAIL" | "WAIT" | "SKIP", reasons: string[] = [], metrics: Record<string, any> = {}) => ({ status, reasons, metrics });

function result(over: Partial<ScanResult> = {}): ScanResult {
  return {
    id: 1, scan_run_id: 1, symbol: "NIFTY", candle_ts: "2026-10-07T04:30:00+00:00", created_at: null, adx5: 19.5, pdi5: 28, mdi5: 14,
    adx15: 22, pdi15: 25, mdi15: 15, atr: 10, atr_status: "NORMAL", vix: 14, vix_change_pct: 1, gate1: "PASS", gate2: "PASS",
    atr_filter: "FAIL", vix_filter: "SKIP", final_result: "NO_SIGNAL", state: "REJECTED", direction: "CALL", rejection_reason: "ATR EXHAUSTED",
    config_version: "1.0.0", setup_id: null,
    details: {
      gate1: gate("PASS", ["Breakout 10:00"]), gate2: gate("PASS", ["15m ADX rising"]),
      atr: gate("FAIL", ["Move 4.0× ATR → EXHAUSTED"], { atr_status: "EXHAUSTED" }), vix: gate("SKIP"),
      reason: "ATR EXHAUSTED", state: "REJECTED", effective_state: "REJECTED", note: null, entry_price: null, stop_price: null,
      target_price: null, atr_value: null, breakout: null, snapshot: {},
    },
    ...over,
  };
}

test("badge shows a text label, never colour alone", () => {
  render(<Badge s="FAIL" />);
  expect(screen.getByText("FAIL")).toBeInTheDocument();
});

test("pipeline shows every gate, the failing reason and no signal", () => {
  render(<Pipeline r={result()} />);
  expect(screen.getByText("GATE 1")).toBeInTheDocument();
  expect(screen.getByText("EXHAUSTED")).toBeInTheDocument();
  expect(screen.getByText(/Move 4.0× ATR/)).toBeInTheDocument();
  expect(screen.getByText("NO SIGNAL")).toBeInTheDocument();
});

test("pipeline shows the signal when all gates pass", () => {
  render(<Pipeline r={result({ final_result: "SIGNAL", state: "SIGNAL_GENERATED" })} />);
  expect(screen.getByText("CALL BUY")).toBeInTheDocument();
});

test("signal card explains the signal", () => {
  const s: Setup = {
    id: 3, symbol: "NIFTY", direction: "CALL", state: "ACTIVE", breakout_ts: "2026-10-07T04:30:00+00:00", detected_at: "",
    config_version: "1.0.3", breakout: { adx_at: 19.5 }, signal_ts: "2026-10-07T04:40:00+00:00", entry_price: 22500, entry_atr: 20,
    stop_price: 22440, target_price: 22590, signal_context: { gate2: { adx: 22, slope: 1.2 }, atr: { atr_status: "NORMAL", ratio: 1.1 }, vix_filter: { vix: 14.2 }, reason: "CALL BUY: breakout" },
    peak_adx: 21, exit_ts: null, exit_price: null, exit_reason: null, closed_reason: null, trade: null,
  };
  render(<SignalCard s={s} />);
  expect(screen.getByText("CALL BUY")).toBeInTheDocument();
  expect(screen.getByText(/v1.0.3/)).toBeInTheDocument();
  expect(screen.getByText("CALL BUY: breakout")).toBeInTheDocument();
});

test("commentary shows the headline, each gate and the side rule", () => {
  render(<Commentary c={{
    headline: "No setup near, CE side (+DI 24.9 / −DI 16.0).", bias: "CE", outlook: "Setup possible from about 14:35 IST.",
    lines: [{ gate: "5m ADX", status: "FAIL", text: "ADX 22.9, needs ≤ 20 (2.9 to go)." }],
    compression: { candles: 17, at: null, text: "If NIFTY trades sideways, 5m ADX reaches ≤ 20 and holds 6 candles in about 17 candles." },
    rules: [
      { direction: "CALL", option: "CE", move_pts: 17, candles: 3, minutes: 15, signal_in: 20, signal_at: "", after_cutoff: false, di_gap: 3.1, text: "Then a rise of 17 pts in 3 candles (15 min) triggers a CE breakout." },
      { direction: "PUT", option: "PE", move_pts: 50, candles: 3, minutes: 15, signal_in: 20, signal_at: "", after_cutoff: false, di_gap: 3.2, text: "Then a fall of 50 pts in 3 candles (15 min) triggers a PE breakout." },
    ],
  }} />);
  expect(screen.getByText(/No setup near/)).toBeInTheDocument();
  expect(screen.getByText(/needs ≤ 20/)).toBeInTheDocument();
  expect(screen.getByText(/trades sideways/)).toBeInTheDocument();
  expect(screen.getByText(/rise of 17 pts/)).toBeInTheDocument();
  expect(screen.getByText(/fall of 50 pts/)).toBeInTheDocument();
});

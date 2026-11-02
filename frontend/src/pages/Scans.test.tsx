import { render, screen } from "@testing-library/react";
import { vi } from "vitest";
import { api } from "../api/client";
import ScanHistory from "./Scans";

afterEach(() => vi.restoreAllMocks());

test("record-only fills that qualified show as MISSED SIGNAL", async () => {
  vi.spyOn(api, "symbols").mockResolvedValue([{ symbol: "NIFTY", testing: false }]);
  const row = { id: 1, scan_run_id: 9, symbol: "NIFTY", candle_ts: "2026-10-29T04:00:00+00:00", gate1: "PASS", gate2: "PASS", atr_filter: "PASS",
    vix_filter: "PASS", final_result: "NO_SIGNAL", state: "QUALIFIED", direction: "CALL", rejection_reason: "late fill, lifecycle not replayed",
    config_version: "1.0.2", setup_id: null, missed: true };
  vi.spyOn(api, "scanHistory").mockResolvedValue({ total: 1, items: [row as any] });
  render(<ScanHistory />);
  expect(await screen.findByText("MISSED SIGNAL")).toBeInTheDocument();
  expect(screen.getByLabelText(/Missed signals only/)).toBeInTheDocument();
});

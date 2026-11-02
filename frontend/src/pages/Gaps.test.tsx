import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import { api } from "../api/client";
import { resetRoleCache } from "../lib/role";
import Gaps from "./Gaps";

const block = (id: string, type: "LATEST" | "INTERIOR", data: "FULL" | "NONE" = "FULL") =>
  ({ id, date: "2026-11-02", start: id, end: id, candles: 6, type, data, selectable: data === "FULL" });

beforeEach(() => {
  resetRoleCache();
  vi.spyOn(api, "whoami").mockResolvedValue({ role: "admin" });
  vi.spyOn(api, "gaps").mockResolvedValue({
    from: "2026-10-27", to: "2026-11-02", total_missing: 18, no_data_days: [],
    days: [{ date: "2026-11-02", expected: 75, missing: 18 }],
    blocks: [block("2026-11-02T04:30:00+00:00", "INTERIOR"), block("2026-11-02T06:00:00+00:00", "INTERIOR", "NONE"), block("2026-11-02T09:30:00+00:00", "LATEST")],
  });
});
afterEach(() => vi.restoreAllMocks());

test("lists blocks and fills the selected ones after confirmation", async () => {
  const fill = vi.spyOn(api, "fillGaps").mockResolvedValue({ results: [{ id: "2026-11-02T09:30:00+00:00", status: "FILLED", mode: "FULL", scans: 6, signals: 1 }] });
  vi.spyOn(window, "confirm").mockReturnValue(true);
  render(<Gaps />);
  expect(await screen.findByText("18")).toBeInTheDocument();
  expect(screen.getByText("Latest · full fill")).toBeInTheDocument();
  expect(screen.getAllByText("Interior · record-only")).toHaveLength(2);
  const boxes = screen.getAllByRole("checkbox", { name: /Select/ });
  await vi.waitFor(() => expect(boxes[2]).not.toBeDisabled());
  expect(boxes[1]).toBeDisabled(); // no data
  fireEvent.click(boxes[2]);
  fireEvent.click(screen.getByRole("button", { name: "Fill selected (1)" }));
  expect(fill).toHaveBeenCalledWith(["2026-11-02T09:30:00+00:00"]);
  expect(await screen.findByText(/6 scans written \(full fill, 1 signal/)).toBeInTheDocument();
});

import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import { api } from "../api/client";
import { PerformanceOverview } from "./Performance";

afterEach(() => vi.restoreAllMocks());

test("date range filters every performance call", async () => {
  const sum = vi.spyOn(api, "summary").mockResolvedValue({ trading: { trades: 0 }, signals: {}, funnel: {} } as any);
  const eq = vi.spyOn(api, "equity").mockResolvedValue([]);
  const an = vi.spyOn(api, "analytics").mockResolvedValue({});
  render(<PerformanceOverview />);
  fireEvent.change(screen.getByLabelText("From"), { target: { value: "2026-10-01" } });
  fireEvent.change(screen.getByLabelText("To"), { target: { value: "2026-10-31" } });
  const r = { date_from: "2026-10-01", date_to: "2026-10-31" };
  await vi.waitFor(() => expect(sum).toHaveBeenLastCalledWith(undefined, false, r));
  expect(eq).toHaveBeenLastCalledWith(false, r);
  expect(an).toHaveBeenLastCalledWith(false, r);
  fireEvent.click(await screen.findByRole("button", { name: "All time" }));
  await vi.waitFor(() => expect(sum).toHaveBeenLastCalledWith(undefined, false, {}));
});

import { render, screen } from "@testing-library/react";
import { vi } from "vitest";
import type { Health } from "../api/client";
import { api } from "../api/client";
import { resetRoleCache } from "../lib/role";
import { Header } from "./Layout";

const health = {
  now: "", market_open: true, provider: "kite", connected: false, session_date: null, feeds: [],
  auto_scan: { enabled: true, runtime_enabled: true, next_run: null }, last_scan: null,
} as unknown as Health;

beforeEach(() => {
  resetRoleCache();
  vi.spyOn(api, "activeSignals").mockResolvedValue({ active: [], pending: [], exited_today: [] });
});
afterEach(() => vi.restoreAllMocks());

test("viewer sees a View only badge and no admin controls", async () => {
  vi.spyOn(api, "whoami").mockResolvedValue({ role: "viewer" });
  render(<Header health={health} reload={() => {}} />);
  expect(await screen.findByText("View only")).toBeInTheDocument();
  expect(screen.queryByText("CONNECT")).toBeNull();
  expect(screen.queryByText("SCAN NOW")).toBeNull();
  expect(screen.queryByText("Auto Scan")).toBeNull();
});

test("admin (the Mac itself) gets CONNECT, SCAN NOW and the auto-scan toggle", async () => {
  vi.spyOn(api, "whoami").mockResolvedValue({ role: "admin" });
  render(<Header health={health} reload={() => {}} />);
  expect(await screen.findByText("CONNECT")).toBeInTheDocument();
  expect(screen.getByText("SCAN NOW")).toBeInTheDocument();
  expect(screen.getByText("Auto Scan")).toBeInTheDocument();
  expect(screen.queryByText("View only")).toBeNull();
});

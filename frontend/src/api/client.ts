// Relative by default: the backend serves the UI (and Vite proxies /api in dev), so friends' browsers hit the Mac, not themselves.
const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";

export class ApiError extends Error {
  constructor(public status: number, message: string, public detail?: unknown) {
    super(message);
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: { "Content-Type": "application/json" }, ...init });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const d = body?.detail;
    const msg = typeof d === "string" ? d : Array.isArray(d) ? d.map((x) => `${x.loc ?? ""} ${x.msg ?? ""}`.trim()).join("; ") : res.statusText;
    throw new ApiError(res.status, msg, d);
  }
  return body as T;
}

const qs = (p: Record<string, string | number | undefined | null>) => {
  const s = new URLSearchParams();
  Object.entries(p).forEach(([k, v]) => v !== undefined && v !== null && v !== "" && s.set(k, String(v)));
  const t = s.toString();
  return t ? `?${t}` : "";
};

export type GateStatus = "PASS" | "FAIL" | "WAIT" | "SKIP";
export interface Gate { status: GateStatus; reasons: string[]; metrics: Record<string, any> }
export interface CommentaryLine { gate: string; status: GateStatus; text: string; earliest?: string | null; would_pass?: boolean }
export interface CommentaryRule { direction: "CALL" | "PUT"; option: "CE" | "PE"; move_pts: number; candles: number; minutes: number; signal_in: number; signal_at: string; after_cutoff: boolean; di_gap: number; text: string }
export interface Commentary { headline: string; bias: "CE" | "PE" | null; lines: CommentaryLine[]; compression: { candles: number | null; at: string | null; text: string } | null; rules: CommentaryRule[]; outlook: string | null; candle_close?: string }
export interface ScanResult {
  id: number; scan_run_id: number; symbol: string; candle_ts: string | null; created_at: string | null;
  adx5: number | null; pdi5: number | null; mdi5: number | null; adx15: number | null; pdi15: number | null; mdi15: number | null;
  atr: number | null; atr_status: string | null; vix: number | null; vix_change_pct: number | null;
  gate1: GateStatus; gate2: GateStatus; atr_filter: GateStatus; vix_filter: GateStatus;
  final_result: "SIGNAL" | "NO_SIGNAL"; state: string; direction: "CALL" | "PUT" | null; rejection_reason: string | null;
  config_version: string; setup_id: number | null; missed?: boolean; replayed?: { setup_id: number; state: string; traded: boolean }; reason?: string; entry_price?: number | null;
  gates?: Record<string, { status: GateStatus; reasons: string[] }>;
  commentary?: Commentary | null;
  details?: {
    gate1: Gate; gate2: Gate; atr: Gate; vix: Gate; reason: string; state: string; effective_state: string; note: string | null;
    entry_price: number | null; stop_price: number | null; target_price: number | null; atr_value: number | null;
    breakout: Record<string, any> | null; snapshot: Record<string, any>; commentary?: Commentary | null;
  };
}
export interface Candle { ts: string; open: number; high: number; low: number; close: number; adx: number | null; pdi: number | null; mdi: number | null; atr: number | null }
export interface ChainSide { ltp: number | null; chg_pct: number | null; oi: number | null; oi_chg_pct: number | null; iv: number | null; delta: number | null; theta: number | null; gamma: number | null; vega: number | null }
export interface OptionChain {
  symbol: string; expiry: string; spot: number; atm: number | null; days_to_expiry: number; as_of: string;
  rows: { strike: number; ce: ChainSide | null; pe: ChainSide | null }[];
  signal: { direction: "CALL" | "PUT"; option: "CE" | "PE"; strike: number; target_delta: number } | null;
}
export interface GapBlock { id: string; date: string; start: string; end: string; candles: number; type: "LATEST" | "INTERIOR"; data: "FULL" | "PARTIAL" | "NONE"; selectable: boolean }
export interface Gaps { from: string; to: string; total_missing: number; days: { date: string; expected: number; missing: number }[]; no_data_days: string[]; blocks: GapBlock[]; replay_pending?: number; candles_from?: string | null }
export interface GapFillResult { id: string; status: "FILLED" | "SKIPPED" | "NO_DATA"; mode?: "FULL" | "REPLAY" | "RECORD_ONLY"; scans?: number; signals?: number; blocked?: number; missed?: number; message?: string }
export interface HistoryResult { symbol: string; status: "LOADED" | "UP_TO_DATE" | "SKIPPED"; inserted_5m?: number; from?: string; message?: string }
export interface PerfRange { date_from?: string; date_to?: string }
export interface ReplayResult { breakouts: number; signals: number; blocked: number; skipped: number }
export interface ScanRun { id: number; trigger: string; candle_ts: string | null; started_at: string; finished_at: string | null; status: string; config_version: string; summary: any }
export interface Trade {
  id: number; setup_id: number; symbol: string; direction: string; status: string; entry_ts: string; entry_price: number;
  exit_ts: string | null; exit_price: number | null; exit_reason: string | null; risk_points: number | null; pnl_points: number | null;
  pnl_pct: number | null; r_multiple: number | null; holding_minutes: number | null; config_version: string;
  breakout_adx_change: number | null; adx5_entry: number | null; adx15_entry: number | null; atr_status: string | null; vix_entry: number | null;
}
export interface SignalEvent { id: number; event: string; candle_ts: string | null; price: number | null; note: string | null; data: any }
export interface Tracking {
  ts: string; price: number; pnl_points: number; r: number | null; stop: number | null; initial_stop: number | null; stop_moved: boolean;
  target: number | null; to_stop: number | null; to_target: number | null; held: number; candles_left: number; adx: number | null;
  peak_adx: number | null; adx_declines: number; verdict: "HOLD" | "TRAIL" | "WATCH"; reasons: string[];
}
export interface Setup {
  id: number; symbol: string; direction: "CALL" | "PUT"; state: string; breakout_ts: string; detected_at: string; config_version: string;
  breakout: Record<string, any>; signal_ts: string | null; entry_price: number | null; entry_atr: number | null; stop_price: number | null;
  target_price: number | null; signal_context: Record<string, any> | null; peak_adx: number | null; exit_ts: string | null;
  exit_price: number | null; exit_reason: string | null; closed_reason: string | null; trade: Trade | null; testing?: boolean; late?: boolean; events?: SignalEvent[]; scans?: ScanResult[]; tracking?: Tracking | null;
}
export interface Feed { feed: string; symbol: string; timeframe: string; status: string; reason: string | null; last_candle: string | null; expected_candle: string; candles: number; last_update: string | null; last_sync: string | null; last_error: string | null; market_open: boolean }
export interface Health {
  now: string; market_open: boolean; provider: string; connected: boolean; session_date?: string | null; feeds: Feed[];
  auto_scan: { enabled: boolean; runtime_enabled: boolean; next_run: string; last_run: string | null; last_result: string | null; last_error: string | null };
  last_scan: ScanRun | null;
}
export interface ParamMeta { key: string; title: string; description: string; type: string; default: any; min: number | null; max: number | null; multiple_of: number | null; options: string[] | null; pattern: string | null }
export interface ConfigResp { version: string; id: number; created_at: string; note: string | null; params: Record<string, Record<string, any>>; defaults: Record<string, Record<string, any>>; schema: { key: string; title: string; params: ParamMeta[] }[] }
export interface TradeStats { trades: number; wins?: number; losses?: number; win_rate?: number; avg_gain_points?: number; avg_loss_points?: number; risk_reward?: number | null; expectancy_points?: number; expectancy_r?: number | null; net_points?: number; net_pct?: number; net_r?: number | null; profit_factor?: number | null; max_drawdown_points?: number; avg_holding_minutes?: number }
export interface Summary {
  signals: { total_scans: number; total_setups: number; total_signals: number; call_signals: number; put_signals: number; rejected_or_expired_setups: number; open_trades: number };
  trading: TradeStats;
  funnel: { evaluations: number; gate1_pass: number; gate2_pass: number; atr_pass: number; vix_pass: number; signals: number; rejection_rate: Record<string, number | null> };
}

export interface AcctAgg { trades: number; wins: number; win_rate: number | null; net: number; avg: number | null; avg_win: number | null; avg_loss: number | null; profit_factor: number | null }
export type AcctBucket = AcctAgg & { bucket: string };
export interface AcctTrade {
  tradingsymbol: string; underlying: string; instrument: string; side: "LONG" | "SHORT"; view: "CALL" | "PUT"; qty: number;
  entry_ts: string; exit_ts: string | null; status: "OPEN" | "CLOSED"; avg_entry: number; avg_exit: number | null; hold_min: number | null;
  gross: number | null; charges: number; brokerage: number; stt: number; net: number | null; orders: number; fills: number; adds: number;
  day: string; day_seq: number; signal_id: number | null; on_signal: boolean; signal_delay_min: number | null; gap_prev_min: number | null;
  after: "WIN" | "LOSS" | null; gap_after_exit_min: number | null; flags: string[];
}
export interface AcctDay { day: string; trades: number; net: number; peak: number; burst15: number; orders: { placed: number; complete: number; cancelled: number; rejected: number; modified: number | null } | null }
export interface AcctStats {
  totals: AcctAgg & { open: number; days: number; green_days: number; first: string | null; last: string | null };
  stop_after: { n: number; net: number; vs_actual: number }[];
  gap_prev: AcctBucket[]; adds: AcctBucket[]; hold: AcctBucket[];
  gave_back: { days: number; total: number; green_to_red: number; of_days: number };
  charges: { gross: number; charges: number; net: number; brokerage: number; stt: number; pct_of_gross: number | null; per_trade: number | null };
  system: { signals: number; net_r: number; win_rate: number | null; taken: number; on_signal: AcctAgg; off_signal: AcctAgg };
  tilt: { after_loss_min: number | null; after_loss_n: number; after_win_min: number | null; after_win_n: number };
  after_two_losses: { next: AcctAgg; overall_win_rate: number | null };
  scalp: AcctBucket[];
  heatmap: { weekday: number; hour: number; trades: number; net: number }[];
  by_trade_number: AcctBucket[];
  by_day_count: { bucket: string; days: number; net: number; avg_day: number; green_pct: number }[];
  reentry_after_loss: AcctBucket[]; reentry_after_win: AcctAgg;
  flags: Record<string, AcctAgg>;
  frequency: { days: number; trades_per_day: number | null; max_per_day: number | null; by_hour: { hour: number; trades: number }[]; max_burst15: number | null };
  orders: { placed: number; complete: number; cancelled: number; rejected: number; modified: number | null; days: number; per_day: number | null; since: string | null; shortest_gap_sec: number | null; median_gap_sec: number | null; per_round_trip: number | null; by_hour: { hour: number; orders: number }[] };
  days: AcctDay[];
  equity: { ts: string; cum: number; cum_on_signal: number }[];
}
export interface AcctFilter { symbol?: string; date_from?: string; date_to?: string }
export interface AcctStatus { fills: number; first_fill: string | null; last_fill: string | null; orders: number; last_sync: { at: string | null; trades_added: number; orders: number; error: string | null } }

export const api = {
  health: () => req<Health>("/api/system/health"),
  whoami: () => req<{ role: "admin" | "viewer" }>("/api/system/whoami"),
  connect: () => req<{ provider: string; connected: boolean; login_url: string | null; message?: string }>("/api/system/connect"),
  setAutoScan: (enabled: boolean) => req("/api/system/autoscan", { method: "POST", body: JSON.stringify({ enabled }) }),
  events: (category?: string) => req<{ id: number; ts: string; level: string; category: string; message: string; data: any }[]>(`/api/system/events${qs({ category, limit: 200 })}`),
  scanNow: () => req<{ run: ScanRun; results: ScanResult[] }>("/api/scans/run", { method: "POST" }),
  latest: () => req<{ run: ScanRun | null; symbols: Record<string, ScanResult | null> }>("/api/scans/latest"),
  gaps: (from?: string, to?: string) => req<Gaps>(`/api/scans/gaps${qs({ from, to })}`),
  fillGaps: (blocks: string[]) => req<{ results: GapFillResult[] }>("/api/scans/gaps/fill", { method: "POST", body: JSON.stringify({ blocks }) }),
  loadHistory: (from: string) => req<{ results: HistoryResult[]; candles_from: string | null }>("/api/market/history", { method: "POST", body: JSON.stringify({ from }) }),
  replayFilled: () => req<ReplayResult>("/api/scans/gaps/replay", { method: "POST" }),
  scanHistory: (p: Record<string, string | number | undefined>) => req<{ total: number; items: ScanResult[] }>(`/api/scans/history${qs(p)}`),
  scanResult: (id: number) => req<ScanResult>(`/api/scans/results/${id}`),
  activeSignals: () => req<{ active: Setup[]; pending: Setup[]; exited_today: Setup[]; rejected_today?: Setup[] }>("/api/signals/active"),
  signalHistory: (p: Record<string, string | number | undefined>) => req<{ total: number; items: Setup[] }>(`/api/signals/history${qs(p)}`),
  signal: (id: number) => req<Setup>(`/api/signals/${id}`),
  symbols: () => req<{ symbol: string; testing: boolean }[]>("/api/market/symbols"),
  candles: (symbol: string, timeframe = "5m", limit = 120) => req<Candle[]>(`/api/market/candles${qs({ symbol, timeframe, limit })}`),
  chain: (symbol: string, strikes = 10) => req<OptionChain>(`/api/options/chain${qs({ symbol, strikes })}`),
  config: () => req<ConfigResp>("/api/config"),
  saveConfig: (params: ConfigResp["params"], note?: string) => req<{ version: string; changed: { group: string; key: string; old: any; new: any }[]; message?: string }>("/api/config", { method: "PUT", body: JSON.stringify({ params, note }) }),
  resetConfig: () => req<{ version: string }>("/api/config/reset", { method: "POST" }),
  configVersions: () => req<{ id: number; version: string; is_active: boolean; note: string | null; created_at: string }[]>("/api/config/versions"),
  summary: (symbol?: string, exclude_late?: boolean, r: PerfRange = {}) => req<Summary>(`/api/performance/summary${qs({ symbol, exclude_late: exclude_late ? "true" : undefined, ...r })}`),
  trades: (p: Record<string, string | undefined> = {}) => req<Trade[]>(`/api/performance/trades${qs(p)}`),
  equity: (exclude_late?: boolean, r: PerfRange = {}) => req<{ ts: string; symbol: string; pnl_points: number; cum_points: number; r: number | null; cum_r: number }[]>(`/api/performance/equity${qs({ exclude_late: exclude_late ? "true" : undefined, ...r })}`),
  acctStatus: () => req<AcctStatus>("/api/account/status"),
  acctStats: (f: AcctFilter = {}) => req<AcctStats>(`/api/account/stats${qs({ ...f })}`),
  acctTrades: (f: AcctFilter = {}) => req<AcctTrade[]>(`/api/account/trades${qs({ ...f })}`),
  acctImport: (csv: string) => req<{ added: number; skipped: number; errors: string[]; error_count: number }>("/api/account/import", { method: "POST", body: csv, headers: { "Content-Type": "text/csv" } }),
  acctSync: () => req<{ trades_added: number; orders: number; skipped?: string }>("/api/account/sync", { method: "POST" }),
  analytics: (exclude_late?: boolean, r: PerfRange = {}) => req<Record<string, any[]>>(`/api/performance/analytics${qs({ exclude_late: exclude_late ? "true" : undefined, ...r })}`),
};

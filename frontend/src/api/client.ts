const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

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
  config_version: string; setup_id: number | null; reason?: string; entry_price?: number | null;
  gates?: Record<string, { status: GateStatus; reasons: string[] }>;
  commentary?: Commentary | null;
  details?: {
    gate1: Gate; gate2: Gate; atr: Gate; vix: Gate; reason: string; state: string; effective_state: string; note: string | null;
    entry_price: number | null; stop_price: number | null; target_price: number | null; atr_value: number | null;
    breakout: Record<string, any> | null; snapshot: Record<string, any>; commentary?: Commentary | null;
  };
}
export interface ScanRun { id: number; trigger: string; candle_ts: string | null; started_at: string; finished_at: string | null; status: string; config_version: string; summary: any }
export interface Trade {
  id: number; setup_id: number; symbol: string; direction: string; status: string; entry_ts: string; entry_price: number;
  exit_ts: string | null; exit_price: number | null; exit_reason: string | null; risk_points: number | null; pnl_points: number | null;
  pnl_pct: number | null; r_multiple: number | null; holding_minutes: number | null; config_version: string;
  breakout_adx_change: number | null; adx5_entry: number | null; adx15_entry: number | null; atr_status: string | null; vix_entry: number | null;
}
export interface SignalEvent { id: number; event: string; candle_ts: string | null; price: number | null; note: string | null; data: any }
export interface Setup {
  id: number; symbol: string; direction: "CALL" | "PUT"; state: string; breakout_ts: string; detected_at: string; config_version: string;
  breakout: Record<string, any>; signal_ts: string | null; entry_price: number | null; entry_atr: number | null; stop_price: number | null;
  target_price: number | null; signal_context: Record<string, any> | null; peak_adx: number | null; exit_ts: string | null;
  exit_price: number | null; exit_reason: string | null; closed_reason: string | null; trade: Trade | null; events?: SignalEvent[]; scans?: ScanResult[];
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

export const api = {
  health: () => req<Health>("/api/system/health"),
  connect: () => req<{ provider: string; connected: boolean; login_url: string | null; message?: string }>("/api/system/connect"),
  setAutoScan: (enabled: boolean) => req("/api/system/autoscan", { method: "POST", body: JSON.stringify({ enabled }) }),
  events: (category?: string) => req<{ id: number; ts: string; level: string; category: string; message: string; data: any }[]>(`/api/system/events${qs({ category, limit: 200 })}`),
  scanNow: () => req<{ run: ScanRun; results: ScanResult[] }>("/api/scans/run", { method: "POST" }),
  latest: () => req<{ run: ScanRun | null; symbols: Record<string, ScanResult | null> }>("/api/scans/latest"),
  scanHistory: (p: Record<string, string | number | undefined>) => req<{ total: number; items: ScanResult[] }>(`/api/scans/history${qs(p)}`),
  scanResult: (id: number) => req<ScanResult>(`/api/scans/results/${id}`),
  activeSignals: () => req<{ active: Setup[]; pending: Setup[] }>("/api/signals/active"),
  signalHistory: (p: Record<string, string | number | undefined>) => req<{ total: number; items: Setup[] }>(`/api/signals/history${qs(p)}`),
  signal: (id: number) => req<Setup>(`/api/signals/${id}`),
  candles: (symbol: string, timeframe = "5m", limit = 120) => req<{ ts: string; close: number; adx: number | null; pdi: number | null; mdi: number | null }[]>(`/api/market/candles${qs({ symbol, timeframe, limit })}`),
  config: () => req<ConfigResp>("/api/config"),
  saveConfig: (params: ConfigResp["params"], note?: string) => req<{ version: string; changed: { group: string; key: string; old: any; new: any }[]; message?: string }>("/api/config", { method: "PUT", body: JSON.stringify({ params, note }) }),
  resetConfig: () => req<{ version: string }>("/api/config/reset", { method: "POST" }),
  configVersions: () => req<{ id: number; version: string; is_active: boolean; note: string | null; created_at: string }[]>("/api/config/versions"),
  summary: (symbol?: string) => req<Summary>(`/api/performance/summary${qs({ symbol })}`),
  trades: (p: Record<string, string | undefined> = {}) => req<Trade[]>(`/api/performance/trades${qs(p)}`),
  equity: () => req<{ ts: string; symbol: string; pnl_points: number; cum_points: number; r: number | null; cum_r: number }[]>("/api/performance/equity"),
  analytics: () => req<Record<string, any[]>>("/api/performance/analytics"),
};

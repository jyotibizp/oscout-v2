const IST = "Asia/Kolkata";

export const timeIST = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleTimeString("en-IN", { timeZone: IST, hour: "2-digit", minute: "2-digit", hour12: false }) : "—";

export const dateTimeIST = (iso?: string | null) =>
  iso
    ? new Date(iso).toLocaleString("en-IN", { timeZone: IST, day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false })
    : "—";

export const dateIST = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleDateString("en-IN", { timeZone: IST, day: "2-digit", month: "short", year: "numeric" }) : "—";

export const n = (v?: number | null, d = 1) => (v === null || v === undefined || Number.isNaN(v) ? "—" : v.toFixed(d));
export const signed = (v?: number | null, d = 1) => (v === null || v === undefined ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(d)}`);
export const minutes = (m?: number | null) => (m === null || m === undefined ? "—" : m >= 60 ? `${Math.floor(m / 60)}h ${Math.round(m % 60)}m` : `${Math.round(m)}m`);
export const relative = (iso?: string | null) => {
  if (!iso) return "—";
  const s = Math.round((new Date(iso).getTime() - Date.now()) / 1000);
  const a = Math.abs(s);
  const txt = a < 60 ? `${a}s` : a < 3600 ? `${Math.round(a / 60)}m` : `${Math.round(a / 3600)}h`;
  return s >= 0 ? `in ${txt}` : `${txt} ago`;
};

import { useEffect, useState } from "react";
import { api, ConfigResp, ParamMeta } from "../api/client";
import { ErrorNote, PageHeader } from "../components/ui";
import { dateTimeIST } from "../lib/format";
import { useApi } from "../lib/hooks";

type Params = ConfigResp["params"];

function validate(p: ParamMeta, v: any): string | null {
  if (p.type === "integer" || p.type === "number") {
    if (v === "" || v === null || Number.isNaN(Number(v))) return "Enter a number";
    const x = Number(v);
    if (p.type === "integer" && !Number.isInteger(x)) return "Whole number";
    if (p.min !== null && x < p.min) return `Min ${p.min}`;
    if (p.max !== null && x > p.max) return `Max ${p.max}`;
    if (p.multiple_of && x % p.multiple_of !== 0) return `Multiple of ${p.multiple_of}`;
  }
  if (p.pattern && typeof v === "string" && !new RegExp(p.pattern).test(v)) return "HH:MM";
  return null;
}

function Input({ p, value, onChange }: { p: ParamMeta; value: any; onChange: (v: any) => void }) {
  if (p.type === "boolean")
    return (
      <select className="input w-28" value={String(value)} onChange={(e) => onChange(e.target.value === "true")}>
        <option value="true">On</option><option value="false">Off</option>
      </select>
    );
  if (p.options)
    return <select className="input w-28" value={value} onChange={(e) => onChange(e.target.value)}>{p.options.map((o) => <option key={o}>{o}</option>)}</select>;
  if (p.type === "integer" || p.type === "number")
    return <input className="input w-28 num text-right" type="number" step={p.type === "integer" ? 1 : "any"} value={value}
      onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))} />;
  return <input className="input w-28 num" value={value} onChange={(e) => onChange(e.target.value)} />;
}

export default function Strategy() {
  const cfg = useApi(api.config, []);
  const versions = useApi(api.configVersions, []);
  const [draft, setDraft] = useState<Params | null>(null);
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { if (cfg.data) setDraft(structuredClone(cfg.data.params)); }, [cfg.data]);
  if (!cfg.data || !draft) return <div><PageHeader title="ADX Configuration" /><ErrorNote error={cfg.error} /></div>;

  const errors: Record<string, string> = {};
  cfg.data.schema.forEach((g) => g.params.forEach((p) => { const e = validate(p, draft[g.key][p.key]); if (e) errors[`${g.key}.${p.key}`] = e; }));
  const dirty = JSON.stringify(draft) !== JSON.stringify(cfg.data.params);
  const save = async () => {
    setErr(null); setMsg(null);
    try {
      const r = await api.saveConfig(draft, note || undefined);
      setMsg(r.changed.length ? `Saved as ADX Strategy v${r.version} (${r.changed.length} change${r.changed.length > 1 ? "s" : ""})` : "No changes");
      setNote(""); cfg.reload(); versions.reload();
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
  };
  const reset = async () => {
    if (!confirm("Reset every parameter to its default? This saves a new version.")) return;
    const r = await api.resetConfig();
    setMsg(`Reset to defaults as v${r.version}`); cfg.reload(); versions.reload();
  };

  return (
    <div>
      <PageHeader title="ADX Configuration" sub={`Active: ADX Strategy v${cfg.data.version} · saved ${dateTimeIST(cfg.data.created_at)}${cfg.data.note ? ` · ${cfg.data.note}` : ""}`}
        right={
          <div className="flex items-center gap-2">
            <input className="input w-56" placeholder="Change note (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
            <button className="btn" onClick={reset}>RESET DEFAULTS</button>
            <button className="btn-primary" disabled={!dirty || Object.keys(errors).length > 0} onClick={save}>SAVE CONFIGURATION</button>
          </div>
        } />
      {msg && <div className="card border-good/40 px-4 py-2 mb-4 text-sm text-good">{msg}</div>}
      <ErrorNote error={err} />
      <div className="grid gap-4 2xl:grid-cols-2">
        {cfg.data.schema.map((g) => (
          <section key={g.key} className="card">
            <div className="px-4 py-2.5 border-b border-line text-xs font-semibold tracking-widest text-ink-soft">{g.title}</div>
            <table className="w-full">
              <thead><tr><th className="th">Parameter</th><th className="th">Value</th><th className="th">Default</th></tr></thead>
              <tbody>
                {g.params.map((p) => {
                  const k = `${g.key}.${p.key}`;
                  const v = draft[g.key][p.key];
                  const changed = v !== cfg.data!.params[g.key][p.key];
                  return (
                    <tr key={p.key} className="align-top">
                      <td className="td whitespace-normal">
                        <div className={`text-sm ${changed ? "text-accent" : "text-ink"}`}>{p.title}</div>
                        <div className="text-xs text-ink-faint max-w-md">{p.description}{p.min !== null && p.max !== null ? ` (${p.min}–${p.max})` : ""}</div>
                      </td>
                      <td className="td">
                        <Input p={p} value={v} onChange={(nv) => setDraft({ ...draft, [g.key]: { ...draft[g.key], [p.key]: nv } })} />
                        {errors[k] && <div className="text-xs text-bad mt-1">{errors[k]}</div>}
                      </td>
                      <td className="td num text-ink-faint text-xs">{String(p.default)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </section>
        ))}
      </div>
      <section className="card mt-6 overflow-x-auto">
        <div className="px-4 py-2.5 border-b border-line text-xs font-semibold tracking-widest text-ink-soft">VERSION HISTORY</div>
        <table className="w-full">
          <thead><tr>{["Version", "Saved", "Note", ""].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
          <tbody>{(versions.data ?? []).map((v) => (
            <tr key={v.id}><td className="td num">v{v.version}</td><td className="td num">{dateTimeIST(v.created_at)}</td><td className="td text-ink-soft">{v.note}</td>
              <td className="td text-xs">{v.is_active ? <span className="text-accent">ACTIVE</span> : ""}</td></tr>))}</tbody>
        </table>
      </section>
    </div>
  );
}

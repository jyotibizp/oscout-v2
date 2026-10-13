import { useEffect, useRef, useState } from "react";

const MUTE_KEY = "oscout.chimeMuted";

/** Ids in `curr` not seen before. `null` prev = first load, which never chimes. */
export function newIds(prev: Set<number> | null, curr: number[]): number[] {
  return prev ? curr.filter((id) => !prev.has(id)) : [];
}

let ctx: AudioContext | null = null;
function audio(): AudioContext | null {
  try {
    ctx ??= new AudioContext();
    if (ctx.state === "suspended") void ctx.resume();
    return ctx;
  } catch {
    return null;
  }
}

/** Two-note rising chime via Web Audio (no asset file). */
export function playChime() {
  const a = audio();
  if (!a) return;
  [880, 1320].forEach((freq, i) => {
    const t = a.currentTime + i * 0.18;
    const osc = a.createOscillator();
    const gain = a.createGain();
    osc.type = "sine";
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0.0001, t);
    gain.gain.exponentialRampToValueAtTime(0.3, t + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.5);
    osc.connect(gain).connect(a.destination);
    osc.start(t);
    osc.stop(t + 0.55);
  });
}

/** Chime whenever a new active signal id appears. Mute state persists per browser. */
export function useSignalChime(activeIds: number[] | undefined) {
  const [muted, setMutedState] = useState(() => {
    try { return localStorage.getItem(MUTE_KEY) === "1"; } catch { return false; }
  });
  const seen = useRef<Set<number> | null>(null);

  // Browsers only allow audio after a user gesture: unlock on the first click anywhere.
  useEffect(() => {
    const unlock = () => audio();
    document.addEventListener("pointerdown", unlock, { once: true });
    return () => document.removeEventListener("pointerdown", unlock);
  }, []);

  useEffect(() => {
    if (!activeIds) return;
    const fresh = newIds(seen.current, activeIds);
    seen.current = new Set([...(seen.current ?? []), ...activeIds]);
    if (fresh.length && !muted) playChime();
  }, [activeIds?.join(","), muted]); // eslint-disable-line react-hooks/exhaustive-deps

  const setMuted = (v: boolean) => {
    setMutedState(v);
    try { localStorage.setItem(MUTE_KEY, v ? "1" : "0"); } catch { /* ignore */ }
    if (!v) playChime(); // audible confirmation when turning sound on
  };
  return { muted, setMuted };
}

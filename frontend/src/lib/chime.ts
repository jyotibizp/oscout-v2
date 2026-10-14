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

const NOTES = { signal: [880, 1175, 1568], exit: [1175, 880, 659] }; // A5-D6-G6 up, reversed down
const NOTE_GAP = 0.13;
const BURST_GAP = 1.5;
const BURSTS = 3; // ~4.5s total

/** Alert chime via Web Audio (no asset file): a bright three-note arpeggio repeated
 *  3x (~4.5s), rising for a new signal, falling for an exit. `bursts` shortens it. */
export function playChime(kind: "signal" | "exit" = "signal", bursts = BURSTS) {
  const a = audio();
  if (!a) return;
  const out = a.createDynamicsCompressor(); // lets peaks run hot without clipping
  out.connect(a.destination);
  for (let b = 0; b < bursts; b++) {
    NOTES[kind].forEach((freq, i) => {
      const t = a.currentTime + b * BURST_GAP + i * NOTE_GAP;
      const last = i === NOTES[kind].length - 1;
      const len = last ? 0.9 : 0.35;
      // triangle body + sine an octave up for a bell-like, cutting tone
      ([["triangle", freq, 0.9], ["sine", freq * 2, 0.35]] as const).forEach(([type, f, peak]) => {
        const osc = a.createOscillator();
        const gain = a.createGain();
        osc.type = type;
        osc.frequency.value = f;
        gain.gain.setValueAtTime(0.0001, t);
        gain.gain.exponentialRampToValueAtTime(peak, t + 0.01);
        gain.gain.exponentialRampToValueAtTime(0.0001, t + len);
        osc.connect(gain).connect(out);
        osc.start(t);
        osc.stop(t + len + 0.05);
      });
    });
  }
}

/** Chime whenever a new active signal (or a new exit) appears. Mute state persists per browser. */
export function useSignalChime(activeIds: number[] | undefined, exitIds: number[] | undefined) {
  const [muted, setMutedState] = useState(() => {
    try { return localStorage.getItem(MUTE_KEY) === "1"; } catch { return false; }
  });
  const seen = useRef<Set<number> | null>(null);
  const seenExits = useRef<Set<number> | null>(null);

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

  useEffect(() => {
    if (!exitIds) return;
    const fresh = newIds(seenExits.current, exitIds);
    seenExits.current = new Set([...(seenExits.current ?? []), ...exitIds]);
    if (fresh.length && !muted) playChime("exit");
  }, [exitIds?.join(","), muted]); // eslint-disable-line react-hooks/exhaustive-deps

  const setMuted = (v: boolean) => {
    setMutedState(v);
    try { localStorage.setItem(MUTE_KEY, v ? "1" : "0"); } catch { /* ignore */ }
    if (!v) playChime("signal", 1); // short audible confirmation when turning sound on
  };
  return { muted, setMuted };
}

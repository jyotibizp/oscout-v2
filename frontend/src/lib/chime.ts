import { useEffect, useRef, useState } from "react";

const MUTE_KEY = "oscout.chimeMuted";

/** Ids in `curr` not seen before. `null` prev = first load, which never chimes. */
export function newIds(prev: Set<number> | null, curr: number[]): number[] {
  return prev ? curr.filter((id) => !prev.has(id)) : [];
}

/** Alert chime: a bright three-note arpeggio repeated 6x (~8.8s), rising for a new
 *  signal, falling for an exit. Pre-rendered WAVs (scripts/gen-chimes.py) because
 *  Safari plays <audio> far more reliably than Web Audio oscillators. */
const players: Partial<Record<"signal" | "exit", HTMLAudioElement>> = {};
function player(kind: "signal" | "exit"): HTMLAudioElement | null {
  try {
    return (players[kind] ??= new Audio(`/chime-${kind}.wav`));
  } catch {
    return null;
  }
}

/** Browsers only allow audio after a user gesture: prime both players silently. */
function unlockAudio() {
  (["signal", "exit"] as const).forEach((k) => {
    const p = player(k);
    if (!p || !p.paused) return;
    p.muted = true;
    // still muted = no real chime started meanwhile, so stop the priming play
    p.play().then(() => { if (p.muted) { p.pause(); p.currentTime = 0; p.muted = false; } }, () => { p.muted = false; });
  });
}

export function playChime(kind: "signal" | "exit" = "signal") {
  const p = player(kind);
  if (!p) return;
  p.muted = false;
  p.currentTime = 0;
  p.play().catch(() => {});
}

/** Chime whenever a new active signal (or a new exit) appears. Mute state persists per browser. */
export function useSignalChime(activeIds: number[] | undefined, exitIds: number[] | undefined) {
  const [muted, setMutedState] = useState(() => {
    try { return localStorage.getItem(MUTE_KEY) === "1"; } catch { return false; }
  });
  const seen = useRef<Set<number> | null>(null);
  const seenExits = useRef<Set<number> | null>(null);

  // Browsers only allow audio after a user gesture: unlock on any click/key until running.
  useEffect(() => {
    const evts = ["click", "keydown", "touchend"] as const;
    const unlock = () => { unlockAudio(); evts.forEach((e) => document.removeEventListener(e, unlock)); };
    evts.forEach((e) => document.addEventListener(e, unlock));
    return () => evts.forEach((e) => document.removeEventListener(e, unlock));
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
    if (!v) playChime(); // full alert on unmute, doubles as a sound test
  };
  return { muted, setMuted };
}

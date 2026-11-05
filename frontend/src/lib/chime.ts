import { useEffect, useRef, useState } from "react";

const MUTE_KEY = "oscout.chimeMuted";
const BASE_TITLE = typeof document !== "undefined" ? document.title : "";

/** Ids in `curr` not seen before. `null` prev = first load, which never chimes. */
export function newIds(prev: Set<number> | null, curr: number[]): number[] {
  return prev ? curr.filter((id) => !prev.has(id)) : [];
}

/** Alert chime: a bright three-note arpeggio repeated 6x (~8.8s), rising for a new
 *  signal, falling for an exit; a short low two-note "uh-oh" (~2.6s) for a rejected breakout. Pre-rendered WAVs (scripts/gen-chimes.py) because
 *  Safari plays <audio> far more reliably than Web Audio oscillators. */
type Kind = "signal" | "exit" | "reject";
const players: Partial<Record<Kind, HTMLAudioElement>> = {};
function player(kind: Kind): HTMLAudioElement | null {
  try {
    return (players[kind] ??= new Audio(`/chime-${kind}.wav`));
  } catch {
    return null;
  }
}

/** Browsers block sound until the page gets a click/key after each load. Prime both
 *  players inside the gesture with a real (unmuted, volume 0) play: Safari only grants
 *  an element sound when it played unmuted in a gesture; a muted play does not count. */
function unlockAudio(): Promise<boolean> {
  return Promise.all((["signal", "exit", "reject"] as const).map((k) => {
    const p = player(k);
    if (!p) return false;
    if (!p.paused) return true;
    p.muted = false;
    p.volume = 0;
    return p.play().then(() => {
      if (p.volume === 0) { p.pause(); p.currentTime = 0; }  // still the priming play, not a real chime
      p.volume = 1;
      return true;
    }, () => { p.volume = 1; return false; });
  })).then((ok) => ok.every(Boolean));
}

/** Resolves false when the browser blocked the sound (no click on the page since it loaded). */
export function playChime(kind: Kind = "signal"): Promise<boolean> {
  const p = player(kind);
  if (!p) return Promise.resolve(false);
  p.muted = false;
  p.volume = 1;
  p.currentTime = 0;
  return p.play().then(() => true, () => false);
}

/** Chime whenever a new active signal, exit or rejected breakout appears. Mute state persists per browser.
 *  `blocked` = sound is on but the browser will not play it until the page is clicked. */
export function useSignalChime(activeIds: number[] | undefined, exitIds: number[] | undefined, rejectIds?: number[]) {
  const [muted, setMutedState] = useState(() => {
    try { return localStorage.getItem(MUTE_KEY) === "1"; } catch { return false; }
  });
  const [unlocked, setUnlocked] = useState(false);
  const [missed, setMissed] = useState(0);  // chimes the browser blocked, flashed in the tab title
  const seen = useRef<Set<number> | null>(null);
  const seenExits = useRef<Set<number> | null>(null);
  const seenRejects = useRef<Set<number> | null>(null);

  // Unlock on click/key; keep listening until a play actually succeeds (a failed try used to stop listening).
  useEffect(() => {
    if (unlocked) return;
    const evts = ["click", "keydown", "touchend"] as const;
    const unlock = () => { unlockAudio().then((ok) => { if (ok) { setUnlocked(true); setMissed(0); } }); };
    evts.forEach((e) => document.addEventListener(e, unlock));
    return () => evts.forEach((e) => document.removeEventListener(e, unlock));
  }, [unlocked]);

  const ring = (kind: Kind) => {
    playChime(kind).then((ok) => {
      if (ok) setUnlocked(true);
      else { setUnlocked(false); setMissed((n) => n + 1); }
    });
  };

  useEffect(() => {
    if (!activeIds) return;
    const fresh = newIds(seen.current, activeIds);
    seen.current = new Set([...(seen.current ?? []), ...activeIds]);
    if (fresh.length && !muted) ring("signal");
  }, [activeIds?.join(","), muted]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!exitIds) return;
    const fresh = newIds(seenExits.current, exitIds);
    seenExits.current = new Set([...(seenExits.current ?? []), ...exitIds]);
    if (fresh.length && !muted) ring("exit");
  }, [exitIds?.join(","), muted]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!rejectIds) return;
    const fresh = newIds(seenRejects.current, rejectIds);
    seenRejects.current = new Set([...(seenRejects.current ?? []), ...rejectIds]);
    if (fresh.length && !muted) ring("reject");
  }, [rejectIds?.join(","), muted]); // eslint-disable-line react-hooks/exhaustive-deps

  // Blocked chime: flash the tab title so a background tab still shows it, until the page is clicked.
  useEffect(() => {
    if (!missed) { document.title = BASE_TITLE; return; }
    let on = false;
    const id = setInterval(() => { on = !on; document.title = on ? "🔔 SIGNAL ALERT" : BASE_TITLE; }, 1000);
    return () => { clearInterval(id); document.title = BASE_TITLE; };
  }, [missed]);

  const setMuted = (v: boolean) => {
    setMutedState(v);
    try { localStorage.setItem(MUTE_KEY, v ? "1" : "0"); } catch { /* ignore */ }
    if (!v) ring("signal"); // full alert on unmute, doubles as a sound test
  };
  return { muted, setMuted, blocked: !muted && !unlocked, missed };
}

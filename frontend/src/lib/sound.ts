import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";

/** Signal alert chime, synthesised with Web Audio (no sound files). CE rises, PE falls. */
let ctx: AudioContext | null = null;

function audio(): AudioContext | null {
  if (typeof window === "undefined" || !(window.AudioContext || (window as any).webkitAudioContext)) return null;
  ctx = ctx ?? new (window.AudioContext || (window as any).webkitAudioContext)();
  return ctx;
}

/** Browsers start audio suspended until the user interacts with the page; call from a click. */
export function unlockAudio() {
  const a = audio();
  if (a && a.state === "suspended") a.resume().catch(() => {});
}

export function chime(direction: "CALL" | "PUT" | string) {
  const a = audio();
  if (!a) return;
  unlockAudio();
  const notes = direction === "PUT" ? [880, 660, 440] : [660, 880, 1100];
  const t0 = a.currentTime + 0.05;
  for (let rep = 0; rep < 2; rep++) {
    notes.forEach((f, i) => {
      const t = t0 + rep * 0.75 + i * 0.18;
      const o = a.createOscillator();
      const g = a.createGain();
      o.type = "sine";
      o.frequency.value = f;
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(0.35, t + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, t + 0.17);
      o.connect(g).connect(a.destination);
      o.start(t);
      o.stop(t + 0.18);
    });
  }
}

const KEY = "oscout.sound";

/** Sound on/off (remembered per browser) and a poller that chimes once for every new signal. */
export function useSignalSound(pollMs = 10000) {
  const [on, setOn] = useState<boolean>(() => {
    try { return localStorage.getItem(KEY) !== "off"; } catch { return true; }
  });
  const seen = useRef<Set<number> | null>(null);  // null until the first poll: signals already open don't chime

  useEffect(() => {
    try { localStorage.setItem(KEY, on ? "on" : "off"); } catch { /* storage blocked: keep in memory */ }
  }, [on]);

  useEffect(() => {  // first click anywhere unlocks audio after a reload
    const h = () => unlockAudio();
    window.addEventListener("pointerdown", h, { once: true });
    return () => window.removeEventListener("pointerdown", h);
  }, []);

  useEffect(() => {
    let alive = true;
    const check = async () => {
      try {
        const { active } = await api.activeSignals();
        if (!alive) return;
        const fresh = active.filter((s) => s.state === "SIGNAL_GENERATED" || s.state === "ACTIVE");
        if (seen.current === null) {
          seen.current = new Set(fresh.map((s) => s.id));
          return;
        }
        for (const s of fresh) {
          if (!seen.current.has(s.id)) {
            seen.current.add(s.id);
            if (on) chime(s.direction);
          }
        }
      } catch { /* backend unreachable: try again next poll */ }
    };
    check();
    const id = setInterval(check, pollMs);  // independent of Auto Refresh, so alerts never stop
    return () => { alive = false; clearInterval(id); };
  }, [on, pollMs]);

  const toggle = (v: boolean) => {
    setOn(v);
    if (v) chime("CALL");  // a click is a user gesture: unlocks audio and confirms it works
  };
  return { on, toggle };
}

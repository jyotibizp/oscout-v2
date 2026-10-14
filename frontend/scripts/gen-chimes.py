"""Render the alert chimes to public/chime-{signal,exit}.wav (run: python3 scripts/gen-chimes.py)."""
import math, struct, wave, pathlib

SR, NOTE_GAP, BURST_GAP, BURSTS = 44100, 0.13, 1.5, 6
NOTES = {"signal": [880, 1175, 1568], "exit": [1175, 880, 659]}

def tri(x):  # triangle wave, period 1
    x %= 1.0
    return 4 * x - 1 if x < 0.5 else 3 - 4 * x

def render(notes):
    total = BURST_GAP * (BURSTS - 1) + NOTE_GAP * 2 + 1.0
    buf = [0.0] * int(total * SR)
    for b in range(BURSTS):
        for i, f in enumerate(notes):
            t0 = b * BURST_GAP + i * NOTE_GAP
            ln = 0.9 if i == len(notes) - 1 else 0.35
            for n in range(int(ln * SR)):
                t = n / SR
                env = min(t / 0.01, 1.0) * math.exp(-t / ln * math.log(1e4))
                buf[int(t0 * SR) + n] += env * (0.9 * tri(f * t) + 0.35 * math.sin(2 * math.pi * 2 * f * t))
    peak = max(abs(x) for x in buf)
    return [x / peak * 0.95 for x in buf]

out = pathlib.Path(__file__).resolve().parent.parent / "public"
for kind, notes in NOTES.items():
    with wave.open(str(out / f"chime-{kind}.wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(x * 32767)) for x in render(notes)))

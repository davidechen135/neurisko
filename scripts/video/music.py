"""Background music for the demo video, synthesised here so there is nothing to license.

An early-80s horror-synth loop (a nod to 1981 and to Halloween): A minor, 96 BPM,
a soft detuned pad, a pulsing bass and a plucked 16th-note arpeggio. Deterministic.

  uv run --no-project --with numpy python scripts/video/music.py out.wav --seconds 180
"""

from __future__ import annotations

import argparse
import wave
from pathlib import Path

import numpy as np

SR = 44100
BPM = 96
BEAT = 60 / BPM
BAR = 4 * BEAT
# Two bars per chord: Am, F, C, E (the major E gives the classic eerie turn back to Am).
CHORDS = [
    (45, [57, 60, 64]),  # A2 | A3 C4 E4
    (41, [57, 60, 65]),  # F2 | A3 C4 F4
    (48, [55, 60, 64]),  # C3 | G3 C4 E4
    (40, [56, 59, 64]),  # E2 | G#3 B3 E4
]
ARP = [0, 1, 2, 1, 0, 2, 1, 2]  # chord-tone order for the 16ths (octave up on odd steps)


def hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def tone(f: float, n: int, harmonics: int, detune: float = 0.0) -> np.ndarray:
    """Soft saw-like tone from a few harmonics (1/k amplitudes), so no filter is needed."""
    t = np.arange(n) / SR
    out = np.zeros(n)
    for k in range(1, harmonics + 1):
        out += np.sin(2 * np.pi * f * (1 + detune) * k * t) / k
    return out


def env_adsr(n: int, a: float, r: float) -> np.ndarray:
    e = np.ones(n)
    na, nr = int(a * SR), int(r * SR)
    e[:na] = np.linspace(0, 1, na)
    e[n - nr:] *= np.linspace(1, 0, nr)
    return e


def render(seconds: float) -> np.ndarray:
    n = int(seconds * SR)
    left, right = np.zeros(n + SR * 4), np.zeros(n + SR * 4)
    t0, i = 0.0, 0
    while t0 < seconds:
        root, notes = CHORDS[i % len(CHORDS)]
        seg = 2 * BAR
        ns = int(seg * SR)
        s = int(t0 * SR)
        # Pad: each note twice, detuned and panned apart, slow swell.
        pad_l, pad_r = np.zeros(ns), np.zeros(ns)
        for m in notes:
            pad_l += tone(hz(m), ns, 6, -0.003)
            pad_r += tone(hz(m), ns, 6, +0.003)
        e = env_adsr(ns, 1.2, 1.0)
        left[s:s + ns] += 0.05 * pad_l * e
        right[s:s + ns] += 0.05 * pad_r * e
        # Bass: 8th-note pulse on the root, short decay.
        step = int(BEAT / 2 * SR)
        for j in range(int(seg / (BEAT / 2))):
            p = s + j * step
            b = tone(hz(root), step, 3) * np.exp(-np.arange(step) / SR * 9)
            b *= 1.0 if j % 2 == 0 else 0.6
            left[p:p + step] += 0.16 * b
            right[p:p + step] += 0.16 * b
        # Arpeggio: 16th-note plucks with a long tail, ping-ponged left/right.
        step = int(BEAT / 4 * SR)
        tail = step * 6
        for j in range(int(seg / (BEAT / 4))):
            p = s + j * step
            m = notes[ARP[j % len(ARP)]] + (12 if j % 2 else 0)
            pl = tone(hz(m), tail, 4) * np.exp(-np.arange(tail) / SR * 7)
            pl[:80] *= np.linspace(0, 1, 80)
            pan = 0.7 if j % 2 else 0.3
            left[p:p + tail] += 0.045 * pl * (1 - pan)
            right[p:p + tail] += 0.045 * pl * pan
        t0 += seg
        i += 1
    # Cheap echo for space (dotted 8th, two repeats).
    d = int(BEAT * 0.75 * SR)
    for g in (0.35, 0.15):
        left[d:] += g * right[:-d].copy()
        right[d:] += g * left[:-d].copy()
        d *= 2
    stereo = np.stack([left[:n], right[:n]], axis=1)
    fade = env_adsr(n, 3.0, 4.0)[:, None]
    stereo *= fade
    return stereo / np.max(np.abs(stereo)) * 0.8


def write(path: Path, seconds: float) -> Path:
    pcm = (render(seconds) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--seconds", type=float, default=60)
    args = ap.parse_args()
    print(write(Path(args.out), args.seconds))

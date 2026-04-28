"""Generate a 3-second test WAV (440Hz tone + brief silence) for replay testing."""

from __future__ import annotations

import argparse

import numpy as np
import soundfile as sf


def generate(path: str, sample_rate: int = 8000, duration_s: float = 3.0) -> None:
    n = int(sample_rate * duration_s)
    t = np.linspace(0, duration_s, n, endpoint=False)
    tone = (np.sin(2 * np.pi * 440 * t) * 16000).astype(np.int16)
    silence_n = sample_rate // 2
    silence = np.zeros(silence_n, dtype=np.int16)
    audio = np.concatenate([silence, tone, silence])
    sf.write(path, audio, sample_rate, subtype="PCM_16")
    print(f"wrote {len(audio)} samples ({len(audio) / sample_rate:.1f}s) to {path}")
#----------#


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="/tmp/test_input.wav")
    parser.add_argument("--rate", type=int, default=8000)
    parser.add_argument("--duration", type=float, default=3.0)
    args = parser.parse_args()
    generate(args.output, args.rate, args.duration)
#----------#


if __name__ == "__main__":
    main()

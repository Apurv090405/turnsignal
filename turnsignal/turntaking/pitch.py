from __future__ import annotations

import numpy as np


F0_MIN_HZ = 70
F0_MAX_HZ = 400
PITCH_CLARITY_THRESHOLD = 0.3
SILENCE_AMPLITUDE = 0.005
MIN_DURATION_S = 0.05


def estimate_f0(samples: np.ndarray, sample_rate: int) -> float | None:
    if samples.size < int(MIN_DURATION_S * sample_rate):
        return None

    s = samples - np.mean(samples)
    if np.max(np.abs(s)) < SILENCE_AMPLITUDE:
        return None

    min_lag = sample_rate // F0_MAX_HZ
    max_lag = sample_rate // F0_MIN_HZ
    if max_lag >= s.size:
        return None

    ac = np.correlate(s, s, mode="full")[s.size - 1:]
    ac0 = float(ac[0])
    if ac0 <= 0:
        return None

    window = ac[min_lag:max_lag + 1]
    if window.size == 0:
        return None
    peak = int(np.argmax(window))
    if float(window[peak]) < PITCH_CLARITY_THRESHOLD * ac0:
        return None

    return float(sample_rate / (peak + min_lag))
#----------#

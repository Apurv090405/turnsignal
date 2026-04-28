from __future__ import annotations

from enum import Enum

import numpy as np

from turnsignal.turntaking.pitch import estimate_f0


class ProsodyVerdict(str, Enum):
    ENDING = "ending"
    GOING = "going"
    AMBIGUOUS = "ambiguous"
#----------#


WINDOW_MS = 800
MIN_WINDOW_S = 0.4
PITCH_DROP_THRESHOLD = 0.15
PITCH_RISE_THRESHOLD = 0.10
ENERGY_DROP_THRESHOLD = 0.20
ENERGY_RISE_THRESHOLD = 0.15
STRONG_ENERGY_DECAY = ENERGY_DROP_THRESHOLD * 2


def _rms(samples: np.ndarray) -> float:
    return float(np.sqrt(np.mean(samples ** 2))) + 1e-9
#----------#


class ProsodySignal:
    """Pitch trajectory + energy decay over the last ~800ms."""

    def analyze(self, samples: np.ndarray, sample_rate: int) -> ProsodyVerdict:
        min_size = int(MIN_WINDOW_S * sample_rate)
        if samples.size < min_size:
            return ProsodyVerdict.AMBIGUOUS

        window = samples[-int(WINDOW_MS * sample_rate / 1000):]
        if window.size < min_size:
            return ProsodyVerdict.AMBIGUOUS

        return self._classify(window, sample_rate)
    #----------#

    def _classify(self, window: np.ndarray, sample_rate: int) -> ProsodyVerdict:
        half = window.size // 2
        first, second = window[:half], window[half:]

        f0_first = estimate_f0(first, sample_rate)
        f0_second = estimate_f0(second, sample_rate)
        rms_first = _rms(first)
        rms_second = _rms(second)
        energy_drop = 1.0 - (rms_second / rms_first)

        if f0_first is None or f0_second is None:
            if energy_drop > STRONG_ENERGY_DECAY:
                return ProsodyVerdict.ENDING
            return ProsodyVerdict.AMBIGUOUS

        pitch_drop = (f0_first - f0_second) / f0_first
        if pitch_drop > PITCH_DROP_THRESHOLD and energy_drop > ENERGY_DROP_THRESHOLD:
            return ProsodyVerdict.ENDING
        if pitch_drop < -PITCH_RISE_THRESHOLD or energy_drop < -ENERGY_RISE_THRESHOLD:
            return ProsodyVerdict.GOING
        return ProsodyVerdict.AMBIGUOUS
    #----------#
#----------#

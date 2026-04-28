from __future__ import annotations

import numpy as np

MIN_FLOOR_MS = 120.0
MAX_FLOOR_MS = 700.0
PERCENTILE = 90
MIN_SAMPLES = 5
WINDOW = 30


class AdaptiveFloor:
    """Tracks a floor on the silence deadline based on the user's observed
    mid-utterance pause distribution."""

    def __init__(self, initial_ms: float = 150.0):
        self._floor_ms = initial_ms
        self._samples: list[float] = []
    #----------#

    @property
    def floor_ms(self) -> float:
        return self._floor_ms
    #----------#

    def observe(self, gap_ms: float) -> None:
        self._samples.append(gap_ms)
        if len(self._samples) < MIN_SAMPLES:
            return
        recent = self._samples[-WINDOW:]
        p = float(np.percentile(recent, PERCENTILE))
        self._floor_ms = max(MIN_FLOOR_MS, min(p, MAX_FLOOR_MS))
    #----------#
#----------#

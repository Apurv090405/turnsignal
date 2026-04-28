from __future__ import annotations

import numpy as np


class RollingAudioBuffer:
    """Stores recent float32 samples up to a fixed window length."""

    def __init__(self, max_samples: int):
        self._max_samples = max_samples
        self._chunks: list[np.ndarray] = []
        self._total = 0
    #----------#

    def write(self, samples: np.ndarray) -> None:
        self._chunks.append(samples)
        self._total += samples.size
        while self._chunks and self._total - self._chunks[0].size >= self._max_samples:
            self._total -= self._chunks[0].size
            self._chunks.pop(0)
    #----------#

    def tail(self, n_samples: int) -> np.ndarray:
        if not self._chunks:
            return np.zeros(0, dtype=np.float32)
        full = np.concatenate(self._chunks)
        return full[-n_samples:] if full.size > n_samples else full
    #----------#
#----------#

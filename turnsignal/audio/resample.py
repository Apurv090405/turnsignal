from __future__ import annotations

import numpy as np
import soxr


def resample(pcm16: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    if src_rate == dst_rate:
        return pcm16
    out = soxr.resample(pcm16.astype(np.float32) / 32768.0, src_rate, dst_rate)
    return np.clip(out * 32768.0, -32768, 32767).astype(np.int16)
#----------#

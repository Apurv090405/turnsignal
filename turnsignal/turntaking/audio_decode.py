from __future__ import annotations

import numpy as np

from turnsignal.core.frame import AudioFrame
from turnsignal.core.types import AudioEncoding


def to_float32(frame: AudioFrame) -> np.ndarray:
    if frame.encoding == AudioEncoding.PCM_F32:
        return np.frombuffer(frame.data, dtype=np.float32)
    if frame.encoding == AudioEncoding.PCM16:
        return np.frombuffer(frame.data, dtype=np.int16).astype(np.float32) / 32768.0
    raise NotImplementedError(
        f"detector requires PCM16 or PCM_F32, got {frame.encoding}"
    )
#----------#

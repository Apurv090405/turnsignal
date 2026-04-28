from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

import numpy as np

VadEvent = Literal["speech_started", "speech_paused"] | None


class VadSignal(ABC):
    """Voice-activity detector. Fed audio in real time; returns a transition."""

    @abstractmethod
    def feed(self, samples: np.ndarray, sample_rate: int) -> VadEvent: ...
    #----------#
#----------#


class HysteresisVad(VadSignal):
    """RMS-based VAD with hysteresis — reference fallback only.

    Drop in silero-vad for production."""

    def __init__(
        self,
        *,
        speech_rms_threshold: float = 0.02,
        silence_rms_threshold: float = 0.01,
        speech_hold_ms: float = 100.0,
        silence_hold_ms: float = 80.0,
    ):
        self._speech_th = speech_rms_threshold
        self._silence_th = silence_rms_threshold
        self._speech_hold_ms = speech_hold_ms
        self._silence_hold_ms = silence_hold_ms
        self._in_speech = False
        self._above_ms = 0.0
        self._below_ms = 0.0
    #----------#

    def feed(self, samples: np.ndarray, sample_rate: int) -> VadEvent:
        if samples.size == 0:
            return None
        rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))
        ms = (samples.size / sample_rate) * 1000.0

        if not self._in_speech:
            return self._maybe_start(rms, ms)
        return self._maybe_pause(rms, ms)
    #----------#

    def _maybe_start(self, rms: float, ms: float) -> VadEvent:
        if rms >= self._speech_th:
            self._above_ms += ms
            if self._above_ms >= self._speech_hold_ms:
                self._in_speech = True
                self._above_ms = 0.0
                self._below_ms = 0.0
                return "speech_started"
        else:
            self._above_ms = 0.0
        return None
    #----------#

    def _maybe_pause(self, rms: float, ms: float) -> VadEvent:
        if rms <= self._silence_th:
            self._below_ms += ms
            if self._below_ms >= self._silence_hold_ms:
                self._in_speech = False
                self._below_ms = 0.0
                self._above_ms = 0.0
                return "speech_paused"
        else:
            self._below_ms = 0.0
        return None
    #----------#
#----------#

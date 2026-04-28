from __future__ import annotations

import numpy as np

from turnsignal.audio.mulaw import mulaw_to_pcm16, pcm16_to_mulaw
from turnsignal.audio.resample import resample
from turnsignal.core.frame import AudioFrame
from turnsignal.core.types import AudioEncoding
from turnsignal.telco.twilio_protocol import TWILIO_RATE


def to_telco_mulaw(frame: AudioFrame) -> bytes:
    if frame.encoding == AudioEncoding.MULAW and frame.sample_rate == TWILIO_RATE:
        return frame.data

    pcm = _decode_to_pcm16(frame)
    if frame.sample_rate != TWILIO_RATE:
        pcm = resample(pcm, frame.sample_rate, TWILIO_RATE)
    return pcm16_to_mulaw(pcm)
#----------#


def _decode_to_pcm16(frame: AudioFrame) -> np.ndarray:
    if frame.encoding == AudioEncoding.PCM16:
        return np.frombuffer(frame.data, dtype=np.int16)
    if frame.encoding == AudioEncoding.PCM_F32:
        f = np.frombuffer(frame.data, dtype=np.float32)
        return np.clip(f * 32768.0, -32768, 32767).astype(np.int16)
    if frame.encoding == AudioEncoding.MULAW:
        return mulaw_to_pcm16(frame.data)
    raise ValueError(f"unsupported encoding {frame.encoding}")
#----------#

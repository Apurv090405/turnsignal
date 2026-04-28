from __future__ import annotations

import time
from dataclasses import dataclass, field

from turnsignal.core.types import AudioDirection, AudioEncoding, EventType


_BYTES_PER_SAMPLE = {
    AudioEncoding.PCM16: 2,
    AudioEncoding.PCM_F32: 4,
    AudioEncoding.MULAW: 1,
}


@dataclass(frozen=True, kw_only=True)
class Frame:
    timestamp: float = field(default_factory=time.monotonic)
#----------#


@dataclass(frozen=True, kw_only=True)
class AudioFrame(Frame):
    data: bytes
    sample_rate: int = 8000
    num_channels: int = 1
    encoding: AudioEncoding = AudioEncoding.PCM16
    direction: AudioDirection = AudioDirection.INBOUND

    @property
    def duration_ms(self) -> float:
        bps = _BYTES_PER_SAMPLE[self.encoding]
        n_samples = len(self.data) // (bps * self.num_channels)
        return (n_samples / self.sample_rate) * 1000
    #----------#
#----------#


@dataclass(frozen=True, kw_only=True)
class TextFrame(Frame):
    text: str
    is_partial: bool = False
    source: str = "user"
#----------#


@dataclass(frozen=True, kw_only=True)
class EventFrame(Frame):
    event_type: EventType
    payload: dict = field(default_factory=dict)
#----------#

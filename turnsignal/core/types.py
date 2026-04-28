from __future__ import annotations

from enum import Enum


class AudioEncoding(str, Enum):
    PCM16 = "pcm16"
    PCM_F32 = "pcm_f32"
    MULAW = "mulaw"
#----------#


class AudioDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
#----------#


class EventType(str, Enum):
    SPEECH_STARTED = "speech_started"
    SPEECH_PAUSED = "speech_paused"
    TURN_END = "turn_end"
    INTERRUPTION = "interruption"
    HANGUP = "hangup"
#----------#

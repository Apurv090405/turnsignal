from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class TurnTakingConfig:
    fast_deadline_ms: float = 200.0
    default_deadline_ms: float = 600.0
    slow_deadline_ms: float = 1200.0
    prosody_buffer_ms: int = 1600
    adaptive_floor_ms: float = 150.0
#----------#


@dataclass(frozen=True, kw_only=True)
class VadConfig:
    speech_rms_threshold: float = 0.02
    silence_rms_threshold: float = 0.01
    speech_hold_ms: float = 100.0
    silence_hold_ms: float = 80.0
#----------#


@dataclass(frozen=True, kw_only=True)
class TelcoConfig:
    bind_host: str = "0.0.0.0"
    bind_port: int = 5000
#----------#

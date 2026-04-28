from __future__ import annotations

from dataclasses import dataclass

from turnsignal.turntaking.prosody_signal import ProsodyVerdict
from turnsignal.turntaking.semantic_signal import SemanticVerdict


@dataclass(frozen=True, kw_only=True)
class Deadlines:
    fast_ms: float = 200.0
    default_ms: float = 600.0
    slow_ms: float = 1200.0
#----------#


def initial_deadline_ms(prosody: ProsodyVerdict, deadlines: Deadlines) -> float:
    return {
        ProsodyVerdict.ENDING: deadlines.fast_ms,
        ProsodyVerdict.GOING: deadlines.slow_ms,
        ProsodyVerdict.AMBIGUOUS: deadlines.default_ms,
    }[prosody]
#----------#


def should_extend(prosody: ProsodyVerdict, semantic: SemanticVerdict | None) -> bool:
    return prosody == ProsodyVerdict.ENDING and semantic == SemanticVerdict.INCOMPLETE
#----------#


def extension_seconds(deadline_ms: float, deadlines: Deadlines) -> float:
    return max(0.0, (deadlines.slow_ms - deadline_ms) / 1000)
#----------#

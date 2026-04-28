from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum


class SemanticVerdict(str, Enum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
#----------#


class SemanticSignal(ABC):
    """Async classifier: is the partial transcript a complete thought?"""

    @abstractmethod
    async def is_complete_thought(self, partial_transcript: str) -> SemanticVerdict: ...
    #----------#
#----------#


class HeuristicSemantic(SemanticSignal):
    """Zero-network reference fallback. Replace with a small LLM in production."""

    _CONNECTIVES = frozenset(
        {"and", "but", "so", "because", "or", "if", "while", "though", "with"}
    )
    _TERMINALS = frozenset({".", "!", "?"})

    async def is_complete_thought(self, partial_transcript: str) -> SemanticVerdict:
        text = partial_transcript.strip()
        if not text:
            return SemanticVerdict.INCOMPLETE
        if text[-1] in self._TERMINALS:
            return SemanticVerdict.COMPLETE
        if text.endswith(","):
            return SemanticVerdict.INCOMPLETE
        last_word = text.split()[-1].lower().strip(".,!?")
        if last_word in self._CONNECTIVES:
            return SemanticVerdict.INCOMPLETE
        return SemanticVerdict.COMPLETE
    #----------#
#----------#

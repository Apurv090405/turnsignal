from __future__ import annotations

import asyncio
from typing import AsyncIterator, Literal

import numpy as np

from turnsignal.turntaking.prosody_signal import ProsodySignal, ProsodyVerdict
from turnsignal.turntaking.semantic_signal import SemanticSignal, SemanticVerdict
from turnsignal.turntaking.vad_signal import VadEvent, VadSignal


class FakeVad(VadSignal):
    def __init__(self) -> None:
        self._events: list[VadEvent] = []
    #----------#

    def queue(self, event: Literal["speech_started", "speech_paused"] | None) -> None:
        self._events.append(event)
    #----------#

    def feed(self, samples: np.ndarray, sample_rate: int) -> VadEvent:
        if not self._events:
            return None
        return self._events.pop(0)
    #----------#
#----------#


class FakeProsody(ProsodySignal):
    def __init__(self, verdict: ProsodyVerdict = ProsodyVerdict.AMBIGUOUS) -> None:
        self.verdict = verdict
    #----------#

    def analyze(self, samples: np.ndarray, sample_rate: int) -> ProsodyVerdict:
        return self.verdict
    #----------#
#----------#


class FakeSemantic(SemanticSignal):
    def __init__(
        self,
        verdict: SemanticVerdict = SemanticVerdict.COMPLETE,
        latency_ms: float = 2.0,
    ) -> None:
        self.verdict = verdict
        self.latency_ms = latency_ms
    #----------#

    async def is_complete_thought(self, partial_transcript: str) -> SemanticVerdict:
        await asyncio.sleep(self.latency_ms / 1000)
        return self.verdict
    #----------#
#----------#


class FakeWebSocket:
    def __init__(self) -> None:
        self._inbox: asyncio.Queue[str | None] = asyncio.Queue()
        self.sent: list[str] = []
        self.closed = False
    #----------#

    async def push(self, message: str) -> None:
        await self._inbox.put(message)
    #----------#

    async def push_close(self) -> None:
        await self._inbox.put(None)
    #----------#

    def __aiter__(self) -> AsyncIterator[str]:
        return self._iter()
    #----------#

    async def _iter(self) -> AsyncIterator[str]:
        while True:
            msg = await self._inbox.get()
            if msg is None:
                return
            yield msg
    #----------#

    async def send(self, message: str) -> None:
        if self.closed:
            raise ConnectionError("websocket closed")
        self.sent.append(message)
    #----------#

    async def close(self) -> None:
        self.closed = True
    #----------#
#----------#

from __future__ import annotations

import asyncio
import time

import numpy as np
import pytest

from turnsignal.core.call import Call
from turnsignal.core.frame import AudioFrame, EventFrame, TextFrame
from turnsignal.core.types import AudioDirection, AudioEncoding, EventType
from turnsignal.turntaking.detector import EndOfTurnDetector
from turnsignal.turntaking.prosody_signal import ProsodyVerdict
from turnsignal.turntaking.semantic_signal import SemanticSignal, SemanticVerdict
from tests.fakes import FakeProsody, FakeSemantic, FakeVad

FAST_MS = 20
DEFAULT_MS = 60
SLOW_MS = 120


def silent_frame(sample_rate: int = 8000, duration_ms: int = 20) -> AudioFrame:
    n = int(sample_rate * duration_ms / 1000)
    return AudioFrame(
        data=np.zeros(n, dtype=np.int16).tobytes(),
        sample_rate=sample_rate,
        encoding=AudioEncoding.PCM16,
        direction=AudioDirection.INBOUND,
    )
#----------#


class Harness:
    def __init__(self, vad, prosody, semantic, call, turn_ends, collector):
        self.vad = vad
        self.prosody = prosody
        self.semantic = semantic
        self.call = call
        self.turn_ends: list[EventFrame] = turn_ends
        self._collector = collector
    #----------#

    async def pump_frame(self) -> None:
        self.call.bus.publish(silent_frame())
        for _ in range(4):
            await asyncio.sleep(0)
    #----------#

    async def shutdown(self) -> None:
        self._collector.cancel()
        await self.call.stop()
    #----------#
#----------#


@pytest.fixture
async def harness():
    vad = FakeVad()
    prosody = FakeProsody()
    semantic = FakeSemantic()
    detector = EndOfTurnDetector(
        vad=vad,
        prosody=prosody,
        semantic=semantic,
        fast_deadline_ms=FAST_MS,
        default_deadline_ms=DEFAULT_MS,
        slow_deadline_ms=SLOW_MS,
        adaptive_floor_ms=0.0,
    )
    call = Call()
    call.add_stage(detector)

    turn_ends: list[EventFrame] = []

    async def collect():
        async for f in call.bus.subscribe(EventFrame):
            if f.event_type == EventType.TURN_END:
                turn_ends.append(f)

    collector = asyncio.create_task(collect())
    await call.start()
    await asyncio.sleep(0)

    h = Harness(vad, prosody, semantic, call, turn_ends, collector)
    try:
        yield h
    finally:
        await h.shutdown()
#----------#


async def _wait_for_turn_end(turn_ends: list[EventFrame], timeout: float) -> EventFrame | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if turn_ends:
            return turn_ends[-1]
        await asyncio.sleep(0.005)
    return None
#----------#


async def test_prosody_ending_semantic_complete_fires_at_fast_deadline(harness):
    harness.prosody.verdict = ProsodyVerdict.ENDING
    harness.semantic.verdict = SemanticVerdict.COMPLETE

    harness.vad.queue("speech_started")
    await harness.pump_frame()

    pause_at = time.monotonic()
    harness.vad.queue("speech_paused")
    await harness.pump_frame()

    event = await _wait_for_turn_end(harness.turn_ends, timeout=0.2)
    assert event is not None
    elapsed_ms = (event.timestamp - pause_at) * 1000
    assert FAST_MS - 5 <= elapsed_ms <= DEFAULT_MS, (
        f"expected fire near {FAST_MS}ms, got {elapsed_ms:.1f}ms"
    )
    assert event.payload["prosody"] == "ending"
    assert event.payload["semantic"] == "complete"
#----------#


async def test_prosody_ending_semantic_incomplete_extends_to_slow_deadline(harness):
    harness.prosody.verdict = ProsodyVerdict.ENDING
    harness.semantic.verdict = SemanticVerdict.INCOMPLETE

    harness.vad.queue("speech_started")
    await harness.pump_frame()

    pause_at = time.monotonic()
    harness.vad.queue("speech_paused")
    await harness.pump_frame()

    event = await _wait_for_turn_end(harness.turn_ends, timeout=0.5)
    assert event is not None
    elapsed_ms = (event.timestamp - pause_at) * 1000
    assert SLOW_MS - 10 <= elapsed_ms <= SLOW_MS + 40
#----------#


async def test_prosody_going_waits_full_slow_deadline(harness):
    harness.prosody.verdict = ProsodyVerdict.GOING
    harness.semantic.verdict = SemanticVerdict.COMPLETE

    harness.vad.queue("speech_started")
    await harness.pump_frame()

    pause_at = time.monotonic()
    harness.vad.queue("speech_paused")
    await harness.pump_frame()

    event = await _wait_for_turn_end(harness.turn_ends, timeout=0.5)
    assert event is not None
    elapsed_ms = (event.timestamp - pause_at) * 1000
    assert SLOW_MS - 10 <= elapsed_ms <= SLOW_MS + 40
#----------#


async def test_prosody_ambiguous_fires_at_default_deadline(harness):
    harness.prosody.verdict = ProsodyVerdict.AMBIGUOUS
    harness.semantic.verdict = SemanticVerdict.COMPLETE

    harness.vad.queue("speech_started")
    await harness.pump_frame()

    pause_at = time.monotonic()
    harness.vad.queue("speech_paused")
    await harness.pump_frame()

    event = await _wait_for_turn_end(harness.turn_ends, timeout=0.3)
    assert event is not None
    elapsed_ms = (event.timestamp - pause_at) * 1000
    assert DEFAULT_MS - 10 <= elapsed_ms <= DEFAULT_MS + 30
#----------#


async def test_speech_resumes_cancels_decision(harness):
    harness.prosody.verdict = ProsodyVerdict.AMBIGUOUS
    harness.semantic.verdict = SemanticVerdict.COMPLETE

    harness.vad.queue("speech_started")
    await harness.pump_frame()

    harness.vad.queue("speech_paused")
    await harness.pump_frame()
    await asyncio.sleep(DEFAULT_MS / 2 / 1000)

    harness.vad.queue("speech_started")
    await harness.pump_frame()

    await asyncio.sleep((SLOW_MS + 30) / 1000)
    assert harness.turn_ends == []
#----------#


async def test_partial_transcript_passed_to_semantic(harness):
    captured: list[str] = []

    class CapturingSemantic(SemanticSignal):
        async def is_complete_thought(self, partial_transcript: str) -> SemanticVerdict:
            captured.append(partial_transcript)
            return SemanticVerdict.COMPLETE

    harness.semantic = CapturingSemantic()
    detector = harness.call._stages[0]
    detector._semantic = harness.semantic

    harness.call.bus.publish(TextFrame(text="i was thinking about", source="user", is_partial=True))
    await asyncio.sleep(0.005)

    harness.prosody.verdict = ProsodyVerdict.ENDING
    harness.vad.queue("speech_started")
    await harness.pump_frame()
    harness.vad.queue("speech_paused")
    await harness.pump_frame()

    await _wait_for_turn_end(harness.turn_ends, timeout=0.3)
    assert captured == ["i was thinking about"]
#----------#


async def test_cancelled_pause_is_recorded_for_adaptive_floor():
    vad = FakeVad()
    prosody = FakeProsody(verdict=ProsodyVerdict.AMBIGUOUS)
    semantic = FakeSemantic(verdict=SemanticVerdict.COMPLETE)
    detector = EndOfTurnDetector(
        vad=vad,
        prosody=prosody,
        semantic=semantic,
        fast_deadline_ms=FAST_MS,
        default_deadline_ms=DEFAULT_MS,
        slow_deadline_ms=SLOW_MS,
        adaptive_floor_ms=0.0,
    )
    call = Call()
    call.add_stage(detector)
    await call.start()
    await asyncio.sleep(0)

    try:
        for _ in range(6):
            vad.queue("speech_started")
            call.bus.publish(silent_frame())
            for _ in range(4):
                await asyncio.sleep(0)

            vad.queue("speech_paused")
            call.bus.publish(silent_frame())
            for _ in range(4):
                await asyncio.sleep(0)

            await asyncio.sleep(0.015)

            vad.queue("speech_started")
            call.bus.publish(silent_frame())
            for _ in range(4):
                await asyncio.sleep(0)

        assert len(detector._floor._samples) >= 5
        assert detector._floor.floor_ms >= 120.0
    finally:
        await call.stop()
#----------#

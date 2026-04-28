from __future__ import annotations

import asyncio
import logging
import time

from turnsignal.core.frame import AudioFrame, EventFrame, TextFrame
from turnsignal.core.pipeline import Stage, StageContext
from turnsignal.core.types import AudioDirection, EventType
from turnsignal.turntaking.adaptive_floor import AdaptiveFloor
from turnsignal.turntaking.audio_buffer import RollingAudioBuffer
from turnsignal.turntaking.audio_decode import to_float32
from turnsignal.turntaking.decision import (
    Deadlines,
    extension_seconds,
    initial_deadline_ms,
    should_extend,
)
from turnsignal.turntaking.prosody_signal import ProsodySignal
from turnsignal.turntaking.semantic_signal import SemanticSignal, SemanticVerdict
from turnsignal.turntaking.vad_signal import VadSignal

log = logging.getLogger(__name__)

PROSODY_BUFFER_MS = 1600


class EndOfTurnDetector(Stage):
    """Decides when the user is done speaking by racing VAD silence, prosody,
    and a semantic completeness check. Publishes EventFrame(TURN_END)."""

    name = "end_of_turn_detector"

    def __init__(
        self,
        *,
        vad: VadSignal,
        prosody: ProsodySignal,
        semantic: SemanticSignal,
        sample_rate: int = 8000,
        fast_deadline_ms: float = 200.0,
        default_deadline_ms: float = 600.0,
        slow_deadline_ms: float = 1200.0,
        adaptive_floor_ms: float = 150.0,
        prosody_buffer_ms: int = PROSODY_BUFFER_MS,
    ):
        self._vad = vad
        self._prosody = prosody
        self._semantic = semantic
        self._sample_rate = sample_rate
        self._deadlines = Deadlines(
            fast_ms=fast_deadline_ms,
            default_ms=default_deadline_ms,
            slow_ms=slow_deadline_ms,
        )
        self._prosody_buffer_ms = prosody_buffer_ms

        buffer_samples = int(prosody_buffer_ms * sample_rate / 1000)
        self._buffer = RollingAudioBuffer(buffer_samples)
        self._floor = AdaptiveFloor(adaptive_floor_ms)

        self._partial_transcript = ""
        self._cancel_event: asyncio.Event | None = None
        self._decision_task: asyncio.Task | None = None
    #----------#

    async def run(self, ctx: StageContext) -> None:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._pull_audio(ctx))
            tg.create_task(self._pull_text(ctx))
    #----------#

    async def _pull_audio(self, ctx: StageContext) -> None:
        async for frame in ctx.subscribe(AudioFrame):
            assert isinstance(frame, AudioFrame)
            if frame.direction != AudioDirection.INBOUND:
                continue
            samples = to_float32(frame)
            self._buffer.write(samples)

            event = self._vad.feed(samples, frame.sample_rate)
            if event == "speech_started":
                await self._on_voice_resume()
            elif event == "speech_paused":
                self._on_voice_pause(ctx)
    #----------#

    async def _pull_text(self, ctx: StageContext) -> None:
        async for frame in ctx.subscribe(TextFrame):
            assert isinstance(frame, TextFrame)
            if frame.source == "user":
                self._partial_transcript = frame.text
    #----------#

    async def _on_voice_resume(self) -> None:
        if self._decision_task and not self._decision_task.done():
            assert self._cancel_event is not None
            self._cancel_event.set()
            try:
                await self._decision_task
            except (asyncio.CancelledError, Exception):
                pass
        self._decision_task = None
        self._cancel_event = None
    #----------#

    def _on_voice_pause(self, ctx: StageContext) -> None:
        self._cancel_event = asyncio.Event()
        self._decision_task = asyncio.create_task(
            self._resolve_turn(ctx, self._cancel_event)
        )
    #----------#

    async def _resolve_turn(self, ctx: StageContext, cancel: asyncio.Event) -> None:
        pause_start = time.monotonic()

        semantic_task = asyncio.create_task(
            self._semantic.is_complete_thought(self._partial_transcript)
        )

        recent = self._buffer.tail(int(self._prosody_buffer_ms * self._sample_rate / 1000))
        prosody = self._prosody.analyze(recent, self._sample_rate)

        deadline_ms = max(
            initial_deadline_ms(prosody, self._deadlines),
            self._floor.floor_ms,
        )

        if await self._wait_or_cancel(cancel, deadline_ms / 1000):
            self._floor.observe((time.monotonic() - pause_start) * 1000)
            semantic_task.cancel()
            return

        semantic = self._take_semantic(semantic_task)

        if should_extend(prosody, semantic):
            ext = extension_seconds(deadline_ms, self._deadlines)
            if await self._wait_or_cancel(cancel, ext):
                return

        ctx.publish(self._build_turn_end(prosody, semantic, pause_start, deadline_ms))
    #----------#

    async def _wait_or_cancel(self, cancel: asyncio.Event, timeout: float) -> bool:
        try:
            await asyncio.wait_for(cancel.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False
    #----------#

    def _take_semantic(self, task: asyncio.Task) -> SemanticVerdict | None:
        if not task.done():
            task.cancel()
            return None
        try:
            return task.result()
        except Exception:
            log.warning("semantic check failed", exc_info=True)
            return None
    #----------#

    def _build_turn_end(
        self,
        prosody,
        semantic,
        pause_start: float,
        deadline_ms: float,
    ) -> EventFrame:
        return EventFrame(
            event_type=EventType.TURN_END,
            payload={
                "pause_ms": (time.monotonic() - pause_start) * 1000,
                "prosody": prosody.value,
                "semantic": semantic.value if semantic else None,
                "deadline_ms": deadline_ms,
                "transcript": self._partial_transcript,
            },
        )
    #----------#
#----------#

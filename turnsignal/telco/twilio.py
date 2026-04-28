from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator, Protocol

from turnsignal.audio.mulaw import mulaw_to_pcm16
from turnsignal.core.frame import AudioFrame, EventFrame
from turnsignal.core.pipeline import StageContext
from turnsignal.core.types import AudioDirection, AudioEncoding, EventType
from turnsignal.telco.base import TelcoAdapter
from turnsignal.telco.twilio_audio import to_telco_mulaw
from turnsignal.telco.twilio_protocol import (
    TWILIO_RATE,
    MediaEvent,
    StartEvent,
    StopEvent,
    build_media_envelope,
    chunk_mulaw,
    parse_event,
)

log = logging.getLogger(__name__)


class WebSocketLike(Protocol):
    async def send(self, message: str | bytes) -> None: ...
    async def close(self) -> None: ...
    def __aiter__(self) -> AsyncIterator[str | bytes]: ...
#----------#


class TwilioStage(TelcoAdapter):
    """Bridges a Twilio Media Streams WebSocket to the bus."""

    name = "twilio"

    def __init__(self, websocket: WebSocketLike):
        self._ws = websocket
        self._stream_sid: str | None = None
        self._stop_event = asyncio.Event()
    #----------#

    async def run(self, ctx: StageContext) -> None:
        reader = asyncio.create_task(self._reader(ctx), name="twilio-reader")
        writer = asyncio.create_task(self._writer(ctx), name="twilio-writer")
        try:
            await self._stop_event.wait()
        finally:
            reader.cancel()
            writer.cancel()
            await asyncio.gather(reader, writer, return_exceptions=True)
            try:
                await self._ws.close()
            except Exception:
                pass
    #----------#

    async def _reader(self, ctx: StageContext) -> None:
        try:
            async for raw in self._ws:
                if not self._handle_event(parse_event(raw), ctx):
                    break
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("twilio reader failed")
        finally:
            ctx.publish(EventFrame(event_type=EventType.HANGUP))
            self._stop_event.set()
    #----------#

    def _handle_event(self, event, ctx: StageContext) -> bool:
        if isinstance(event, StartEvent):
            self._stream_sid = event.stream_sid
            return True
        if isinstance(event, MediaEvent):
            if event.track == "inbound":
                self._publish_inbound(ctx, event.payload)
            return True
        if isinstance(event, StopEvent):
            return False
        return True
    #----------#

    def _publish_inbound(self, ctx: StageContext, mulaw_payload: bytes) -> None:
        pcm16 = mulaw_to_pcm16(mulaw_payload)
        ctx.publish(
            AudioFrame(
                data=pcm16.tobytes(),
                sample_rate=TWILIO_RATE,
                encoding=AudioEncoding.PCM16,
                direction=AudioDirection.INBOUND,
            )
        )
    #----------#

    async def _writer(self, ctx: StageContext) -> None:
        try:
            async for frame in ctx.subscribe(AudioFrame):
                assert isinstance(frame, AudioFrame)
                if frame.direction != AudioDirection.OUTBOUND:
                    continue
                if self._stream_sid is None:
                    continue
                if not await self._send_frame(frame):
                    return
        except asyncio.CancelledError:
            raise
    #----------#

    async def _send_frame(self, frame: AudioFrame) -> bool:
        mulaw = to_telco_mulaw(frame)
        for chunk in chunk_mulaw(mulaw):
            envelope = build_media_envelope(self._stream_sid, chunk)
            try:
                await self._ws.send(envelope)
            except Exception:
                log.warning("twilio send failed; ending writer", exc_info=True)
                self._stop_event.set()
                return False
        return True
    #----------#
#----------#

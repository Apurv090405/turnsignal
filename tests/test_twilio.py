from __future__ import annotations

import asyncio
import base64
import json
import time

import numpy as np

from turnsignal.audio.mulaw import pcm16_to_mulaw
from turnsignal.core.call import Call, CallState
from turnsignal.core.frame import AudioFrame, EventFrame
from turnsignal.core.pipeline import Stage, StageContext
from turnsignal.core.types import AudioDirection, AudioEncoding
from turnsignal.telco.twilio import TwilioStage
from tests.fakes import FakeWebSocket


def media_event(payload_bytes: bytes, stream_sid: str = "MZ_test") -> str:
    return json.dumps(
        {
            "event": "media",
            "streamSid": stream_sid,
            "media": {
                "track": "inbound",
                "chunk": "1",
                "timestamp": "20",
                "payload": base64.b64encode(payload_bytes).decode("ascii"),
            },
        }
    )
#----------#


def start_event(stream_sid: str = "MZ_test") -> str:
    return json.dumps({"event": "start", "streamSid": stream_sid, "start": {}})
#----------#


def stop_event() -> str:
    return json.dumps({"event": "stop", "stop": {}})
#----------#


class FrameCollector(Stage):
    name = "collector"

    def __init__(self) -> None:
        self.audio: list[AudioFrame] = []
        self.events: list[EventFrame] = []
    #----------#

    async def run(self, ctx: StageContext) -> None:
        audio_task = asyncio.create_task(self._collect_audio(ctx))
        event_task = asyncio.create_task(self._collect_events(ctx))
        try:
            await asyncio.gather(audio_task, event_task)
        except asyncio.CancelledError:
            raise
    #----------#

    async def _collect_audio(self, ctx: StageContext) -> None:
        async for frame in ctx.subscribe(AudioFrame):
            assert isinstance(frame, AudioFrame)
            if frame.direction == AudioDirection.INBOUND:
                self.audio.append(frame)
    #----------#

    async def _collect_events(self, ctx: StageContext) -> None:
        async for frame in ctx.subscribe(EventFrame):
            assert isinstance(frame, EventFrame)
            self.events.append(frame)
    #----------#
#----------#


async def _wait_for(predicate, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.005)
    raise AssertionError("timeout waiting for predicate")
#----------#


async def test_inbound_media_decoded_to_pcm16_inbound_frame():
    ws = FakeWebSocket()
    collector = FrameCollector()
    call = Call()
    call.add_stage(TwilioStage(ws))
    call.add_stage(collector)
    await call.start()

    pcm = (np.sin(np.linspace(0, 2 * np.pi * 5, 160)) * 8000).astype(np.int16)
    mulaw = pcm16_to_mulaw(pcm)

    await ws.push(start_event())
    await ws.push(media_event(mulaw))
    for _ in range(8):
        await asyncio.sleep(0)

    assert len(collector.audio) == 1
    frame = collector.audio[0]
    assert frame.direction == AudioDirection.INBOUND
    assert frame.encoding == AudioEncoding.PCM16
    assert frame.sample_rate == 8000
    assert len(frame.data) == 160 * 2

    await ws.push(stop_event())
    await _wait_for(lambda: call.state == CallState.STOPPED, timeout=0.5)
#----------#


async def test_stop_event_publishes_hangup_and_stops_call():
    ws = FakeWebSocket()
    call = Call()
    call.add_stage(TwilioStage(ws))
    await call.start()

    await ws.push(start_event())
    await ws.push(stop_event())

    await _wait_for(lambda: call.state == CallState.STOPPED, timeout=0.5)
    assert call.state == CallState.STOPPED
#----------#


async def test_outbound_pcm16_at_24khz_resampled_and_sent_as_mulaw():
    ws = FakeWebSocket()
    call = Call()
    call.add_stage(TwilioStage(ws))
    await call.start()
    await ws.push(start_event())
    for _ in range(8):
        await asyncio.sleep(0)

    tts = (np.sin(np.linspace(0, 2 * np.pi * 220 * 0.1, 2400)) * 12000).astype(np.int16)
    call.bus.publish(
        AudioFrame(
            data=tts.tobytes(),
            sample_rate=24000,
            encoding=AudioEncoding.PCM16,
            direction=AudioDirection.OUTBOUND,
        )
    )
    for _ in range(20):
        await asyncio.sleep(0)

    media_msgs = [json.loads(m) for m in ws.sent]
    assert all(m["event"] == "media" for m in media_msgs)
    assert all(m["streamSid"] == "MZ_test" for m in media_msgs)
    total_bytes = sum(
        len(base64.b64decode(m["media"]["payload"])) for m in media_msgs
    )
    assert 700 <= total_bytes <= 900

    await ws.push(stop_event())
    await _wait_for(lambda: call.state == CallState.STOPPED, timeout=0.5)
#----------#


async def test_inbound_audio_does_not_loop_back_to_twilio():
    ws = FakeWebSocket()
    call = Call()
    call.add_stage(TwilioStage(ws))
    await call.start()

    pcm = np.zeros(160, dtype=np.int16)
    await ws.push(start_event())
    await ws.push(media_event(pcm16_to_mulaw(pcm)))
    for _ in range(10):
        await asyncio.sleep(0)

    assert ws.sent == []

    await ws.push(stop_event())
    await _wait_for(lambda: call.state == CallState.STOPPED, timeout=0.5)
#----------#

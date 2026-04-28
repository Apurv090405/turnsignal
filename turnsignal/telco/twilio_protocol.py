from __future__ import annotations

import base64
import json
from dataclasses import dataclass

TWILIO_RATE = 8000
TWILIO_CHUNK_BYTES = 160


@dataclass(frozen=True)
class StartEvent:
    stream_sid: str
#----------#


@dataclass(frozen=True)
class MediaEvent:
    payload: bytes
    track: str
#----------#


@dataclass(frozen=True)
class StopEvent:
    pass
#----------#


@dataclass(frozen=True)
class UnknownEvent:
    name: str
#----------#


def parse_event(raw: str) -> StartEvent | MediaEvent | StopEvent | UnknownEvent:
    msg = json.loads(raw)
    name = msg.get("event", "")
    if name == "start":
        sid = msg.get("streamSid") or msg.get("start", {}).get("streamSid", "")
        return StartEvent(stream_sid=sid)
    if name == "media":
        media = msg.get("media", {})
        return MediaEvent(
            payload=base64.b64decode(media["payload"]),
            track=media.get("track", "inbound"),
        )
    if name == "stop":
        return StopEvent()
    return UnknownEvent(name=name)
#----------#


def build_media_envelope(stream_sid: str, mulaw_chunk: bytes) -> str:
    return json.dumps(
        {
            "event": "media",
            "streamSid": stream_sid,
            "media": {"payload": base64.b64encode(mulaw_chunk).decode("ascii")},
        }
    )
#----------#


def chunk_mulaw(mulaw_bytes: bytes, chunk_size: int = TWILIO_CHUNK_BYTES):
    for i in range(0, len(mulaw_bytes), chunk_size):
        yield mulaw_bytes[i : i + chunk_size]
#----------#

import base64
import json

from turnsignal.telco.twilio_protocol import (
    MediaEvent,
    StartEvent,
    StopEvent,
    UnknownEvent,
    build_media_envelope,
    chunk_mulaw,
    parse_event,
)


def test_parse_start_event():
    raw = json.dumps({"event": "start", "streamSid": "MZ_abc", "start": {}})
    e = parse_event(raw)
    assert isinstance(e, StartEvent)
    assert e.stream_sid == "MZ_abc"
#----------#


def test_parse_start_event_nested_sid():
    raw = json.dumps({"event": "start", "start": {"streamSid": "MZ_xyz"}})
    e = parse_event(raw)
    assert isinstance(e, StartEvent)
    assert e.stream_sid == "MZ_xyz"
#----------#


def test_parse_media_event_decodes_payload():
    payload = b"\x80\x80\x80"
    raw = json.dumps(
        {
            "event": "media",
            "media": {
                "track": "inbound",
                "payload": base64.b64encode(payload).decode("ascii"),
            },
        }
    )
    e = parse_event(raw)
    assert isinstance(e, MediaEvent)
    assert e.payload == payload
    assert e.track == "inbound"
#----------#


def test_parse_stop_event():
    raw = json.dumps({"event": "stop", "stop": {}})
    e = parse_event(raw)
    assert isinstance(e, StopEvent)
#----------#


def test_parse_unknown_event():
    raw = json.dumps({"event": "mark", "mark": {"name": "x"}})
    e = parse_event(raw)
    assert isinstance(e, UnknownEvent)
    assert e.name == "mark"
#----------#


def test_build_media_envelope_round_trip():
    chunk = b"\x01\x02\x03"
    raw = build_media_envelope("MZ_abc", chunk)
    msg = json.loads(raw)
    assert msg["event"] == "media"
    assert msg["streamSid"] == "MZ_abc"
    assert base64.b64decode(msg["media"]["payload"]) == chunk
#----------#


def test_chunk_mulaw_splits_at_boundary():
    data = b"\xff" * (160 * 3 + 50)
    chunks = list(chunk_mulaw(data))
    assert len(chunks) == 4
    assert all(len(c) == 160 for c in chunks[:3])
    assert len(chunks[-1]) == 50
#----------#

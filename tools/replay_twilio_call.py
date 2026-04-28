"""Synthetic Twilio Media Streams client for local pipeline testing.

Connects to a running TwilioStage server (e.g. examples/twilio_echo.py) and
streams a WAV file as if it were a real phone call. Captures the server's
outbound audio and writes it to an output WAV so you can listen to the result.

Usage:
    python tools/replay_twilio_call.py \\
        --input recordings/sample.wav \\
        --output /tmp/echoed.wav \\
        --server ws://localhost:5000

Requires soundfile for WAV I/O:
    pip install soundfile
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import time
import uuid

import numpy as np
import soundfile as sf
from websockets.asyncio.client import connect

from turnsignal.audio.mulaw import mulaw_to_pcm16, pcm16_to_mulaw
from turnsignal.audio.resample import resample

TELCO_RATE = 8000
FRAME_MS = 20
FRAME_BYTES = 160


def load_audio_as_8k_pcm16(path: str) -> np.ndarray:
    audio, sr = sf.read(path, dtype="int16", always_2d=False)
    if audio.ndim == 2:
        audio = audio[:, 0]
    if sr != TELCO_RATE:
        audio = resample(audio, sr, TELCO_RATE)
    return audio.astype(np.int16)
#----------#


def slice_into_frames(pcm: np.ndarray) -> list[bytes]:
    out = []
    samples_per_frame = TELCO_RATE * FRAME_MS // 1000
    for i in range(0, len(pcm), samples_per_frame):
        chunk = pcm[i : i + samples_per_frame]
        out.append(pcm16_to_mulaw(chunk))
    return out
#----------#


def make_start_event(stream_sid: str) -> str:
    return json.dumps(
        {
            "event": "start",
            "streamSid": stream_sid,
            "start": {
                "streamSid": stream_sid,
                "callSid": "CA_replay_" + stream_sid,
                "tracks": ["inbound"],
                "mediaFormat": {
                    "encoding": "audio/x-mulaw",
                    "sampleRate": TELCO_RATE,
                    "channels": 1,
                },
            },
        }
    )
#----------#


def make_media_event(stream_sid: str, mulaw_chunk: bytes, chunk_idx: int) -> str:
    return json.dumps(
        {
            "event": "media",
            "streamSid": stream_sid,
            "media": {
                "track": "inbound",
                "chunk": str(chunk_idx),
                "timestamp": str(chunk_idx * FRAME_MS),
                "payload": base64.b64encode(mulaw_chunk).decode("ascii"),
            },
        }
    )
#----------#


def make_stop_event(stream_sid: str) -> str:
    return json.dumps({"event": "stop", "streamSid": stream_sid, "stop": {}})
#----------#


async def stream_to_server(ws, frames: list[bytes], stream_sid: str) -> None:
    await ws.send(make_start_event(stream_sid))
    start = time.monotonic()
    for i, chunk in enumerate(frames):
        target = start + (i * FRAME_MS) / 1000
        sleep_for = target - time.monotonic()
        if sleep_for > 0:
            await asyncio.sleep(sleep_for)
        await ws.send(make_media_event(stream_sid, chunk, i))
    await asyncio.sleep(0.2)
    await ws.send(make_stop_event(stream_sid))
#----------#


async def collect_outbound(ws, captured: list[int]) -> None:
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if msg.get("event") != "media":
                continue
            payload = msg.get("media", {}).get("payload")
            if not payload:
                continue
            mulaw = base64.b64decode(payload)
            pcm = mulaw_to_pcm16(mulaw)
            captured.extend(pcm.tolist())
    except Exception:
        pass
#----------#


async def replay(input_path: str, output_path: str, server_url: str) -> None:
    pcm = load_audio_as_8k_pcm16(input_path)
    frames = slice_into_frames(pcm)
    stream_sid = "MZ_replay_" + uuid.uuid4().hex[:8]

    logging.info(
        "loaded %d frames (%.1fs) from %s",
        len(frames),
        len(frames) * FRAME_MS / 1000,
        input_path,
    )
    logging.info("connecting to %s", server_url)

    async with connect(server_url) as ws:
        captured: list[int] = []
        sender = asyncio.create_task(stream_to_server(ws, frames, stream_sid))
        receiver = asyncio.create_task(collect_outbound(ws, captured))
        await sender
        await asyncio.sleep(0.5)
        receiver.cancel()
        try:
            await receiver
        except asyncio.CancelledError:
            pass

    if captured:
        out = np.array(captured, dtype=np.int16)
        sf.write(output_path, out, TELCO_RATE, subtype="PCM_16")
        logging.info(
            "wrote %d samples (%.1fs) to %s",
            len(out),
            len(out) / TELCO_RATE,
            output_path,
        )
    else:
        logging.warning("no outbound audio captured from server")
#----------#


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="path to a WAV file (any rate)")
    parser.add_argument("--output", default="/tmp/echoed.wav", help="output WAV (8kHz)")
    parser.add_argument("--server", default="ws://localhost:5000", help="WS server URL")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    asyncio.run(replay(args.input, args.output, args.server))
#----------#


if __name__ == "__main__":
    main()

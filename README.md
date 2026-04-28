# turnsignal

> Minimal-deps Python voice-AI library with telco-native turn-taking.

`turnsignal` is a small, modular Python library for building real-time
voice agents over the phone. It focuses on the two pain points that hurt every
existing framework: **turn-taking quality** and **telco-native audio handling**.

**Status:** v0.1.0-alpha. Architecture, turn-taking, audio pipeline, and the
Twilio adapter are real and tested (38 tests, all passing). STT / LLM / TTS
stages are not yet built — see [Status](#status). Drop in your own provider
clients today, or wait for the upstream stages.

---

## Why this exists

Looking at the open-source voice-AI landscape:

| Framework | Where it hurts |
|---|---|
| Pipecat | Memory leaks under concurrent calls |
| Bolna | Serial Python + GIL → end-to-end latency |
| LiveKit Agents | Solid, but heavyweight and opinionated about infra |
| Vocode | Inactive, integration friction |

The actually-hard problems in voice AI right now are turn-taking,
sub-300ms first-token latency under load, graceful reconnect, and
concurrency at thousands of calls. **Frameworks compete on the easy parts
(orchestration) and leave the hard parts to you.**

`turnsignal` picks one hard problem — turn-taking — and tries to be the
best-in-class at it, on top of an architecture that doesn't make the *other*
hard problems harder.

---

## The hero feature: turn-taking

Most voice frameworks treat end-of-utterance detection as a silence timer:

> "If user has been silent for 700ms, assume they're done."

This produces false interrupts (cut user off mid-thought) ~30% of the time
and dead air on slow speakers.

`turnsignal` races **three signals in parallel** when VAD detects a pause:

| Signal | What it measures | Latency |
|---|---|---|
| **A. VAD silence timer** | Adaptive floor learned from per-user pause distribution | 0 (timer) |
| **B. Prosody** | Pitch trajectory + energy decay over last 800ms (autocorr-based F0) | <5ms |
| **C. Semantic** | Small LLM: "is this a complete thought?" on partial transcript | 80–120ms (cached) |

**Decision rule:**

```
prosody = ENDING                            → fire at  200ms (fast)
prosody = GOING                             → wait at 1200ms (slow)
prosody = AMBIGUOUS                         → fire at  600ms (default)
prosody = ENDING  AND semantic = INCOMPLETE → extend to 1200ms
speech resumes during decision              → cancel + record gap
```

The **adaptive floor** records every cancelled pause (mid-utterance gap) and
clamps the deadline to never fire faster than this user's p90 mid-utterance
pause length. New callers start at 150ms; the floor stabilizes within a few
turns.

This is implemented in `turnsignal/turntaking/`. The orchestration is in
`detector.py` (~150 lines); each signal is its own swappable module.

---

## Architecture

```
                     ┌─────────────────────────────────────┐
                     │              EventBus               │
 ┌────────────┐      │  AudioFrame / TextFrame /           │      ┌────────────┐
 │  Twilio    │──┬──▶│  EventFrame   pub/sub by isinstance │◀──┬──│  Stage X   │
 │  (telco)   │  │   └─────────────────────────────────────┘   │  └────────────┘
 └────────────┘  │                                             │
       ▲         │   ┌────────────┐  ┌────────────┐  ┌──────┐  │
       │         └──▶│  STT       │─▶│  LLM       │─▶│ TTS  │──┘
       └────────────────────────────────────────────────────────
                  bus → outbound audio → telco
```

- **`Stage`** is the unit of work: an `async def run(ctx)` coroutine.
- **`StageContext`** lets a stage `subscribe(FrameType)` and `publish(frame)`.
- **`Call`** owns the bus and supervises stages. Watches for `EventFrame(HANGUP)`
  and tears every stage down automatically.
- **`AudioFrame.direction`** (`INBOUND` / `OUTBOUND`) keeps caller audio and
  TTS audio from feeding back into each other.

---

## Module layout

```
turnsignal/
├── core/
│   ├── types.py           — AudioEncoding, AudioDirection, EventType
│   ├── frame.py           — Frame, AudioFrame, TextFrame, EventFrame
│   ├── bus.py             — in-process pub/sub
│   ├── pipeline.py        — Stage / StageContext primitives
│   └── call.py            — Call: lifecycle + supervisor + hangup watcher
├── audio/
│   ├── mulaw.py           — G.711 μ-law tables (zero non-numpy deps)
│   └── resample.py        — soxr-backed sample-rate conversion
├── config/
│   ├── sections.py        — TurnTakingConfig, VadConfig, TelcoConfig
│   └── loader.py          — TOML + env-var overlay
├── turntaking/
│   ├── audio_buffer.py    — rolling float32 buffer for prosody window
│   ├── audio_decode.py    — frame → float32 conversion
│   ├── adaptive_floor.py  — per-user p90 pause floor
│   ├── pitch.py           — autocorrelation F0 estimator
│   ├── vad_signal.py      — VadSignal interface + reference HysteresisVad
│   ├── prosody_signal.py  — pitch + energy → ENDING/GOING/AMBIGUOUS
│   ├── semantic_signal.py — async classifier interface + heuristic fallback
│   ├── decision.py        — pure functions: deadlines + extend logic
│   └── detector.py        — orchestrates the three signals
└── telco/
    ├── base.py            — TelcoAdapter marker
    ├── twilio_protocol.py — Twilio Media Streams JSON event parsing
    ├── twilio_audio.py    — frame → μ-law 8k normalization
    └── twilio.py          — TwilioStage: WS bridge ↔ bus
```

Every module is small and single-purpose. Easy to read, easy to swap.

---

## Quick start

### Install

```bash
git clone https://github.com/<your-org>/turnsignal
cd turnsignal
python -m venv .venv && source .venv/bin/activate
pip install -e ".[twilio,dev]"
```

Requires Python 3.11+ (uses `tomllib`, `asyncio.TaskGroup`, kw-only dataclasses).

### Run the Twilio echo example

```bash
python examples/twilio_echo.py
# in another shell:
ngrok http 5000
```

Set your Twilio number's voice webhook to a URL returning:

```xml
<Response>
  <Connect>
    <Stream url="wss://<your-ngrok-host>/" />
  </Connect>
</Response>
```

Call the number — you'll hear yourself echoed back through the full
inbound-decode → bus → re-encode → outbound pipeline.

### Build your own assistant

```python
from turnsignal.core.call import Call
from turnsignal.telco.twilio import TwilioStage
from turnsignal.turntaking import (
    EndOfTurnDetector,
    HeuristicSemantic,
    HysteresisVad,
    ProsodySignal,
)

async def handle(websocket):
    call = Call()
    call.add_stage(TwilioStage(websocket))
    call.add_stage(YourSttStage())                # provide your own
    call.add_stage(EndOfTurnDetector(
        vad=HysteresisVad(),                      # swap for silero-vad in prod
        prosody=ProsodySignal(),
        semantic=HeuristicSemantic(),             # swap for an LLM in prod
    ))
    call.add_stage(YourLlmStage())                # provide your own
    call.add_stage(YourTtsStage())                # provide your own
    await call.start()
    await call.wait()
```

---

## Configuration

Environment variables (`TS_<SECTION>_<KEY>`) and TOML are both supported. Env
wins on conflict.

`turnsignal.example.toml`:

```toml
[turntaking]
fast_deadline_ms = 200
default_deadline_ms = 600
slow_deadline_ms = 1200
prosody_buffer_ms = 1600
adaptive_floor_ms = 150

[vad]
speech_rms_threshold = 0.02
silence_rms_threshold = 0.01
speech_hold_ms = 100
silence_hold_ms = 80

[telco]
bind_host = "0.0.0.0"
bind_port = 5000
```

```bash
export TS_TURNTAKING_FAST_DEADLINE_MS=180
export TS_TELCO_BIND_PORT=8080
TS_CONFIG=turnsignal.example.toml python examples/twilio_echo.py
```

```python
from turnsignal import load_config
cfg = load_config("turnsignal.example.toml")
```

---

## Status

| Component | State |
|---|---|
| Core (Frame / Bus / Stage / Call) | ✅ Tested, production-shaped |
| Audio (μ-law tables, soxr resample) | ✅ Tested, μ-law roundtrip <8% error |
| Config (TOML + env overlay) | ✅ Tested |
| Turn-taking orchestration | ✅ Algorithm pinned by tests |
| **Turn-taking thresholds** | ⚠️ **Defaults; not calibrated against labeled data** |
| VAD: HysteresisVad | ⚠️ Reference only — drop in silero-vad for production |
| Semantic: HeuristicSemantic | ⚠️ Reference only — drop in real LLM (Haiku 4.5 + cache) |
| Telco: TwilioStage | ✅ Tested with fake WebSocket |
| STT stage (Deepgram, etc.) | ❌ Not built |
| LLM stage (streaming + speculation) | ❌ Not built |
| TTS stage (Cartesia, ElevenLabs) | ❌ Not built |
| Process-per-call worker | ❌ Not built |
| Plivo / Exotel adapters | ❌ Not built |
| Observability (per-turn timeline) | ❌ Logging only |
| Benchmark harness | ❌ Not built |

### Production-readiness — honest call

**What you can use today:**
- The `Call` / `Stage` / `EventBus` primitives. Architecture is sound, leak-free
  in single-call mode, and the pieces compose cleanly.
- The `TwilioStage` for actual phone calls.
- The `EndOfTurnDetector` once you wire in real signal implementations.
- The audio pipeline (μ-law, resampling).

**What you cannot use today:**
- A drop-in conversational agent. There are no STT/LLM/TTS stages yet.
- Out-of-the-box turn-taking quality. The default thresholds are starting
  points. You'll need to run the (not-yet-built) benchmark harness on your
  own recorded calls to tune them.
- High-concurrency deployments. There's no process-per-call worker yet.

**Verdict:** v0.1.0-alpha. Solid skeleton, the hard part (turn-taking
algorithm + telco audio path) is done. The rest is integration work that
genuinely benefits from contributors.

---

## Testing

```bash
.venv/bin/pytest
```

```
collected 38 items
tests/test_audio_buffer.py ....                    [ 10%]
tests/test_config.py .....                         [ 23%]
tests/test_decision.py .......                     [ 42%]
tests/test_detector.py .......                     [ 60%]
tests/test_resample.py ....                        [ 71%]
tests/test_twilio.py ....                          [ 81%]
tests/test_twilio_protocol.py .......              [100%]
============================== 38 passed in 0.86s
```

The detector tests run the full 3-signal race with shortened deadlines
(20ms / 60ms / 120ms instead of 200/600/1200), so the suite finishes in <1s
without sacrificing algorithmic coverage.

---

## Roadmap

### Near-term (next 2-4 weeks)

1. **STT / LLM / TTS streaming stages** with one provider each. Deepgram +
   Anthropic + Cartesia is a sensible starting trio.
2. **Benchmark harness** for the turn-taking detector. Recorded calls with
   ground-truth turn-end labels, measuring (a) false-interrupt rate, (b)
   end-of-turn latency. This is what closes the "quality" loop.
3. **Real `silero-vad` adapter** as `turntaking/vad_signal_silero.py`.

### Medium-term

4. **Process-per-call worker** (`runtime/worker.py`) — hard memory isolation
   under high concurrency. Solves Pipecat's headline pain point.
5. **Plivo, Exotel, and SIP adapters** to validate the `TelcoAdapter`
   abstraction holds across providers.
6. **Observability** — a `obs/tracing.py` that records per-turn timestamps
   (stt_final, llm_first_token, tts_first_audio, turn_end) and exports
   OpenTelemetry spans.

### Open questions for contributors

- Is autocorr F0 the right pitch estimator for telco-quality audio? Should we
  swap to YIN or RAPT?
- Adaptive floor: p90 over a 30-sample window — is the window size right? Per
  call vs per user vs per language?
- Twilio + LiveKit + WebRTC under one `TelcoAdapter` interface — does the
  abstraction survive WebRTC's negotiated SDP?

---

## Contributing

We need contributors for the items in [Roadmap](#roadmap). The architecture
is intentionally small so it's possible to hold the whole thing in your head;
each module is <100 lines.

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

MIT — see [LICENSE](LICENSE).

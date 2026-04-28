# Contributing to turnsignal

Thanks for your interest. This is an early-stage project; the architecture is
deliberately small so it's possible to hold the whole thing in your head.

## Getting set up

```bash
git clone https://github.com/<your-org>/turnsignal
cd turnsignal
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,twilio]"
pytest
```

You should see 38 tests pass in under a second.

## What we need help with

In rough order of leverage:

1. **STT / LLM / TTS streaming stages.** One provider each is enough to start
   (Deepgram, Anthropic, Cartesia is a sensible trio). Each stage is a
   `Stage` subclass; see `telco/twilio.py` for the shape.
2. **Benchmark harness for turn-taking.** A script that replays recorded
   calls with ground-truth turn-end labels and reports false-interrupt rate
   and end-of-turn latency. This is the *quality* feedback loop and the
   thing the README needs to graph.
3. **`silero-vad` adapter** as `turntaking/vad_signal_silero.py` implementing
   `VadSignal`. Drop-in replacement for `HysteresisVad`.
4. **Process-per-call worker** at `runtime/worker.py`. Hard memory isolation
   under high concurrency.
5. **Plivo / Exotel / SIP adapters** under `telco/`.
6. **Per-turn observability** at `obs/tracing.py` — OpenTelemetry spans for
   `stt_final`, `llm_first_token`, `tts_first_audio`, `turn_end`.

## Code style

- **snake_case** for variables and functions. **PascalCase** for classes.
  **UPPER_SNAKE** for module-level constants.
- **One concern per module.** If a file is doing two things, split it.
  `core/types.py` (enums) and `core/frame.py` (frames) are intentionally
  separate.
- **No comments unless they explain *why*.** If the comment describes *what*
  the code does, the code should be clearer instead.
- **`#----------#` separator after every function/method.** Visual structure
  matters when reviewing diffs.
- **No `print`.** Use `logging.getLogger(__name__)`.
- **No backwards-compat shims.** This is v0.1.x; we'll break things if it
  improves the design.

## Tests

- Every new module gets a `tests/test_<module>.py`.
- Tests live in `tests/`. Library code does not import test code.
- Async tests use `pytest-asyncio` (mode = auto, configured in pyproject).
- For deadline-based code (the detector), pass shortened deadlines via the
  constructor so tests run in milliseconds, not seconds. See
  `tests/test_detector.py` for the pattern.

## Pull request checklist

- [ ] `pytest` passes.
- [ ] `ruff check turnsignal tests` is clean.
- [ ] New modules are <150 lines. If yours is bigger, split it.
- [ ] PR description says *why*, not *what*.

## Licensing

By contributing, you agree your contribution is licensed under the MIT
license, the same as the rest of the project.

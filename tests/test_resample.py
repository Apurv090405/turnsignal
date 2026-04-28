import numpy as np

from turnsignal.audio.mulaw import mulaw_to_pcm16, pcm16_to_mulaw
from turnsignal.audio.resample import resample


def test_mulaw_roundtrip_bounded_error():
    rng = np.random.default_rng(seed=0)
    pcm = rng.integers(-30000, 30000, size=2000, dtype=np.int16)
    encoded = pcm16_to_mulaw(pcm)
    decoded = mulaw_to_pcm16(encoded)
    rel_err = np.abs(decoded.astype(np.int32) - pcm.astype(np.int32)) / (
        np.abs(pcm).astype(np.int32) + 1
    )
    assert float(np.percentile(rel_err, 99)) < 0.10
#----------#


def test_mulaw_silence_roundtrip():
    pcm = np.zeros(160, dtype=np.int16)
    decoded = mulaw_to_pcm16(pcm16_to_mulaw(pcm))
    assert np.max(np.abs(decoded)) <= 8
#----------#


def test_resample_8k_to_16k_doubles_length():
    pcm = (np.sin(np.linspace(0, 2 * np.pi * 100, 800)) * 10000).astype(np.int16)
    out = resample(pcm, 8000, 16000)
    assert abs(out.size - 1600) <= 4
    assert out.dtype == np.int16
#----------#


def test_resample_noop_when_rates_match():
    pcm = np.arange(160, dtype=np.int16)
    out = resample(pcm, 8000, 8000)
    assert np.array_equal(out, pcm)
#----------#

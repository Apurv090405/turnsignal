import numpy as np

from turnsignal.turntaking.audio_buffer import RollingAudioBuffer


def test_tail_returns_empty_when_buffer_empty():
    buf = RollingAudioBuffer(max_samples=1000)
    assert buf.tail(100).size == 0
#----------#


def test_tail_returns_last_n_samples():
    buf = RollingAudioBuffer(max_samples=1000)
    buf.write(np.arange(500, dtype=np.float32))
    out = buf.tail(100)
    assert out.size == 100
    assert out[0] == 400
    assert out[-1] == 499
#----------#


def test_evicts_old_chunks_past_max():
    buf = RollingAudioBuffer(max_samples=300)
    for i in range(10):
        buf.write(np.full(100, i, dtype=np.float32))
    out = buf.tail(300)
    assert out.size == 300
    assert out[0] >= 7
#----------#


def test_tail_smaller_than_total_returns_only_tail():
    buf = RollingAudioBuffer(max_samples=1000)
    buf.write(np.arange(800, dtype=np.float32))
    out = buf.tail(50)
    assert out.size == 50
    assert out[-1] == 799
#----------#

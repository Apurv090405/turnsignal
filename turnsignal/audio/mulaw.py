from __future__ import annotations

import numpy as np


def _build_decode_table() -> np.ndarray:
    table = np.zeros(256, dtype=np.int16)
    for i in range(256):
        u = ~i & 0xFF
        sign = u & 0x80
        exponent = (u >> 4) & 0x07
        mantissa = u & 0x0F
        sample = ((mantissa << 3) + 0x84) << exponent
        sample -= 0x84
        table[i] = -sample if sign else sample
    return table
#----------#


def _build_encode_table() -> np.ndarray:
    bias = 0x84
    clip = 32635
    table = np.zeros(65536, dtype=np.uint8)
    for pcm in range(-32768, 32768):
        sign = 0x80 if pcm < 0 else 0
        sample = min(abs(pcm), clip) + bias
        exponent = 7
        for mask in (0x4000, 0x2000, 0x1000, 0x0800, 0x0400, 0x0200, 0x0100):
            if sample & mask:
                break
            exponent -= 1
        mantissa = (sample >> (exponent + 3)) & 0x0F
        ulaw = ~(sign | (exponent << 4) | mantissa) & 0xFF
        table[pcm + 32768] = ulaw
    return table
#----------#


_DECODE_TABLE = _build_decode_table()
_ENCODE_TABLE = _build_encode_table()


def mulaw_to_pcm16(mulaw_bytes: bytes) -> np.ndarray:
    return _DECODE_TABLE[np.frombuffer(mulaw_bytes, dtype=np.uint8)]
#----------#


def pcm16_to_mulaw(pcm16: np.ndarray) -> bytes:
    indices = np.clip(pcm16.astype(np.int32) + 32768, 0, 65535)
    return _ENCODE_TABLE[indices].tobytes()
#----------#

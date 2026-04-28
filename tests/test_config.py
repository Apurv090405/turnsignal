from __future__ import annotations

import os

import pytest

from turnsignal.config import load_config


def test_defaults_when_no_path_no_env():
    cfg = load_config()
    assert cfg.turntaking.fast_deadline_ms == 200.0
    assert cfg.vad.speech_rms_threshold == 0.02
    assert cfg.telco.bind_port == 5000
#----------#


def test_toml_overrides_defaults(tmp_path):
    p = tmp_path / "cfg.toml"
    p.write_text(
        """
[turntaking]
fast_deadline_ms = 100

[telco]
bind_host = "127.0.0.1"
bind_port = 9000
"""
    )
    cfg = load_config(p)
    assert cfg.turntaking.fast_deadline_ms == 100.0
    assert cfg.turntaking.default_deadline_ms == 600.0
    assert cfg.telco.bind_host == "127.0.0.1"
    assert cfg.telco.bind_port == 9000
#----------#


def test_env_overrides_toml(tmp_path, monkeypatch):
    p = tmp_path / "cfg.toml"
    p.write_text("[turntaking]\nfast_deadline_ms = 100\n")
    monkeypatch.setenv("TS_TURNTAKING_FAST_DEADLINE_MS", "75")
    cfg = load_config(p)
    assert cfg.turntaking.fast_deadline_ms == 75.0
#----------#


def test_env_only(monkeypatch):
    monkeypatch.setenv("TS_TELCO_BIND_PORT", "8080")
    cfg = load_config()
    assert cfg.telco.bind_port == 8080
#----------#


def test_env_string_coerced_to_float(monkeypatch):
    monkeypatch.setenv("TS_VAD_SPEECH_RMS_THRESHOLD", "0.05")
    cfg = load_config()
    assert cfg.vad.speech_rms_threshold == pytest.approx(0.05)
#----------#

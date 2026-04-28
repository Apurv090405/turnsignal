from __future__ import annotations

import os
import tomllib
import typing
from dataclasses import dataclass, field, fields
from pathlib import Path

from turnsignal.config.sections import (
    TelcoConfig,
    TurnTakingConfig,
    VadConfig,
)


@dataclass(frozen=True, kw_only=True)
class Config:
    turntaking: TurnTakingConfig = field(default_factory=TurnTakingConfig)
    vad: VadConfig = field(default_factory=VadConfig)
    telco: TelcoConfig = field(default_factory=TelcoConfig)
#----------#


_SECTIONS = {
    "turntaking": TurnTakingConfig,
    "vad": VadConfig,
    "telco": TelcoConfig,
}


def load_config(path: str | Path | None = None, env_prefix: str = "TS_") -> Config:
    raw = _read_toml(path) if path else {}
    raw = _overlay_env(raw, env_prefix)
    return _materialize(raw)
#----------#


def _read_toml(path: str | Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)
#----------#


def _overlay_env(base: dict, prefix: str) -> dict:
    out: dict = {k: dict(v) if isinstance(v, dict) else v for k, v in base.items()}
    for raw_key, raw_val in os.environ.items():
        if not raw_key.startswith(prefix):
            continue
        section, _, key = raw_key[len(prefix):].lower().partition("_")
        if not key:
            continue
        out.setdefault(section, {})[key] = raw_val
    return out
#----------#


def _materialize(raw: dict) -> Config:
    parts: dict = {}
    for name, klass in _SECTIONS.items():
        parts[name] = _coerce(klass, raw.get(name, {}))
    return Config(**parts)
#----------#


def _coerce(klass, raw: dict):
    hints = typing.get_type_hints(klass)
    typed: dict = {}
    for f in fields(klass):
        if f.name not in raw:
            continue
        value = raw[f.name]
        t = hints[f.name]
        typed[f.name] = value if isinstance(value, t) else t(value)
    return klass(**typed)
#----------#

"""Configuration loading and validation for the AMT pipeline."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

FEATURE_VERSION = "amt-v2"
LABEL_VERSION = "tick-horizon-v1"

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "default.toml"


class ConfigError(ValueError):
    """Raised when the configuration file is missing or invalid."""


@dataclass(frozen=True)
class InstrumentConfig:
    symbol: str = "EURUSD"
    active_id: int | None = None
    pip_size: float = 0.0001
    bin_size: float = 0.00005


@dataclass(frozen=True)
class CandleConfig:
    interval_seconds: int = 60


@dataclass(frozen=True)
class ContextConfig:
    macro_candles: int = 7
    fast_candles: int = 3
    profile_min_ticks: int = 30
    value_area_target: float = 0.70
    tail_bins: int = 3
    single_print_max_ticks: int = 1
    volatility_min_changes: int = 10
    epsilon: float = 1e-9


@dataclass(frozen=True)
class LabelConfig:
    horizons_seconds: tuple[int, ...] = (60, 90, 120, 180)
    exit_tolerance_seconds: float = 5.0
    tie_policy: str = "exclude"


@dataclass(frozen=True)
class DataConfig:
    input_path: str = "data/ticks.csv"
    features_path: str = "data/features.csv"
    labels_path: str = "data/labels.csv"


@dataclass(frozen=True)
class Config:
    instrument: InstrumentConfig = field(default_factory=InstrumentConfig)
    candles: CandleConfig = field(default_factory=CandleConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    labels: LabelConfig = field(default_factory=LabelConfig)
    data: DataConfig = field(default_factory=DataConfig)
    feature_version: str = FEATURE_VERSION
    label_version: str = LABEL_VERSION


def _build_section(cls: type, raw: Any, name: str) -> Any:
    if raw is None:
        return cls()
    if not isinstance(raw, dict):
        raise ConfigError(f"[{name}] must be a table")
    known = {f.name for f in fields(cls)}
    unknown = sorted(set(raw) - known)
    if unknown:
        raise ConfigError(f"unknown keys in [{name}]: {unknown}")
    return cls(**raw)


def _validate(config: Config) -> None:
    instrument = config.instrument
    if instrument.pip_size <= 0:
        raise ConfigError("instrument.pip_size must be positive")
    if instrument.bin_size <= 0:
        raise ConfigError("instrument.bin_size must be positive")
    if instrument.active_id is not None and instrument.active_id < 0:
        raise ConfigError("instrument.active_id must be non-negative")

    if config.candles.interval_seconds < 1:
        raise ConfigError("candles.interval_seconds must be at least 1")

    context = config.context
    if context.macro_candles < 1:
        raise ConfigError("context.macro_candles must be at least 1")
    if context.fast_candles < 1:
        raise ConfigError("context.fast_candles must be at least 1")
    if context.fast_candles > context.macro_candles:
        raise ConfigError("context.fast_candles must not exceed context.macro_candles")
    if context.profile_min_ticks < 1:
        raise ConfigError("context.profile_min_ticks must be at least 1")
    if not 0 < context.value_area_target <= 1:
        raise ConfigError("context.value_area_target must be in (0, 1]")
    if context.tail_bins < 1:
        raise ConfigError("context.tail_bins must be at least 1")
    if context.single_print_max_ticks < 0:
        raise ConfigError("context.single_print_max_ticks must be non-negative")
    if context.volatility_min_changes < 1:
        raise ConfigError("context.volatility_min_changes must be at least 1")
    if context.epsilon <= 0:
        raise ConfigError("context.epsilon must be positive")

    labels = config.labels
    if not labels.horizons_seconds:
        raise ConfigError("labels.horizons_seconds must not be empty")
    if any(horizon <= 0 for horizon in labels.horizons_seconds):
        raise ConfigError("labels.horizons_seconds must all be positive")
    if list(labels.horizons_seconds) != sorted(set(labels.horizons_seconds)):
        raise ConfigError("labels.horizons_seconds must be unique and ascending")
    if labels.exit_tolerance_seconds < 0:
        raise ConfigError("labels.exit_tolerance_seconds must be non-negative")
    if labels.tie_policy not in {"exclude", "keep"}:
        raise ConfigError("labels.tie_policy must be 'exclude' or 'keep'")


def load_config(path: str | Path | None = None) -> Config:
    """Load and validate a TOML configuration file."""

    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not config_path.is_file():
        raise ConfigError(f"configuration file not found: {config_path}")

    with config_path.open("rb") as handle:
        raw = tomllib.load(handle)

    labels_raw = dict(raw.get("labels", {}))
    if "horizons_seconds" in labels_raw:
        labels_raw["horizons_seconds"] = tuple(labels_raw["horizons_seconds"])

    config = Config(
        instrument=_build_section(InstrumentConfig, raw.get("instrument"), "instrument"),
        candles=_build_section(CandleConfig, raw.get("candles"), "candles"),
        context=_build_section(ContextConfig, raw.get("context"), "context"),
        labels=_build_section(LabelConfig, labels_raw, "labels"),
        data=_build_section(DataConfig, raw.get("data"), "data"),
    )
    _validate(config)
    return config

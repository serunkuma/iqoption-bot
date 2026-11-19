"""Configuration loading and validation.

One TOML file configures the whole engine. Every section is validated at
startup so a typo or an impossible combination fails loudly instead of
producing silent research artefacts.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

FEATURE_VERSION = "amt-v3"
CORE_FEATURE_VERSION = "core16-v1"
LABEL_VERSION = "snapshot-horizon-v1"
CANDLE_VERSION = "1m-clock-v1"

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
class SnapshotConfig:
    offsets_seconds: tuple[int, ...] = (30,)
    entry_delay_ms: int = 250
    entry_tolerance_seconds: float = 1.0
    exit_tolerance_seconds: float = 5.0
    min_ticks_per_bar: int = 1


@dataclass(frozen=True)
class LabelConfig:
    horizons_seconds: tuple[int, ...] = (60, 90, 120, 180)
    tie_policy: str = "exclude"


@dataclass(frozen=True)
class RouterConfig:
    min_ev: float = 0.03
    payouts: tuple[tuple[int, float], ...] = (
        (60, 0.80),
        (90, 0.82),
        (120, 0.84),
        (180, 0.86),
    )
    tie_break: str = "earliest_horizon"

    def payout(self, horizon: int) -> float:
        for key, value in self.payouts:
            if key == horizon:
                return value
        raise ConfigError(f"no payout configured for horizon {horizon}")


@dataclass(frozen=True)
class ModelConfig:
    engine: str = "lightgbm"
    calibration: str = "auto"
    purge_seconds: int = 180
    embargo_seconds: int = 0
    n_splits: int = 5
    min_train_rows: int = 500
    random_seed: int = 7
    n_estimators: int = 300
    learning_rate: float = 0.03
    num_leaves: int = 15
    min_child_samples: int = 50


@dataclass(frozen=True)
class ExecutionConfig:
    mode: str = "paper"
    stake: float = 1.0
    max_open_trades: int = 1


@dataclass(frozen=True)
class StoreConfig:
    root: str = "data"
    ticks_path: str = "data/ticks.parquet"
    snapshots_path: str = "data/snapshots.parquet"
    models_path: str = "data/models"
    reports_path: str = "reports"


@dataclass(frozen=True)
class DataConfig:
    input_path: str = "data/ticks.csv"


@dataclass(frozen=True)
class Config:
    instrument: InstrumentConfig = field(default_factory=InstrumentConfig)
    candles: CandleConfig = field(default_factory=CandleConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    snapshot: SnapshotConfig = field(default_factory=SnapshotConfig)
    labels: LabelConfig = field(default_factory=LabelConfig)
    router: RouterConfig = field(default_factory=RouterConfig)
    models: ModelConfig = field(default_factory=ModelConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    store: StoreConfig = field(default_factory=StoreConfig)
    data: DataConfig = field(default_factory=DataConfig)
    feature_version: str = FEATURE_VERSION
    core_feature_version: str = CORE_FEATURE_VERSION
    label_version: str = LABEL_VERSION
    candle_version: str = CANDLE_VERSION


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


def _coerce_payouts(raw: Any) -> tuple[tuple[int, float], ...]:
    if not isinstance(raw, dict):
        raise ConfigError("[router.payouts] must be a table of horizon = payout")
    pairs: list[tuple[int, float]] = []
    for key, value in raw.items():
        try:
            horizon = int(key)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"payout key {key!r} is not an integer horizon") from exc
        if not isinstance(value, (int, float)):
            raise ConfigError(f"payout for {horizon}s must be numeric")
        pairs.append((horizon, float(value)))
    return tuple(sorted(pairs))


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

    snapshot = config.snapshot
    if not snapshot.offsets_seconds:
        raise ConfigError("snapshot.offsets_seconds must not be empty")
    interval = config.candles.interval_seconds
    for offset in snapshot.offsets_seconds:
        if not 0 <= offset < interval:
            raise ConfigError(
                f"snapshot offset {offset} must be in [0, {interval}) seconds"
            )
    if len(set(snapshot.offsets_seconds)) != len(snapshot.offsets_seconds):
        raise ConfigError("snapshot.offsets_seconds must be unique")
    if snapshot.entry_delay_ms < 0:
        raise ConfigError("snapshot.entry_delay_ms must be non-negative")
    if snapshot.entry_tolerance_seconds < 0:
        raise ConfigError("snapshot.entry_tolerance_seconds must be non-negative")
    if snapshot.exit_tolerance_seconds < 0:
        raise ConfigError("snapshot.exit_tolerance_seconds must be non-negative")
    if snapshot.min_ticks_per_bar < 1:
        raise ConfigError("snapshot.min_ticks_per_bar must be at least 1")

    labels = config.labels
    if not labels.horizons_seconds:
        raise ConfigError("labels.horizons_seconds must not be empty")
    if any(horizon <= 0 for horizon in labels.horizons_seconds):
        raise ConfigError("labels.horizons_seconds must all be positive")
    if list(labels.horizons_seconds) != sorted(set(labels.horizons_seconds)):
        raise ConfigError("labels.horizons_seconds must be unique and ascending")
    if labels.tie_policy not in {"exclude", "keep"}:
        raise ConfigError("labels.tie_policy must be 'exclude' or 'keep'")

    router = config.router
    if router.min_ev < -1 or router.min_ev >= 1:
        raise ConfigError("router.min_ev must be in [-1, 1)")
    if router.tie_break not in {"earliest_horizon", "highest_ev"}:
        raise ConfigError("router.tie_break must be 'earliest_horizon' or 'highest_ev'")
    horizons = set(labels.horizons_seconds)
    for horizon, payout in router.payouts:
        if payout <= 0:
            raise ConfigError(f"payout for horizon {horizon} must be positive")
        if horizon not in horizons:
            raise ConfigError(
                f"payout configured for horizon {horizon} that is not in labels.horizons_seconds"
            )
    missing = sorted(horizons - {horizon for horizon, _ in router.payouts})
    if missing:
        raise ConfigError(f"no payout configured for horizons {missing}")

    models = config.models
    if models.engine not in {"lightgbm", "sklearn"}:
        raise ConfigError("models.engine must be 'lightgbm' or 'sklearn'")
    if models.calibration not in {"auto", "isotonic", "platt", "none"}:
        raise ConfigError(
            "models.calibration must be 'auto', 'isotonic', 'platt', or 'none'"
        )
    if models.purge_seconds < 0:
        raise ConfigError("models.purge_seconds must be non-negative")
    if models.embargo_seconds < 0:
        raise ConfigError("models.embargo_seconds must be non-negative")
    if models.n_splits < 2:
        raise ConfigError("models.n_splits must be at least 2")
    if models.min_train_rows < 1:
        raise ConfigError("models.min_train_rows must be at least 1")

    execution = config.execution
    if execution.mode not in {"paper", "demo", "live"}:
        raise ConfigError("execution.mode must be 'paper', 'demo', or 'live'")
    if execution.stake <= 0:
        raise ConfigError("execution.stake must be positive")
    if execution.max_open_trades < 1:
        raise ConfigError("execution.max_open_trades must be at least 1")


def _read(path: str | Path | None) -> dict[str, Any]:
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not config_path.is_file():
        raise ConfigError(f"configuration file not found: {config_path}")
    with config_path.open("rb") as handle:
        return tomllib.load(handle)


def load_config(path: str | Path | None = None) -> Config:
    """Load and validate a TOML configuration file."""

    raw = _read(path)

    labels_raw = dict(raw.get("labels", {}))
    if "horizons_seconds" in labels_raw:
        labels_raw["horizons_seconds"] = tuple(labels_raw["horizons_seconds"])

    snapshot_raw = dict(raw.get("snapshot", {}))
    if "offsets_seconds" in snapshot_raw:
        snapshot_raw["offsets_seconds"] = tuple(snapshot_raw["offsets_seconds"])

    router_raw = dict(raw.get("router", {}))
    if "payouts" in router_raw:
        router_raw["payouts"] = _coerce_payouts(router_raw["payouts"])

    config = Config(
        instrument=_build_section(InstrumentConfig, raw.get("instrument"), "instrument"),
        candles=_build_section(CandleConfig, raw.get("candles"), "candles"),
        context=_build_section(ContextConfig, raw.get("context"), "context"),
        snapshot=_build_section(SnapshotConfig, snapshot_raw, "snapshot"),
        labels=_build_section(LabelConfig, labels_raw, "labels"),
        router=_build_section(RouterConfig, router_raw, "router"),
        models=_build_section(ModelConfig, raw.get("models"), "models"),
        execution=_build_section(ExecutionConfig, raw.get("execution"), "execution"),
        store=_build_section(StoreConfig, raw.get("store"), "store"),
        data=_build_section(DataConfig, raw.get("data"), "data"),
    )
    _validate(config)
    return config


def config_hash(config: Config) -> str:
    """Return a stable short hash of the resolved configuration."""

    import hashlib
    import json

    payload = {
        f.name: getattr(config, f.name)
        for f in fields(config)
    }
    text = json.dumps(payload, default=str, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

"""Shared fixtures for the engine test suite."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from engine.config import (
    CandleConfig,
    Config,
    ContextConfig,
    InstrumentConfig,
    LabelConfig,
    RouterConfig,
    SnapshotConfig,
)
from engine.domain.timeframes import Tick

BASE = datetime(2026, 11, 18, 12, 0, 0, tzinfo=timezone.utc)


def make_config(
    *,
    context: dict | None = None,
    snapshot: dict | None = None,
    labels: dict | None = None,
    router: dict | None = None,
    execution: dict | None = None,
    models: dict | None = None,
) -> Config:
    context_values = {
        "macro_candles": 3,
        "fast_candles": 2,
        "profile_min_ticks": 5,
        "value_area_target": 0.70,
        "tail_bins": 2,
        "single_print_max_ticks": 1,
        "volatility_min_changes": 3,
    }
    context_values.update(context or {})

    snapshot_values = {
        "entry_delay_ms": 250,
        "entry_tolerance_seconds": 2.0,
        "exit_tolerance_seconds": 5.0,
        "min_ticks_per_bar": 1,
    }
    snapshot_values.update(snapshot or {})

    label_values = {"horizons_seconds": (60, 90), "tie_policy": "exclude"}
    label_values.update(labels or {})

    router_values = {
        "min_ev": 0.03,
        "payouts": ((60, 0.80), (90, 0.80)),
        "tie_break": "earliest_horizon",
    }
    router_values.update(router or {})

    from engine.config import ExecutionConfig, ModelConfig

    execution_values = {
        "mode": "paper",
        "stake": 1.0,
        "max_open_trades": 1,
        "cooldown_seconds": 0,
        "daily_loss_limit": None,
    }
    execution_values.update(execution or {})

    model_values = {
        "engine": "sklearn",
        "calibration": "auto",
        "purge_seconds": 0,
        "n_splits": 2,
        "min_train_rows": 20,
        "n_estimators": 20,
        "num_leaves": 4,
        "min_child_samples": 5,
    }
    model_values.update(models or {})

    return Config(
        instrument=InstrumentConfig(
            symbol="EURUSD", active_id=0, pip_size=0.0001, bin_size=0.001
        ),
        candles=CandleConfig(interval_seconds=60),
        context=ContextConfig(**context_values),
        snapshot=SnapshotConfig(**snapshot_values),
        labels=LabelConfig(**label_values),
        router=RouterConfig(**router_values),
        models=ModelConfig(**model_values),
        execution=ExecutionConfig(**execution_values),
    )


def synthetic_ticks(
    minutes: int = 12,
    per_minute: int = 60,
    base_price: float = 1.0,
    step: float = 0.0001,
    start: datetime = BASE,
) -> list[Tick]:
    """Deterministic, strictly rising ticks with one tick per second."""

    ticks: list[Tick] = []
    for minute in range(minutes):
        for second in range(per_minute):
            offset = minute * 60 + second * (60 // per_minute)
            price = base_price + (minute * per_minute + second) * step
            ticks.append(Tick(start + timedelta(seconds=offset), price, 0))
    return ticks


def synthetic_walk_ticks(
    minutes: int = 120,
    per_minute: int = 60,
    base_price: float = 1.0,
    start: datetime = BASE,
    seed: int = 7,
) -> list[Tick]:
    """Seeded random-walk ticks that produce both call and put labels."""

    import random

    generator = random.Random(seed)
    price = base_price
    ticks: list[Tick] = []
    for minute in range(minutes):
        for second in range(per_minute):
            if generator.random() < 0.15:
                move = 0.0
            else:
                move = generator.gauss(0.0, 0.00002)
            price = round(price + move, 5)
            ticks.append(
                Tick(start + timedelta(minutes=minute, seconds=second), price, 0)
            )
    return ticks

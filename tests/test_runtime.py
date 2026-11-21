import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

import numpy as np

from engine.config import Config
from engine.execution import LOST, Trade
from engine.features import CORE_FEATURES
from engine.models import (
    Calibrator,
    HorizonMetrics,
    HorizonModel,
    ModelArtifactError,
    ModelSuite,
)
from engine.runtime import RuntimeEngine
from engine.stream import StreamStore

from .helpers import BASE, make_config


class StubEstimator:
    """Deterministic classifier: every row gets the same Call probability."""

    def __init__(self, probability: float) -> None:
        self.probability = probability

    def predict_proba(self, matrix: np.ndarray) -> np.ndarray:
        probability = self.probability
        return np.tile([1.0 - probability, probability], (len(matrix), 1))


def stub_suite(config: Config, probability: float = 0.9) -> ModelSuite:
    models = {}
    for horizon in config.labels.horizons_seconds:
        models[horizon] = HorizonModel(
            horizon_seconds=horizon,
            estimator=StubEstimator(probability),
            calibrator=Calibrator(method="none"),
            feature_names=CORE_FEATURES,
            metrics=HorizonMetrics(horizon_seconds=horizon),
        )
    return ModelSuite(
        models=models,
        feature_names=CORE_FEATURES,
        feature_version=config.feature_version,
        core_feature_version=config.core_feature_version,
        label_version=config.label_version,
        decision_version=config.decision_version,
        candle_version=config.candle_version,
        instrument={
            "symbol": config.instrument.symbol,
            "active_id": config.instrument.active_id,
        },
        artifact_id="sha256:stub",
    )


def payload(moment, price: float) -> dict:
    return {"received_at": moment.isoformat(), "close": price}


def drive(
    store: StreamStore,
    runtime: RuntimeEngine,
    minutes: int,
    *,
    prices=None,
) -> None:
    """Feed one minute at a time with ticks at 0s, 1s, and 30s.

    The 0s tick closes the previous candle; the 1s tick is the first tick after
    the 250ms entry delay.
    """

    for minute in range(minutes):
        for second in (0, 1, 30):
            moment = BASE + timedelta(minutes=minute, seconds=second)
            price = (
                prices(minute, second)
                if prices is not None
                else 1.0 + minute * 0.001 + second * 0.00001
            )
            result = store.ingest(0, payload(moment, price))
            runtime.on_ingest(result)


class RuntimeTests(unittest.TestCase):
    def make_runtime(self, directory, config, suite):
        store = StreamStore(
            Path(directory) / "stream",
            interval_seconds=config.candles.interval_seconds,
            window_size=config.context.macro_candles,
            flush_events=10,
            compression="none",
            active_id=config.instrument.active_id,
        )
        runtime = RuntimeEngine(
            store,
            suite,
            config,
            decisions_dir=Path(directory) / "decisions",
        )
        return store, runtime

    def journal_records(self, directory) -> list[dict]:
        paths = sorted(Path(directory, "decisions").glob("*/*.jsonl"))
        records: list[dict] = []
        for path in paths:
            for line in path.read_text(encoding="utf-8").splitlines():
                records.append(json.loads(line))
        return records

    def test_incompatible_artifact_is_rejected(self) -> None:
        config = make_config()
        with tempfile.TemporaryDirectory() as directory:
            store = StreamStore(
                Path(directory) / "stream", flush_events=10, compression="none"
            )
            with self.assertRaises(ModelArtifactError):
                RuntimeEngine(store, ModelSuite(), config)

    def test_warmup_precedes_the_first_decision(self) -> None:
        config = make_config()
        with tempfile.TemporaryDirectory() as directory:
            store, runtime = self.make_runtime(directory, config, stub_suite(config))
            drive(store, runtime, minutes=8)

            self.assertEqual(runtime.counters.warmup, 2)
            self.assertEqual(runtime.counters.decisions, 7)
            runtime.close()
            store.close()

    def test_a_qualified_decision_opens_a_paper_trade(self) -> None:
        config = make_config()
        with tempfile.TemporaryDirectory() as directory:
            store, runtime = self.make_runtime(directory, config, stub_suite(config))
            drive(store, runtime, minutes=8)

            self.assertGreaterEqual(runtime.counters.trades, 1)
            trades = [t for t in runtime.broker.trades]
            self.assertTrue(trades)
            first = trades[0]
            self.assertEqual(first.direction, "call")
            self.assertAlmostEqual(first.payout, 0.80)
            self.assertEqual(first.status, "won")

            records = self.journal_records(directory)
            self.assertTrue(any(r["action"] == "trade" for r in records))
            self.assertTrue(
                all(r["artifact_id"] == "sha256:stub" for r in records)
            )
            self.assertTrue(
                all(r["decision_version"] == "candle-close-v1" for r in records)
            )
            runtime.close()
            store.close()

    def test_an_open_trade_blocks_the_next_decision(self) -> None:
        config = make_config()
        with tempfile.TemporaryDirectory() as directory:
            store, runtime = self.make_runtime(directory, config, stub_suite(config))
            drive(store, runtime, minutes=8)

            self.assertGreaterEqual(runtime.counters.trade_open, 1)
            reasons = {r["reason"] for r in self.journal_records(directory)}
            self.assertIn("trade_open", reasons)
            runtime.close()
            store.close()

    def test_cooldown_blocks_a_decision_after_a_trade_closes(self) -> None:
        config = make_config(execution={"cooldown_seconds": 3600})
        with tempfile.TemporaryDirectory() as directory:
            store, runtime = self.make_runtime(directory, config, stub_suite(config))
            drive(store, runtime, minutes=8)

            self.assertGreaterEqual(runtime.counters.cooldown, 1)
            reasons = {r["reason"] for r in self.journal_records(directory)}
            self.assertIn("cooldown", reasons)
            runtime.close()
            store.close()

    def test_daily_loss_stop_blocks_decisions(self) -> None:
        config = make_config(execution={"daily_loss_limit": 0.5})
        with tempfile.TemporaryDirectory() as directory:
            store, runtime = self.make_runtime(directory, config, stub_suite(config))
            runtime.broker.trades.append(
                Trade(
                    trade_id=99,
                    snapshot_id=-1,
                    active_id=0,
                    direction="call",
                    horizon_seconds=60,
                    stake=1.0,
                    payout=0.80,
                    entry_timestamp=BASE,
                    entry_price=1.0,
                    expiry_timestamp=BASE + timedelta(seconds=60),
                    expected_value=0.5,
                    status=LOST,
                    exit_price=0.9,
                    resolved_at=BASE + timedelta(seconds=60),
                    pnl=-1.0,
                )
            )
            drive(store, runtime, minutes=8)

            self.assertGreaterEqual(runtime.counters.daily_stop, 1)
            reasons = {r["reason"] for r in self.journal_records(directory)}
            self.assertIn("daily_stop", reasons)
            runtime.close()
            store.close()

    def test_missing_entry_tick_is_journaled(self) -> None:
        config = make_config(snapshot={"entry_tolerance_seconds": 0.1})
        with tempfile.TemporaryDirectory() as directory:
            store, runtime = self.make_runtime(directory, config, stub_suite(config))
            drive(store, runtime, minutes=8)

            self.assertGreaterEqual(runtime.counters.no_entry_tick, 1)
            reasons = {r["reason"] for r in self.journal_records(directory)}
            self.assertIn("no_entry_tick", reasons)
            self.assertEqual(runtime.counters.trades, 0)
            runtime.close()
            store.close()

    def test_low_probability_is_a_no_trade(self) -> None:
        config = make_config()
        with tempfile.TemporaryDirectory() as directory:
            store, runtime = self.make_runtime(
                directory, config, stub_suite(config, probability=0.5)
            )
            drive(store, runtime, minutes=8)

            self.assertEqual(runtime.counters.trades, 0)
            reasons = {r["reason"] for r in self.journal_records(directory)}
            self.assertIn("below_hurdle", reasons)
            runtime.close()
            store.close()


if __name__ == "__main__":
    unittest.main()

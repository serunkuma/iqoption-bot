"""System entry point.

``runner.py`` owns process lifecycle and wiring. It is the only module that
knows about every component; each component stays independently testable.

Modes
-----
serve      capture ticks from the browser extension and persist them to JSONL
build      turn a tick capture into the Parquet store and the labelled dataset
train      train the four calibrated horizon models on a dataset
backtest   replay a dataset through the router and the paper broker
diagnose   print a data-quality report for a capture or store
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from components import receiver
from engine import (
    TickStore,
    build_from_csv,
    build_from_store,
    config_hash,
    load_config,
    run_backtest,
    train_suite,
)
from engine.build import write_artifacts
from engine.config import Config, ConfigError
from engine.reports import build_report, calibration_summary
from engine.store import TickStoreError
from engine.models import ModelSuite

logger = logging.getLogger("iqoption.runner")

SUITE_FILENAME = "suite.pkl"


class JsonlTickSink:
    """Append accepted ticks to a daily JSONL file.

    This is the durable boundary between capture and analysis. The broker's own
    ``at`` field stays inside ``payload`` and is never promoted.
    """

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def __call__(self, active_id, payload: dict) -> None:
        price = payload.get("close")
        if not isinstance(price, (int, float)):
            return
        stamp = payload.get("received_at")
        if not isinstance(stamp, str):
            return
        try:
            moment = datetime.fromisoformat(stamp)
        except ValueError:
            return
        path = self.directory / f"ticks-{moment.date().isoformat()}.jsonl"
        record = {
            "received_at": stamp,
            "active_id": active_id,
            "price": float(price),
            "payload": payload,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str) + "\n")


def _load_store(path: str | Path, config: Config) -> TickStore:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == ".csv":
        return TickStore.from_csv(source, active_id=config.instrument.active_id)
    if suffix == ".jsonl":
        return TickStore.from_jsonl(source, active_id=config.instrument.active_id)
    if suffix == ".parquet":
        return TickStore.from_parquet(source)
    raise TickStoreError(f"unsupported tick input: {source}")


# -- commands --------------------------------------------------------------


def cmd_serve(args: argparse.Namespace, config: Config) -> int:
    if args.raw_dir:
        receiver.set_tick_sink(JsonlTickSink(args.raw_dir))
        logger.info("Persisting accepted ticks to %s", args.raw_dir)
    logger.info(
        "Starting capture only. No candles, features, or signals are produced in this mode."
    )
    receiver.run(args.host, args.port)
    return 0


def cmd_build(args: argparse.Namespace, config: Config) -> int:
    source = args.input or config.data.input_path
    store = _load_store(source, config)
    if store.is_empty:
        print("tick store is empty; nothing to build")
        return 1

    artifacts = build_from_store(store, config)
    paths = write_artifacts(artifacts, config)

    summary = artifacts.summary()
    print("build summary")
    for key, value in summary.items():
        print(f"  {key:<28}: {value}")
    print("artifacts")
    for key, value in paths.items():
        print(f"  {key:<28}: {value}")
    return 0


def cmd_train(args: argparse.Namespace, config: Config) -> int:
    import pandas as pd

    dataset_path = Path(args.dataset or Path(config.store.root) / "dataset.parquet")
    if not dataset_path.is_file():
        print(f"dataset not found: {dataset_path}")
        return 1

    dataset = pd.read_parquet(dataset_path)
    suite = train_suite(dataset, config, config_hash=config_hash(config))

    models_dir = Path(config.store.models_path)
    models_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dated = models_dir / f"suite-{stamp}.pkl"
    suite.save(dated)
    suite.save(models_dir / SUITE_FILENAME)

    print(f"dataset rows   : {len(dataset)}")
    print(f"trained models : {sorted(suite.models)}")
    for horizon, reason in sorted(suite.skipped.items()):
        print(f"skipped {horizon:>4}s      : {reason}")
    for horizon, model in sorted(suite.models.items()):
        metrics = model.metrics
        print(
            f"horizon {horizon:>4}s  rows={metrics.rows} oos={metrics.oos_rows} "
            f"eval={metrics.evaluation_rows} brier={metrics.brier} "
            f"auc={metrics.auc} cal={metrics.calibration}"
        )
        if metrics.calibration_note:
            print(f"                  calibration: {metrics.calibration_note}")
    print(f"suite written  : {models_dir / SUITE_FILENAME}")
    return 0


def cmd_backtest(args: argparse.Namespace, config: Config) -> int:
    import pandas as pd

    dataset_path = Path(args.dataset or Path(config.store.root) / "dataset.parquet")
    suite_path = Path(args.model or Path(config.store.models_path) / SUITE_FILENAME)
    if not dataset_path.is_file():
        print(f"dataset not found: {dataset_path}")
        return 1
    if not suite_path.is_file():
        print(f"model suite not found: {suite_path}")
        return 1

    dataset = pd.read_parquet(dataset_path)
    suite = ModelSuite.load(suite_path)
    result = run_backtest(dataset, suite, config)

    calibration: dict[str, dict] = {}
    if suite.evaluation.empty:
        print(
            "warning: suite has no held-out evaluation rows; "
            "calibration report will be empty"
        )
    else:
        for horizon, group in suite.evaluation.groupby("horizon_seconds", sort=True):
            calibration[str(int(horizon))] = calibration_summary(
                group["label"].to_numpy(dtype=int),
                group["probability"].to_numpy(dtype=float),
            )

    report = build_report(suite, calibration, result.trades, result.summary())
    destination = Path(config.store.reports_path)
    path = report.write(destination, name="backtest")

    print("backtest summary")
    for key, value in result.summary().items():
        print(f"  {key:<28}: {value}")
    print(f"report written               : {path}")
    return 0


def cmd_diagnose(args: argparse.Namespace, config: Config) -> int:
    source = args.input or config.data.input_path
    store = _load_store(source, config)
    print("tick store")
    print(f"  rows                        : {len(store)}")
    print(f"  duplicates dropped          : {store.stats.get('duplicates_dropped', 0)}")
    print(f"  out-of-order rows           : {store.stats.get('out_of_order', 0)}")
    if store.is_empty:
        return 0
    timestamps = store.frame["timestamp"]
    print(f"  first tick                  : {timestamps.iloc[0]}")
    print(f"  last tick                   : {timestamps.iloc[-1]}")
    span = (timestamps.iloc[-1] - timestamps.iloc[0]).total_seconds()
    print(f"  span seconds                : {span:.0f}")
    buckets = store.frame["timestamp"].dt.floor("min").nunique()
    print(f"  minutes with ticks          : {buckets}")
    return 0


# -- argument parsing ------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="runner.py",
        description="IQ Option bot entry point.",
    )
    parser.add_argument("--config", default=None, help="path to a TOML configuration")
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="capture ticks from the browser extension")
    serve.add_argument("--host", default=receiver.HOST)
    serve.add_argument("--port", type=int, default=receiver.PORT)
    serve.add_argument(
        "--raw-dir",
        default="data/raw",
        help="directory for JSONL tick capture; use '' to disable persistence",
    )

    build = sub.add_parser("build", help="build store, snapshots, and dataset")
    build.add_argument("--input", default=None, help="tick CSV, JSONL, or Parquet")

    train = sub.add_parser("train", help="train the horizon model suite")
    train.add_argument("--dataset", default=None)

    backtest = sub.add_parser("backtest", help="replay a dataset through the router")
    backtest.add_argument("--dataset", default=None)
    backtest.add_argument("--model", default=None)

    diagnose = sub.add_parser("diagnose", help="print a data-quality report")
    diagnose.add_argument("--input", default=None)

    return parser


COMMANDS = {
    "serve": cmd_serve,
    "build": cmd_build,
    "train": cmd_train,
    "backtest": cmd_backtest,
    "diagnose": cmd_diagnose,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2

    try:
        return COMMANDS[args.command](args, config)
    except (TickStoreError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        logger.info("Interrupted.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

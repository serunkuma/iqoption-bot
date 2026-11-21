"""System entry point.

``runner.py`` owns process lifecycle and wiring. It is the only module that
knows about every component; each component stays independently testable.

Modes
-----
serve        stream ticks into the hourly Parquet store and make candle-close decisions
build        turn a tick capture into the Parquet store and the labelled dataset
train        train the four calibrated horizon models and write a .joblib artifact
backtest     replay a dataset through the router and the paper broker
model-check  validate a runtime artifact and print its manifest
replay       rebuild candles from raw events and compare them with the store
diagnose     print a data-quality report for a capture or store
docs-check   validate documentation status labels, links, and index coverage
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from components import receiver
from engine import (
    ModelArtifactError,
    ModelSuite,
    RuntimeEngine,
    TickStore,
    build_from_store,
    config_hash,
    load_config,
    replay_from_dirs,
    run_backtest,
    train_suite,
)
from engine.build import write_artifacts
from engine.config import Config, ConfigError
from engine.execution import TradeJournal
from engine.reports import build_report, calibration_summary
from engine.store import TickStoreError
from engine.stream import StreamBufferError, StreamStore

logger = logging.getLogger("iqoption.runner")

RUNTIME_FILENAME = "suite.joblib"
LEGACY_FILENAME = "suite.pkl"


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


def _find_model(config: Config, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    models_dir = Path(config.store.models_path)
    runtime = Path(config.models.runtime_path)
    if runtime.is_file():
        return runtime
    candidates = sorted(models_dir.glob("suite-*.joblib"))
    if candidates:
        return candidates[-1]
    legacy = models_dir / LEGACY_FILENAME
    if legacy.is_file():
        return legacy
    return runtime


# -- commands --------------------------------------------------------------


def cmd_serve(args: argparse.Namespace, config: Config) -> int:
    root = args.stream_dir or config.stream.root
    suite: ModelSuite | None = None

    if not args.capture_only:
        model_path = Path(args.model or config.models.runtime_path)
        try:
            suite = ModelSuite.load(model_path, require_manifest=True)
        except ModelArtifactError as exc:
            print(f"model artifact error: {exc}", file=sys.stderr)
            return 1
        problems = suite.validate(config)
        if problems:
            print("model artifact is incompatible:", file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
            return 1
        logger.info("Loaded artifact %s (%s)", model_path, suite.artifact_id)

    store = StreamStore(
        root,
        interval_seconds=config.candles.interval_seconds,
        window_size=config.context.macro_candles,
        flush_events=config.stream.flush_events,
        compression=config.stream.compression,
        max_buffer_events=config.stream.max_buffer_events,
        active_id=config.instrument.active_id,
        artifact_id=suite.artifact_id if suite is not None else None,
    )
    runtime: RuntimeEngine | None = None
    if suite is not None:
        runtime = RuntimeEngine(
            store,
            suite,
            config,
            decisions_dir=Path(root) / "decisions",
            trade_journal=TradeJournal(Path(root) / "trades.jsonl"),
        )
    else:
        logger.warning(
            "Capture-only mode: ticks and candles are stored, no decisions are made."
        )

    def sink(active_id, payload: dict) -> None:
        try:
            result = store.ingest(active_id, payload)
        except StreamBufferError as exc:
            raise SystemExit(f"stream buffer limit exceeded: {exc}") from exc
        if runtime is not None:
            runtime.on_ingest(result)

    receiver.set_tick_sink(sink)
    logger.info("Streaming accepted ticks to %s", root)
    try:
        receiver.run(args.host, args.port)
    finally:
        receiver.set_tick_sink(None)
        if runtime is not None:
            runtime.close()
        store.close()
        print("stream summary")
        for key, value in store.counters.items():
            print(f"  {key:<24}: {value}")
        print(f"  {'last_sequence':<24}: {store.last_sequence}")
        print(f"  {'last_finalized_bucket':<24}: {store.last_finalized_bucket}")
        if runtime is not None:
            print("runtime summary")
            for key, value in runtime.counters.as_dict().items():
                print(f"  {key:<24}: {value}")
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
    dated = models_dir / f"suite-{stamp}.joblib"
    suite.save(dated)

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
    print(f"suite written  : {dated}")
    print(f"manifest       : {ModelSuite.manifest_path(dated)}")
    print(f"artifact id    : {suite.artifact_id}")
    return 0


def cmd_backtest(args: argparse.Namespace, config: Config) -> int:
    import pandas as pd

    dataset_path = Path(args.dataset or Path(config.store.root) / "dataset.parquet")
    suite_path = _find_model(config, args.model)
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


def cmd_model_check(args: argparse.Namespace, config: Config) -> int:
    import json

    path = Path(args.model)
    try:
        suite = ModelSuite.load(path, require_manifest=True)
    except ModelArtifactError as exc:
        print(f"model artifact error: {exc}", file=sys.stderr)
        return 1

    problems = suite.validate(config)
    print("model artifact")
    print(f"  path                        : {path}")
    print(f"  artifact id                 : {suite.artifact_id}")
    print(f"  format                      : {suite.model_format_version}")
    print(f"  core features               : {suite.core_feature_version}")
    print(f"  feature diagnostics         : {suite.feature_version}")
    print(f"  decision                    : {suite.decision_version}")
    print(f"  candle                      : {suite.candle_version}")
    print(f"  horizons                    : {sorted(suite.models)}")
    if suite.manifest:
        print("manifest")
        print(json.dumps(suite.manifest, indent=2, sort_keys=True, default=str))
    if problems:
        print("validation: FAILED")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("validation: OK")
    return 0


def cmd_replay(args: argparse.Namespace, config: Config) -> int:
    import pandas as pd

    dataset = None
    if args.dataset:
        path = Path(args.dataset)
        if not path.is_file():
            print(f"dataset not found: {path}")
            return 1
        dataset = pd.read_parquet(path)

    report = replay_from_dirs(
        args.events,
        args.candles,
        interval_seconds=config.candles.interval_seconds,
        dataset=dataset,
        config=config if dataset is not None else None,
    )
    print("replay report")
    for key, value in report.as_dict().items():
        if key == "mismatches":
            print(f"  {key:<24}: {len(value)}")
        else:
            print(f"  {key:<24}: {value}")
    for item in report.mismatches[:20]:
        print(
            f"  candle {item.bucket_key} {item.field}: "
            f"recorded={item.expected} rebuilt={item.actual}"
        )
    return 0 if report.ok else 1


def cmd_diagnose(args: argparse.Namespace, config: Config) -> int:
    source = args.input or config.data.input_path
    store = _load_store(source, config)
    print("tick store")
    print(f"  rows                        : {len(store)}")
    print(f"  duplicate (timestamp, price): {store.stats.get('duplicate_rows', 0)}")
    print(f"  out-of-order rows           : {store.stats.get('out_of_order', 0)}")
    if store.is_empty:
        return 0
    timestamps = store.frame["timestamp"]
    print(f"  first tick                  : {timestamps.iloc[0]}")
    print(f"  last tick                   : {timestamps.iloc[-1]}")
    print(
        f"  sequence range              : "
        f"{store.frame['sequence'].min()}..{store.frame['sequence'].max()}"
    )
    span = (timestamps.iloc[-1] - timestamps.iloc[0]).total_seconds()
    print(f"  span seconds                : {span:.0f}")
    buckets = store.frame["timestamp"].dt.floor("min").nunique()
    print(f"  minutes with ticks          : {buckets}")
    return 0


def cmd_docs_check(args: argparse.Namespace, config: Config | None) -> int:
    """Validate the documentation tree. Needs no configuration."""

    from tools.check_docs import format_report, check_docs

    report = check_docs(args.docs_root)
    print("documentation check")
    for line in format_report(report):
        print(f"  {line}")
    return 0 if report.ok else 1


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

    serve = sub.add_parser(
        "serve", help="stream ticks into the hourly Parquet store and decide at candle close"
    )
    serve.add_argument("--host", default=receiver.HOST)
    serve.add_argument("--port", type=int, default=receiver.PORT)
    serve.add_argument(
        "--stream-dir",
        default=None,
        help="stream store root (default: config [stream].root)",
    )
    serve.add_argument(
        "--model",
        default=None,
        help=".joblib artifact (default: config [models].runtime_path)",
    )
    serve.add_argument(
        "--capture-only",
        action="store_true",
        help="store ticks and candles without inference",
    )

    build = sub.add_parser("build", help="build store, snapshots, and dataset")
    build.add_argument("--input", default=None, help="tick CSV, JSONL, or Parquet")

    train = sub.add_parser("train", help="train the horizon model suite")
    train.add_argument("--dataset", default=None)

    backtest = sub.add_parser("backtest", help="replay a dataset through the router")
    backtest.add_argument("--dataset", default=None)
    backtest.add_argument("--model", default=None)

    model_check = sub.add_parser(
        "model-check", help="validate a runtime artifact and print its manifest"
    )
    model_check.add_argument("--model", required=True)

    replay = sub.add_parser(
        "replay", help="rebuild candles from raw events and compare with the store"
    )
    replay.add_argument("--events", required=True, help="event parts root")
    replay.add_argument("--candles", default=None, help="recorded candle parts root")
    replay.add_argument("--dataset", default=None, help="dataset for feature parity")

    diagnose = sub.add_parser("diagnose", help="print a data-quality report")
    diagnose.add_argument("--input", default=None)

    docs = sub.add_parser(
        "docs-check",
        help="validate documentation status labels, links, and index coverage",
    )
    docs.add_argument("--docs-root", default=".", help="repository root to check")

    return parser


COMMANDS = {
    "serve": cmd_serve,
    "build": cmd_build,
    "train": cmd_train,
    "backtest": cmd_backtest,
    "model-check": cmd_model_check,
    "replay": cmd_replay,
    "diagnose": cmd_diagnose,
    "docs-check": cmd_docs_check,
}

#: Commands that do not read the TOML configuration.
CONFIG_FREE_COMMANDS = {"docs-check"}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    if args.command in CONFIG_FREE_COMMANDS:
        return COMMANDS[args.command](args, None)

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2

    try:
        return COMMANDS[args.command](args, config)
    except ModelArtifactError as exc:
        print(f"model artifact error: {exc}", file=sys.stderr)
        return 2
    except (TickStoreError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        logger.info("Interrupted.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

"""Offline CLI: build AMT feature and label tables from captured ticks."""

from __future__ import annotations

import argparse
from pathlib import Path

from .config import ConfigError, load_config
from .data import TickDataError, load_ticks, write_rows
from .features import FEATURE_COLUMNS, build_features
from .labels import LABEL_COLUMNS, build_labels
from .timeframes import group_candles


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build AMT features and labels from ticks.")
    parser.add_argument("--config", default=None, help="path to a TOML configuration")
    parser.add_argument("--input", default=None, help="tick CSV override")
    parser.add_argument("--features", default=None, help="feature CSV output override")
    parser.add_argument("--labels", default=None, help="label CSV output override")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"configuration error: {exc}")
        return 2

    input_path = args.input or config.data.input_path
    features_path = args.features or config.data.features_path
    labels_path = args.labels or config.data.labels_path

    try:
        tick_set = load_ticks(input_path, active_id=config.instrument.active_id)
    except TickDataError as exc:
        print(f"tick data error: {exc}")
        return 2

    candles = group_candles(tick_set.ticks, config.candles.interval_seconds)
    features = build_features(tick_set.ticks, config, candles)
    labels = build_labels(tick_set.ticks, config)

    write_rows(features_path, features, FEATURE_COLUMNS)
    write_rows(labels_path, labels, LABEL_COLUMNS)

    profile_missing = sum(row["profile_missing"] for row in features)
    ties = sum(1 for row in labels if row["label"] == "tie")
    missing = sum(1 for row in labels if row["label"] == "missing")

    print(f"rows read            : {tick_set.total_rows}")
    print(f"duplicates dropped   : {tick_set.duplicates_dropped}")
    print(f"out-of-order rows    : {tick_set.out_of_order}")
    print(f"ticks kept           : {len(tick_set.ticks)}")
    print(f"candles              : {len(candles)}")
    print(f"feature rows         : {len(features)}")
    print(f"profile-missing rows : {profile_missing}")
    print(f"label rows           : {len(labels)}")
    print(f"ties                 : {ties}")
    print(f"missing exits        : {missing}")
    print(f"features written     : {Path(features_path)}")
    print(f"labels written       : {Path(labels_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

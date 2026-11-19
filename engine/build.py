"""Pipeline assembly: store -> snapshots -> features -> labelled dataset."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .config import Config, config_hash
from .domain.labels import snapshot_label_rows
from .features import build_feature_table, build_diagnostic_table
from .sampler import SamplerReport, build_snapshots
from .store import TickStore

#: Columns that identify a labelled dataset row.
DATASET_INDEX = ("snapshot_id", "horizon_seconds")


@dataclass
class BuildArtifacts:
    store: TickStore
    sampler: SamplerReport
    features: pd.DataFrame
    labels: pd.DataFrame
    dataset: pd.DataFrame
    config_hash: str

    def summary(self) -> dict[str, object]:
        return {
            "ticks": len(self.store),
            "duplicates_dropped": self.store.stats.get("duplicates_dropped", 0),
            "out_of_order": self.store.stats.get("out_of_order", 0),
            "snapshots": len(self.sampler.snapshots),
            "feature_rows": len(self.features),
            "label_rows": len(self.labels),
            "dataset_rows": len(self.dataset),
            "usable_rows": int(self.dataset["usable"].sum()) if len(self.dataset) else 0,
            "config_hash": self.config_hash,
            **self.sampler.as_dict(),
        }


def build_dataset(snapshots, config: Config) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return ``(features, labels, dataset)`` for a list of snapshots."""

    feature_rows = build_feature_table(snapshots, config)
    features = pd.DataFrame(feature_rows)
    labels = pd.DataFrame(snapshot_label_rows(snapshots, config.labels.tie_policy))

    if features.empty or labels.empty:
        return features, labels, pd.DataFrame()

    label_columns = [
        column
        for column in labels.columns
        if column not in {"timestamp", "active_id"}
    ]
    dataset = features.merge(
        labels.loc[:, label_columns], on="snapshot_id", how="inner"
    )
    dataset = dataset.sort_values(
        ["timestamp", "horizon_seconds"], kind="mergesort"
    ).reset_index(drop=True)
    return features, labels, dataset


def build_from_ticks(ticks, config: Config) -> BuildArtifacts:
    store = TickStore.from_ticks(ticks)
    return build_from_store(store, config)


def build_from_store(store: TickStore, config: Config) -> BuildArtifacts:
    sampler = build_snapshots(store, config)
    features, labels, dataset = build_dataset(sampler.snapshots, config)
    return BuildArtifacts(
        store=store,
        sampler=sampler,
        features=features,
        labels=labels,
        dataset=dataset,
        config_hash=config_hash(config),
    )


def build_from_csv(path: str | Path, config: Config) -> BuildArtifacts:
    store = TickStore.from_csv(path, active_id=config.instrument.active_id)
    return build_from_store(store, config)


def diagnostic_table(store: TickStore, config: Config) -> pd.DataFrame:
    """One row per tick. Research aid, not the model input."""

    return pd.DataFrame(build_diagnostic_table(store.as_ticks(), config))


def write_artifacts(artifacts: BuildArtifacts, config: Config) -> dict[str, Path]:
    """Persist the store, features, labels, and dataset under ``config.store``."""

    root = Path(config.store.root)
    root.mkdir(parents=True, exist_ok=True)
    paths = {
        "ticks": artifacts.store.write_parquet(config.store.ticks_path),
        "features": root / "features.parquet",
        "labels": root / "labels.parquet",
        "dataset": root / "dataset.parquet",
    }
    artifacts.features.to_parquet(paths["features"], index=False)
    artifacts.labels.to_parquet(paths["labels"], index=False)
    if not artifacts.dataset.empty:
        artifacts.dataset.to_parquet(paths["dataset"], index=False)
    return paths

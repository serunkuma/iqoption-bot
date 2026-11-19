"""Validation and diagnostic reports.

Reports are read-only: they audit the engine and never change a model or a
trade. Flat one-unit sizing is the default so results stay comparable across
candidates.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from .config import Config
from .execution import OPEN, Trade, WON
from .models import ModelSuite


def _clip(probability: np.ndarray) -> np.ndarray:
    return np.clip(np.asarray(probability, dtype=float), 1e-6, 1 - 1e-6)


def reliability_curve(
    labels: np.ndarray, probabilities: np.ndarray, bins: int = 10
) -> list[dict[str, float | int]]:
    """Bin predictions and report observed frequency per bin."""

    labels = np.asarray(labels, dtype=float)
    probabilities = _clip(probabilities)
    edges = np.linspace(0.0, 1.0, bins + 1)
    rows: list[dict[str, float | int]] = []
    for index in range(bins):
        lower, upper = edges[index], edges[index + 1]
        if index == bins - 1:
            mask = (probabilities >= lower) & (probabilities <= upper)
        else:
            mask = (probabilities >= lower) & (probabilities < upper)
        count = int(mask.sum())
        rows.append(
            {
                "bin": index,
                "lower": round(float(lower), 4),
                "upper": round(float(upper), 4),
                "count": count,
                "mean_predicted": float(probabilities[mask].mean()) if count else 0.0,
                "observed_rate": float(labels[mask].mean()) if count else 0.0,
            }
        )
    return rows


def calibration_summary(labels: np.ndarray, probabilities: np.ndarray) -> dict[str, float | int]:
    from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

    labels = np.asarray(labels, dtype=int)
    probabilities = _clip(probabilities)
    summary: dict[str, float | int] = {
        "rows": int(labels.size),
        "positives": int(labels.sum()),
        "brier": round(float(brier_score_loss(labels, probabilities)), 6),
        "log_loss": round(
            float(log_loss(labels, probabilities, labels=[0, 1])), 6
        ),
    }
    if len(np.unique(labels)) == 2:
        summary["auc"] = round(float(roc_auc_score(labels, probabilities)), 6)
    else:
        summary["auc"] = 0.0
    curve = reliability_curve(labels, probabilities)
    ece = sum(
        (row["count"] / max(1, labels.size))
        * abs(row["mean_predicted"] - row["observed_rate"])
        for row in curve
    )
    summary["ece"] = round(float(ece), 6)
    return summary


def horizon_summary(suite: ModelSuite) -> pd.DataFrame:
    rows = [model.metrics.as_dict() for model in suite.models.values()]
    if not rows:
        return pd.DataFrame(
            columns=[
                "horizon_seconds",
                "rows",
                "positives",
                "oos_rows",
                "evaluation_rows",
                "log_loss",
                "brier",
                "auc",
                "calibration",
                "calibration_note",
                "skipped_reason",
            ]
        )
    return pd.DataFrame(rows).sort_values("horizon_seconds").reset_index(drop=True)


def feature_importance(suite: ModelSuite, top: int = 16) -> pd.DataFrame:
    """SHAP importance per horizon, with a native-importance fallback."""

    frames: list[pd.DataFrame] = []
    for horizon, model in sorted(suite.models.items()):
        importances: np.ndarray | None = None
        try:  # pragma: no cover - depends on optional shap install
            import shap

            explainer = shap.TreeExplainer(model.estimator)
            sample = np.zeros((1, len(model.feature_names)), dtype=float)
            values = explainer.shap_values(sample)
            if isinstance(values, list):
                values = values[-1]
            importances = np.abs(np.asarray(values)).mean(axis=0)
        except Exception:
            native = getattr(model.estimator, "feature_importances_", None)
            if native is not None:
                importances = np.asarray(native, dtype=float)
        if importances is None:
            continue
        frames.append(
            pd.DataFrame(
                {
                    "horizon_seconds": horizon,
                    "feature": model.feature_names,
                    "importance": importances,
                }
            )
        )
    if not frames:
        return pd.DataFrame(columns=["horizon_seconds", "feature", "importance"])
    combined = pd.concat(frames, ignore_index=True)
    combined["rank"] = combined.groupby("horizon_seconds")["importance"].rank(
        ascending=False, method="first"
    )
    return (
        combined[combined["rank"] <= top]
        .sort_values(["horizon_seconds", "rank"])
        .reset_index(drop=True)
    )


def concurrency(trades: Sequence[Trade]) -> dict[str, float | int]:
    """Trade overlap statistics for flat-sizing audits."""

    if not trades:
        return {
            "trades": 0,
            "max_concurrent": 0,
            "mean_concurrent": 0.0,
            "overlapping_trades": 0,
        }

    events: list[tuple[float, int]] = []
    for trade in trades:
        start = trade.entry_timestamp.timestamp()
        end = trade.expiry_timestamp.timestamp()
        events.append((start, 1))
        events.append((end, -1))
    events.sort()

    current = 0
    peak = 0
    for _, delta in events:
        current += delta
        peak = max(peak, current)

    overlapping = sum(
        1
        for index, trade in enumerate(trades)
        for other in trades[index + 1 :]
        if trade.entry_timestamp < other.expiry_timestamp
        and other.entry_timestamp < trade.expiry_timestamp
    )

    return {
        "trades": len(trades),
        "max_concurrent": peak,
        "mean_concurrent": round(current / len(trades), 6),
        "overlapping_trades": overlapping,
    }


def _format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if value != value:  # NaN
            return ""
        return f"{value:.6g}"
    return str(value)


def _markdown_table(frame: pd.DataFrame) -> str:
    """Render a DataFrame as a pipe table without the optional tabulate dep."""

    if frame.empty:
        return ""
    columns = [str(column) for column in frame.columns]
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in frame.itertuples(index=False):
        lines.append("| " + " | ".join(_format_cell(value) for value in row) + " |")
    return "\n".join(lines)


@dataclass
class ReportBundle:
    calibration: dict[str, dict[str, float | int]]
    horizons: pd.DataFrame
    importance: pd.DataFrame
    execution: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "calibration": self.calibration,
            "horizons": self.horizons.to_dict(orient="records"),
            "importance": self.importance.to_dict(orient="records"),
            "execution": self.execution,
        }

    def write(self, directory: str | Path, name: str = "report") -> Path:
        destination = Path(directory)
        destination.mkdir(parents=True, exist_ok=True)
        payload = self.to_dict()
        json_path = destination / f"{name}.json"
        json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

        lines = [f"# {name}", "", "## Per-horizon", ""]
        if not self.horizons.empty:
            lines.append(_markdown_table(self.horizons))
        else:
            lines.append("_No horizon models were trained._")
        lines.extend(["", "## Execution", "", "```json", json.dumps(self.execution, indent=2, default=str), "```"])
        (destination / f"{name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return json_path


def build_report(
    suite: ModelSuite,
    calibration: dict[str, dict[str, float | int]],
    trades: Sequence[Trade],
    skipped: dict[str, int] | None = None,
) -> ReportBundle:
    closed = [trade for trade in trades if trade.status != OPEN]
    wins = sum(1 for trade in closed if trade.status == WON)
    execution = {
        "trades": len(trades),
        "closed": len(closed),
        "open": len(trades) - len(closed),
        "wins": wins,
        "win_rate": round(wins / len(closed), 6) if closed else 0.0,
        "pnl": round(sum(trade.pnl or 0.0 for trade in trades), 6),
        "concurrency": concurrency(trades),
        "skipped": skipped or {},
        "skipped_horizons": {
            str(horizon): reason for horizon, reason in suite.skipped.items()
        },
    }
    return ReportBundle(
        calibration=calibration,
        horizons=horizon_summary(suite),
        importance=feature_importance(suite),
        execution=execution,
    )

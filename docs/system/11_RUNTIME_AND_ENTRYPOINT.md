# Runtime and Entry Point

Status: Current

> `runner.py` is the only entry point. It owns process lifecycle and wiring; capture, streaming, sampling, features, models, routing, and execution stay independently testable. `serve` stores events and candles and can make paper decisions at candle close.

---

## Commands

Every command loads `config/default.toml` (or `--config`), validates it, and fails with exit code `2` on a configuration error.

| Command | Purpose | Writes |
|---------|---------|--------|
| `serve` | Stream accepted ticks to the event/candle store; optionally journal decisions or make paper trades | `data/stream/` |
| `build` | Build the tick store, snapshots, features, labels, and dataset | `data/*.parquet` |
| `train` | Train the four calibrated horizon models | Timestamped `.joblib` plus manifest |
| `backtest` | Replay the held-out evaluation slice through router and paper broker | `reports/backtest.{json,md}` |
| `model-check` | Validate a runtime artifact and print its manifest | nothing |
| `replay` | Rebuild candles from stored events and compare with recorded tables | nothing |
| `diagnose` | Print a data-quality report for a capture or store | nothing |
| `docs-check` | Validate documentation status labels, links, and index coverage | nothing |

Global flags:

| Flag | Default | Meaning |
|------|---------|---------|
| `--config` | `config/default.toml` | TOML configuration path |
| `--log-level` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

```powershell
.\.venv\Scripts\python.exe runner.py serve --capture-only
.\.venv\Scripts\python.exe runner.py serve --shadow
.\.venv\Scripts\python.exe runner.py model-check --model data\models\suite-YYYYMMDDTHHMMSSZ.joblib
.\.venv\Scripts\python.exe runner.py replay --events data\stream\events --candles data\stream\candles
.\.venv\Scripts\python.exe runner.py build --input data\stream\events
.\.venv\Scripts\python.exe runner.py train
.\.venv\Scripts\python.exe runner.py backtest
.\.venv\Scripts\python.exe runner.py diagnose --input data\raw\ticks-2026-11-18.jsonl
```

---

## `serve`

```powershell
.\.venv\Scripts\python.exe runner.py serve --capture-only
.\.venv\Scripts\python.exe runner.py serve --shadow
.\.venv\Scripts\python.exe runner.py serve --model data\models\suite-YYYYMMDDTHHMMSSZ.joblib
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--host` | `localhost` | Bind address |
| `--port` | `8765` | WebSocket port |
| `--stream-dir` | `[stream].root` | Stream store root |
| `--model` | `[models].runtime_path` | Manifest-bearing `.joblib` artifact |
| `--capture-only` | off | Store ticks/candles without loading a model or making decisions |
| `--shadow` | off | Load the model, journal decisions, and never open a paper trade |

`--capture-only` and `--shadow` are mutually exclusive. Without either, startup requires a compatible `.joblib` artifact and fails with exit code `1` when it is missing, corrupt, or incompatible. The loaded artifact stays pinned for the process. The receiver forwards accepted events to `StreamStore`; it does not write the former daily raw JSONL capture. See [Streaming Runtime and Store](16_STREAMING_RUNTIME_AND_STORE.md) for event, storage, recovery, decision, and failure contracts.

---

## `build`

```powershell
.\.venv\Scripts\python.exe runner.py build --input data\ticks.csv
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--input` | `data/ticks.csv` | `.csv`, `.jsonl`, `.parquet`, or a stream events directory |

The input suffix selects the loader. CSV and JSONL enforce the tick contract; Parquet is trusted as an already-validated store. A directory is treated as a stream store root (or its `events` directory) and its hourly `part-*.parquet` files are concatenated and stable-sorted by `(timestamp, sequence)`.

Outputs, all under `config.store`:

| File | Content |
|------|---------|
| `data/ticks.parquet` | Canonical batch tick table with sequence; exact duplicate events are preserved |
| `data/features.parquet` | One row per validated snapshot |
| `data/labels.parquet` | Long format, one row per snapshot per horizon |
| `data/dataset.parquet` | Features joined to labels on `snapshot_id` |

The command prints the build summary: tick count, duplicate timestamp/price count, out-of-order rows, candidate minutes, snapshots, feature/label/dataset rows, usable rows, config hash, and sampler exclusion counters.

An empty store returns exit code `1` rather than writing empty artifacts.

---

## `train`

```powershell
.\.venv\Scripts\python.exe runner.py train --dataset data\dataset.parquet
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--dataset` | `data/dataset.parquet` | Labelled dataset |

Writes `data/models/suite-YYYYMMDDTHHMMSSZ.joblib` and the matching `.manifest.json` sidecar. Prints one line per horizon with row count, out-of-sample rows, held-out evaluation rows, Brier score, AUC, and calibrator. A rejected calibrator is printed as a note. Skipped horizons print their reason instead.

The command fails with exit code `1` when the dataset is missing; it does **not** silently train on an empty dataset. No artifact is automatically promoted to the configured runtime path.

---

## `backtest`

```powershell
.\.venv\Scripts\python.exe runner.py backtest --dataset data\dataset.parquet --model data\models\suite-YYYYMMDDTHHMMSSZ.joblib
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--dataset` | `data/dataset.parquet` | Labelled dataset, used for timing and outcomes |
| `--model` | configured runtime suite, latest dated `.joblib`, or legacy `suite.pkl` | Analysis/backtest suite |

Only snapshots present in the suite's held-out evaluation table produce a probability. Every other snapshot is counted as `skipped_no_model`. The command writes `reports/backtest.json` and `reports/backtest.md` and prints the execution summary.

When the suite has no evaluation rows, the command warns, writes a report with an empty calibration section, and trades nothing.

## `model-check` and `replay`

`model-check --model <path>` requires a `.joblib` artifact with a readable, matching manifest. It validates the artifact contract against the active configuration and prints the manifest and compatibility result. It does not activate or modify the artifact.

`replay --events <root> [--candles <root>] [--dataset <path>]` reads hourly event parts, rebuilds closed candles with the runtime candle builder, and reports missing, extra, or mismatching candles. Supplying a dataset also checks feature parity. It exits `1` when the comparison reports a divergence.

---

## `diagnose`

```powershell
.\.venv\Scripts\python.exe runner.py diagnose --input data\raw\ticks-2026-11-18.jsonl
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--input` | `data/ticks.csv` | `.csv`, `.jsonl`, `.parquet`, or a stream events directory |

Prints row count, duplicate `(timestamp, price)` count, out-of-order rows, first and last tick, sequence range, span in seconds, and minutes with ticks. A directory input reads the streaming store's event parts.

---

## `docs-check`

```powershell
.\.venv\Scripts\python.exe runner.py docs-check
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--docs-root` | `.` | Repository root to check |

Runs the same code as `tools/check_docs.py` and enforces three rules:

1. Every markdown file under `docs/` declares `Status: Current`, `Planning`, or `Historical`.
2. Every relative markdown link resolves to a file that exists.
3. Every markdown file under `docs/` is linked from `docs/index.md`.

Output:

```text
documentation check
  files checked                : 44
  missing status               : 0
  broken link                  : 0
  orphan doc                   : 0
```

Exit code `0` is clean; `1` lists every offending path and detail. This command is config-free: it does not load the TOML file, so it still works when the configuration is broken. It only reads files and imports the standard library, so it cannot trip the LightGBM import ordering.

The checker also runs before every commit through the versioned hook:

```powershell
.\.venv\Scripts\python.exe tools\install_hooks.py
```

The hook lives in `.githooks/pre-commit` and calls `tools/check_docs.py` directly, so it does not depend on the virtual environment being healthy. See [Testing](../system/05_TESTING.md) for the bypass and optional test-suite behaviour.

The checker validates structure, not truth. Prose that no longer matches the code still passes.

---

## Wiring Rules

1. `runner.py` may import every component; no component imports `runner`.
2. `engine` never imports `components`; capture is upstream of the engine.
3. Components exchange plain data: `Tick`, `TickStore`, `Snapshot`, `FeatureVector`, `SignalProposal`, `Trade`.
4. No component reads another component's private attributes.
5. Every command that persists artefacts writes under `config.store`.
6. `serve` performs candle-close inference and paper decisions when a compatible model is loaded; it does not place broker orders.

---

## Import-Order Caveat (Windows)

LightGBM's Windows DLL must load before pandas/pyarrow. If pandas is imported first, the first `LGBMClassifier.fit` can raise `OSError: exception: access violation reading 0x0000000000000000` inside `LGBM_DatasetSetField`.

`engine/models.py` imports `lightgbm` before `pandas`, and `engine/__init__.py` imports `.models` first. Scripts must import `engine` (or `engine.models`) before importing pandas directly. The tests and `runner.py` both follow this order.

---

## Related Documentation

- [Components](02_COMPONENTS.md)
- [Configuration](03_CONFIGURATION.md)
- [Interfaces](04_INTERFACES.md)
- [Data pipeline](07_DATA_PIPELINE.md)
- [Tick store](../data/07_TICK_STORE.md)
- [Snapshots and continuity](../data/08_SNAPSHOTS_AND_CONTINUITY.md)
- [Reports and diagnostics](15_REPORTS_AND_DIAGNOSTICS.md)
- [Streaming runtime and store](16_STREAMING_RUNTIME_AND_STORE.md)

---

*Last updated: 2026-11-21*

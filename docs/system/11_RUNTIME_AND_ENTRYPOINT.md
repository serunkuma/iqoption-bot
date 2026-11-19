# Runtime and Entry Point

Status: Current

> `runner.py` is the only entry point. It owns process lifecycle and wiring; capture, sampling, features, models, routing, and execution stay independently testable. `serve` captures only — it does not build candles, compute features, or emit signals.

---

## Commands

Every command loads `config/default.toml` (or `--config`), validates it, and fails with exit code `2` on a configuration error.

| Command | Purpose | Writes |
|---------|---------|--------|
| `serve` | Capture ticks from the browser extension | `data/raw/ticks-YYYY-MM-DD.jsonl` |
| `build` | Build the tick store, snapshots, features, labels, and dataset | `data/*.parquet` |
| `train` | Train the four calibrated horizon models | `data/models/suite.pkl` and a dated copy |
| `backtest` | Replay the held-out evaluation slice through router and paper broker | `reports/backtest.{json,md}` |
| `diagnose` | Print a data-quality report for a capture or store | nothing |
| `docs-check` | Validate documentation status labels, links, and index coverage | nothing |

Global flags:

| Flag | Default | Meaning |
|------|---------|---------|
| `--config` | `config/default.toml` | TOML configuration path |
| `--log-level` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

```powershell
.\.venv\Scripts\python.exe runner.py serve
.\.venv\Scripts\python.exe runner.py build --input data\ticks.csv
.\.venv\Scripts\python.exe runner.py train
.\.venv\Scripts\python.exe runner.py backtest
.\.venv\Scripts\python.exe runner.py diagnose --input data\raw\ticks-2026-11-18.jsonl
```

---

## `serve`

```powershell
.\.venv\Scripts\python.exe runner.py serve --raw-dir data\raw
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--host` | `localhost` | Bind address |
| `--port` | `8765` | WebSocket port |
| `--raw-dir` | `data/raw` | JSONL capture directory; pass `''` to disable persistence |

`serve` installs a `JsonlTickSink` on the receiver, logs one warning that no candles, features, or signals are produced in this mode, and then blocks until `Ctrl+C`.

Each accepted tick appends one line to `ticks-<UTC date>.jsonl`:

```json
{"received_at": "2026-11-18T12:00:02.100000+01:00", "active_id": 42, "price": 1.25, "payload": {"active_id": 42, "close": 1.25, "at": 123}}
```

The broker payload is preserved verbatim under `payload`. Only `received_at`, `active_id`, and `price` are promoted; the broker's `at` field is never used as the tick timestamp. Sink failures are logged and never terminate capture.

---

## `build`

```powershell
.\.venv\Scripts\python.exe runner.py build --input data\ticks.csv
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--input` | `data/ticks.csv` | `.csv`, `.jsonl`, or `.parquet` tick input |

The input suffix selects the loader. CSV and JSONL enforce the tick contract; Parquet is trusted as an already-validated store.

Outputs, all under `config.store`:

| File | Content |
|------|---------|
| `data/ticks.parquet` | Canonical ordered, deduplicated tick table |
| `data/features.parquet` | One row per validated snapshot |
| `data/labels.parquet` | Long format, one row per snapshot per horizon |
| `data/dataset.parquet` | Features joined to labels on `snapshot_id` |

The command prints the build summary: tick count, duplicates dropped, out-of-order rows, candidate minutes, snapshots, feature/label/dataset rows, usable rows, config hash, and every sampler exclusion counter.

An empty store returns exit code `1` rather than writing empty artifacts.

---

## `train`

```powershell
.\.venv\Scripts\python.exe runner.py train --dataset data\dataset.parquet
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--dataset` | `data/dataset.parquet` | Labelled dataset |

Writes `data/models/suite.pkl` and a timestamped `suite-YYYYMMDDTHHMMSSZ.pkl` copy. Prints one line per horizon with row count, out-of-sample rows, held-out evaluation rows, Brier score, AUC, and calibrator. A rejected calibrator is printed as a note. Skipped horizons print their reason instead.

The command fails with exit code `1` when the dataset is missing; it does **not** silently train on an empty dataset.

---

## `backtest`

```powershell
.\.venv\Scripts\python.exe runner.py backtest --dataset data\dataset.parquet --model data\models\suite.pkl
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--dataset` | `data/dataset.parquet` | Labelled dataset, used for timing and outcomes |
| `--model` | `data/models/suite.pkl` | Trained suite |

Only snapshots present in the suite's held-out evaluation table produce a probability. Every other snapshot is counted as `skipped_no_model`. The command writes `reports/backtest.json` and `reports/backtest.md` and prints the execution summary.

When the suite has no evaluation rows, the command warns, writes a report with an empty calibration section, and trades nothing.

---

## `diagnose`

```powershell
.\.venv\Scripts\python.exe runner.py diagnose --input data\raw\ticks-2026-11-18.jsonl
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--input` | `data/ticks.csv` | `.csv`, `.jsonl`, or `.parquet` |

Prints row count, duplicates dropped, out-of-order rows, first and last tick, span in seconds, and the number of whole minutes that contain at least one tick. This is the first check before a build: minutes with ticks is the ceiling on candidate snapshots.

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
  files checked                : 42
  missing status               : 0
  broken link                  : 0
  orphan doc                   : 0
```

Exit code `0` is clean; `1` lists every offending path and detail. This command is config-free: it does not load the TOML file, so it still works when the configuration is broken. It only reads files and imports the standard library, so it cannot trip the LightGBM import ordering.

The checker validates structure, not truth. Prose that no longer matches the code still passes.

---

## Wiring Rules

1. `runner.py` may import every component; no component imports `runner`.
2. `engine` never imports `components`; capture is upstream of the engine.
3. Components exchange plain data: `Tick`, `TickStore`, `Snapshot`, `FeatureVector`, `SignalProposal`, `Trade`.
4. No component reads another component's private attributes.
5. Every command that persists artefacts writes under `config.store`.
6. `serve` is capture-only. Live feature computation and live signals are not implemented.

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

---

*Last updated: 2026-11-19*

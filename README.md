# IQ Option Bot

Status: Current

> **Current status: a local streaming and offline research system with paper-only decisions.** The browser extension forwards IQ Option WebSocket frames to `runner.py serve`, which stores accepted events and closed candles in hourly Parquet parts. When given a compatible model artifact, `serve` computes candle-close features and records paper decisions; it does not place orders.
>
> There is no broker execution, learned signal selector, complete risk manager, or multi-instrument support. The pipeline has never demonstrated an edge on real data. Do not use it with real money.

---

## What It Does Today

- A Chrome Manifest V3 extension runs on `*.iqoption.com`, observes the page's WebSocket traffic, and forwards matching frames to `ws://localhost:8765`.
- `components/receiver.py` validates each frame, stamps `received_at`, buffers 500 raw messages per `active_id`, and forwards accepted events to the stream store.
- `engine/stream/` preserves accepted events with a sequence, builds candles, rejects late events, persists hourly Parquet parts, and maintains restart state.
- `engine/store.py` loads CSV, JSONL, or Parquet into a validated tick table; exact duplicates are preserved and batch rows are stably ordered by timestamp and sequence.
- `engine/sampler.py` emits one offline decision snapshot per eligible candle close, after a contiguous completed-candle window, then resolves delayed entry and horizon outcomes.
- `engine/features.py` computes the 16-input `core16-v2` vector plus the `amt-v4` diagnostic table from completed candles, with no state and no lookahead.
- `engine/domain/labels.py` produces `snapshot-horizon-v1` labels at 60/90/120/180 seconds; ties and missing exits stay explicit.
- `engine/models.py` trains four calibrated binary classifiers using purged walk-forward, splits out-of-sample rows 70/30 chronologically, and stores the later 30% as the held-out evaluation slice.
- `engine/router.py` computes payout-aware expected value, applies the `+0.03` hurdle, and returns one proposal or an explicit no-trade with a reason code.
- `engine/backtest.py` and `engine/execution.py` replay only held-out probabilities through a paper broker with a one-open-trade limit.
- `engine/reports.py` writes calibration, reliability, and importance output as JSON and Markdown.

The capture console has been manually verified to show live prices. Everything downstream runs end to end on synthetic or small captures. **No result to date is distinguishable from noise.**

## What It Does Not Do Yet

- Runtime paper decisions are implemented, but no broker order execution; `demo` and `live` modes are rejected.
- Runtime gates include one open paper trade, cooldown, and a configured daily loss stop; this is not a complete risk manager or kill switch.
- No multi-instrument support; the sampler filters to one `active_id`.
- Streaming events and candles are persisted in hourly parts; offline snapshots are rebuilt and not stored separately.
- No incremental append; `build` reads a whole file.
- No learned selector, rule-based baseline, drift monitoring, or per-fold/per-session report breakdowns.
- No evidence of positive expected value after payout.

## Quick Start

### 1. Create the environment

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

Install the versioned git hooks once per clone so the documentation checker runs before every commit:

```powershell
.\.venv\Scripts\python.exe tools\install_hooks.py
```

### 2. Start the stream store

```powershell
.\.venv\Scripts\python.exe runner.py serve
```

The receiver listens on `ws://localhost:8765` and stores accepted events and closed candles under `data/stream/`. Use `--capture-only` to store data without loading a model or making decisions. Otherwise, `serve` requires a compatible `.joblib` artifact at `models.runtime_path` or the `--model` path.

### 3. Load the extension

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Select **Load unpacked** and choose the `chrome-extension` folder.
4. Open or reload an IQ Option page.

The extension reconnects every two seconds after a disconnect. While disconnected it queues up to 500 messages and drops the oldest when full.

### 4. Verify ticks

Watch the receiver console. Each accepted frame logs the asset identity, `close`, `open`, `min`, `max`, `volume`, `at`, and buffer length.

### 5. Inspect a file capture

```powershell
.\.venv\Scripts\python.exe runner.py diagnose --input data\ticks.csv
```

`diagnose` reads a `.csv`, `.jsonl`, `.parquet`, or stream events directory and reports duplicate `(timestamp, price)` pairs, out-of-order rows, sequence range, and time coverage. Streaming files can be reviewed with `replay`.

### 6. Build the dataset

```powershell
.\.venv\Scripts\python.exe runner.py build --input data\ticks.csv
```

Inputs may be `.csv`, `.jsonl`, `.parquet`, or a stream events directory such as `data\stream\events`; the default is `data/ticks.csv`. Outputs are `data/ticks.parquet`, `data/features.parquet`, `data/labels.parquet`, and `data/dataset.parquet`. The command prints a build summary with snapshot exclusions and the artifact paths.

### 7. Train and backtest

```powershell
.\.venv\Scripts\python.exe runner.py train
.\.venv\Scripts\python.exe runner.py backtest
```

`train` writes a timestamped `data/models/suite-<UTC timestamp>.joblib` and a `.manifest.json` sidecar. `model-check --model <path>` validates the runtime artifact. `backtest` writes `reports/backtest.json` and `reports/backtest.md`; it replays held-out evaluation probabilities only.

### 8. Run the tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
.\.venv\Scripts\python.exe runner.py docs-check
```

The first command runs the unit suite. The second validates documentation status labels, links, and index coverage. Once the hooks are installed, the commit-time check runs automatically.

### 9. Stop capture

Press `Ctrl+C` in the receiver terminal.

## Architecture

```text
IQ Option Traderoom (browser)
    -> chrome-extension/inject.js        observe WebSocket, filter candle-generated
    -> chrome-extension/content.js       forward to ws://localhost:8765
    -> components/receiver.py            validate, stamp received_at, buffer
    -> engine.stream.StreamStore         events/candles, sequence, gaps, persistence
    -> candle-close RuntimeEngine        core16-v2 / amt-v4, .joblib inference
    -> deterministic EV router           paper proposal or no-trade
    -> decision and trade journals       JSONL

Offline research remains available:
    -> CSV / JSONL / Parquet
    -> engine.store.TickStore            batch table, stable timestamp/sequence order
    -> engine.sampler                    candle-close snapshots, delayed entry, labels
    -> engine.features                   core16-v2 + amt-v4
    -> engine.domain.labels              snapshot-horizon-v1
    -> data/dataset.parquet
    -> engine.models                     four calibrated horizon classifiers
    -> engine.router                     EV hurdle, one proposal or no-trade
    -> engine.backtest + execution       paper trades, held-out replay
    -> reports/backtest.{json,md}
```

`runner.py` is the only entry point. It wires the components; no component imports another component's internals.

## Repository Layout

```text
iqoption-bot/
├── runner.py               # serve / build / train / backtest / model-check / replay / diagnose
├── config/default.toml     # Active configuration
├── components/receiver.py  # Tick capture
├── engine/                 # Store, stream runtime, sampler, features, models, router, execution
├── chrome-extension/       # MV3 capture extension
├── tests/                  # Unit tests for offline and streaming paths
├── tools/                  # Docs checker and hook installer
├── .githooks/              # Versioned pre-commit hook
└── docs/                   # Documentation tree
```

## Documentation

- [docs/00_ORIENTATION.md](docs/00_ORIENTATION.md) — **start here**: the pipeline, the feature layers, what is proven
- [docs/index.md](docs/index.md) — full documentation index
- [AGENTS.md](AGENTS.md) — source of truth for agents and developers
- [RUNBOOK.md](RUNBOOK.md) — operating capture, build, train, and backtest
- [docs/system/01_OVERVIEW.md](docs/system/01_OVERVIEW.md) — current architecture and scope
- [docs/system/11_RUNTIME_AND_ENTRYPOINT.md](docs/system/11_RUNTIME_AND_ENTRYPOINT.md) — every command and output
- [docs/system/16_STREAMING_RUNTIME_AND_STORE.md](docs/system/16_STREAMING_RUNTIME_AND_STORE.md) — current streaming/runtime contract
- [docs/data/01_TICK_STREAM.md](docs/data/01_TICK_STREAM.md) — what a tick means here
- [docs/planning.md](docs/planning.md) — roadmap and phases
- [docs/system/10_LIMITATIONS_AND_BACKLOG.md](docs/system/10_LIMITATIONS_AND_BACKLOG.md) — what to improve next

## Roadmap Summary

1. Verify frame semantics, measure real tick cadence, and improve session/reconnect observability.
2. Validate the candle-close path on independent real captures and compare it with rule-based baselines.
3. Improve reporting, replay/recovery evidence, and operational procedures.
4. Evaluate a learned selector separately; keep paper-only execution until all evidence and safety gates are met.

## Safety

- This is a research project, not financial advice.
- Automated trading may violate IQ Option's terms or local regulations; verify eligibility and platform rules before any live use.
- Real-money trading is not supported by the current code. Execution is paper-only.
- Live execution requires the gate in [docs/system/09_MODEL_VALIDATION.md](docs/system/09_MODEL_VALIDATION.md), a risk layer, and a kill switch.
- Never commit credentials, SSIDs, or account data.

## Requirements

- Windows with PowerShell.
- Python 3.11 or newer.
- Chrome or a Chromium-based browser.
- `websockets`, `numpy`, `pandas`, `pyarrow`, `scikit-learn`, `lightgbm`, and `shap` per `requirements.txt`.

### Windows note

Import `engine` before `pandas`/`pyarrow` in any script. The package imports LightGBM first to avoid a DLL access-violation crash inside `LGBM_DatasetSetField`.

---

*Last updated: 2026-11-21*

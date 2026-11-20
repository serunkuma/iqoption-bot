# IQ Option Bot

Status: Current

> **Current status: a working offline prediction engine fed by a live tick capture, with a paper-only backtest.** The project captures IQ Option browser WebSocket frames, persists them as daily JSONL, builds a validated Parquet tick store, samples continuity-gated snapshots, computes a stateless 16-feature vector, attaches per-horizon labels, trains four calibrated LightGBM classifiers, and replays held-out probabilities through an expected-value router and a paper broker.
>
> It does **not** place orders, compute live features, run a live signal loop, manage risk, or support more than one instrument. The pipeline has never demonstrated an edge on real data. Do not use it with real money.

---

## What It Does Today

- A Chrome Manifest V3 extension runs on `*.iqoption.com`, observes the page's WebSocket traffic, and forwards matching frames to `ws://localhost:8765`.
- `components/receiver.py` validates each frame, stamps `received_at`, buffers 500 raw messages per `active_id`, and can persist every accepted tick as a daily JSONL file.
- `engine/store.py` loads CSV, JSONL, or Parquet into a validated, ordered, deduplicated tick store with point-in-time price lookup.
- `engine/sampler.py` requires seven contiguous completed 1-minute bars before emitting a snapshot at a configurable minute offset, then resolves a delayed entry and one exit per horizon.
- `engine/features.py` computes the 16-input `core16-v1` vector plus the `amt-v3` diagnostic table from one snapshot, with no state and no lookahead.
- `engine/domain/labels.py` produces `snapshot-horizon-v1` labels at 60/90/120/180 seconds; ties and missing exits stay explicit.
- `engine/models.py` trains four calibrated binary classifiers using purged walk-forward, splits out-of-sample rows 70/30 chronologically, and stores the later 30% as the held-out evaluation slice.
- `engine/router.py` computes payout-aware expected value, applies the `+0.03` hurdle, and returns one proposal or an explicit no-trade with a reason code.
- `engine/backtest.py` and `engine/execution.py` replay only held-out probabilities through a paper broker with a one-open-trade limit.
- `engine/reports.py` writes calibration, reliability, and importance output as JSON and Markdown.

The capture console has been manually verified to show live prices. Everything downstream runs end to end on synthetic or small captures. **No result to date is distinguishable from noise.**

## What It Does Not Do Yet

- No live candle, snapshot, or feature computation — `serve` captures only.
- No live signal loop and no order execution; `demo` and `live` mode names are validated then rejected.
- No risk manager, daily loss limit, or kill switch; fixed stake and one open trade only.
- No multi-instrument support; the sampler filters to one `active_id`.
- No candle or snapshot store; both are rebuilt inside a build.
- No incremental append; `build` reads a whole file.
- No rule-based baseline, no drift monitoring, no per-fold or per-session report breakdowns.
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

### 2. Start capture

```powershell
.\.venv\Scripts\python.exe runner.py serve
```

The receiver listens on `ws://localhost:8765` and appends accepted ticks to `data/raw/ticks-YYYY-MM-DD.jsonl`. Pass `--raw-dir ''` to disable persistence.

### 3. Load the extension

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Select **Load unpacked** and choose the `chrome-extension` folder.
4. Open or reload an IQ Option page.

The extension reconnects every two seconds after a disconnect. While disconnected it queues up to 500 messages and drops the oldest when full.

### 4. Verify ticks

Watch the receiver console. Each accepted frame logs the asset identity, `close`, `open`, `min`, `max`, `volume`, `at`, and buffer length.

### 5. Inspect the capture

```powershell
.\.venv\Scripts\python.exe runner.py diagnose --input data\raw\ticks-2026-11-18.jsonl
```

Prints row count, duplicates dropped, out-of-order rows, first and last tick, span, and minutes with ticks.

### 6. Build the dataset

```powershell
.\.venv\Scripts\python.exe runner.py build --input data\raw\ticks-2026-11-18.jsonl
```

Inputs may be `.csv`, `.jsonl`, or `.parquet`; the default is `data/ticks.csv`. Outputs are `data/ticks.parquet`, `data/features.parquet`, `data/labels.parquet`, and `data/dataset.parquet`. The command prints a build summary with snapshot exclusions and the artifact paths.

### 7. Train and backtest

```powershell
.\.venv\Scripts\python.exe runner.py train
.\.venv\Scripts\python.exe runner.py backtest
```

`train` writes `data/models/suite.pkl` plus a dated copy and prints per-horizon row counts, evaluation rows, Brier, AUC, and calibration mode. `backtest` writes `reports/backtest.json` and `reports/backtest.md`.

### 8. Run the tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
.\.venv\Scripts\python.exe runner.py docs-check
```

The first command runs the 121 unit tests. The second validates documentation status labels, links, and index coverage. Once the hooks are installed, the commit-time check runs automatically.

### 9. Stop capture

Press `Ctrl+C` in the receiver terminal.

## Architecture

```text
IQ Option Traderoom (browser)
    -> chrome-extension/inject.js        observe WebSocket, filter candle-generated
    -> chrome-extension/content.js       forward to ws://localhost:8765
    -> components/receiver.py            validate, stamp received_at, buffer, sink
    -> data/raw/ticks-YYYY-MM-DD.jsonl
    -> runner.py build
    -> engine.store.TickStore            ordered, deduplicated, point-in-time
    -> engine.sampler                    continuity gate, delayed entry, exits
    -> engine.features                   core16-v1 + amt-v3
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
├── runner.py               # serve / build / train / backtest / diagnose
├── config/default.toml     # Active configuration
├── components/receiver.py  # Tick capture
├── engine/                 # Store, sampler, features, models, router, execution
├── chrome-extension/       # MV3 capture extension
├── tests/                  # 121 unit tests
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
- [docs/data/01_TICK_STREAM.md](docs/data/01_TICK_STREAM.md) — what a tick means here
- [docs/planning.md](docs/planning.md) — roadmap and phases
- [docs/system/10_LIMITATIONS_AND_BACKLOG.md](docs/system/10_LIMITATIONS_AND_BACKLOG.md) — what to improve next

## Roadmap Summary

1. Harden tick capture: verify frame semantics, add quality counters, move receiver constants into configuration.
2. Trust the data: measure real tick cadence, record sessions and gaps, persist snapshots.
3. Validate honestly: real multi-day captures, a rule-based baseline, per-fold and per-session reporting.
4. Only then: risk controls, paper loop, demo adapter, operations.

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

*Last updated: 2026-11-19*

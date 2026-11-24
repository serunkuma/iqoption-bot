# IQ Option Bot — Agent Guide

Status: Current

> **This file is the single source of truth for any AI agent or developer working in this repository.** Read it fully before making changes. Keep it current when architecture, commands, or decisions change.

---

## 1. What This System Does

IQ Option Bot is a local, documentation-driven project with four working layers:

1. **Capture** — a Chrome extension forwards IQ Option WebSocket frames to `components/receiver.py`, which validates and timestamps accepted events.
2. **Streaming** — `engine/stream/` sequences events, builds completed candles, persists hourly Parquet parts, and maintains recoverable state.
3. **Analysis and training** — `engine/` builds candle-close snapshots, the `core16-v2` input vector and `amt-v4` diagnostics, labels, datasets, and four calibrated classifiers.
4. **Prediction and paper evaluation** — a manifest-validated `.joblib` suite can drive candle-close runtime inference and deterministic EV paper decisions; offline backtests replay held-out probabilities.

There is **no broker order execution, no learned direction/horizon/no-trade selector, no complete risk manager or kill switch, and no multi-instrument support.** Runtime paper decisions exist, but the pipeline has not demonstrated an edge on real data. Never describe it as a working trading bot.

The four per-horizon classifiers estimate probabilities; the final router is deterministic. Runtime inference requires a compatible `.joblib` artifact with a manifest and fails closed if validation fails. Legacy pickle suites remain for analysis/backtest only. The learned selector and evidence-based promotion remain planned. See [docs/planning/ml-runtime-and-signal-selection.md](docs/planning/ml-runtime-and-signal-selection.md). Pocket Auto v3 is a reference repository only.

---

## 2. Repository Layout

```text
iqoption-bot/
├── README.md                       # Project entry point
├── AGENTS.md                       # THIS FILE — agent guide and source of truth
├── RUNBOOK.md                      # Operating procedures
├── runner.py                       # Entry point: serve/build/train/backtest/model-check/replay/diagnose/docs-check
├── requirements.txt                # Python dependencies
├── asset_names.json                # active_id → display-name map
├── .githooks/
│   └── pre-commit                  # Runs the documentation checker before each commit
├── .gitattributes                  # Forces LF endings for the shell hooks
├── tools/
│   ├── check_docs.py               # Documentation status/link/index checker
│   └── install_hooks.py            # Points core.hooksPath at .githooks/
├── config/
│   └── default.toml                # Active configuration for the whole engine
├── components/
│   ├── __init__.py
│   └── receiver.py                 # Tick-capture component
├── engine/
│   ├── __init__.py                 # Imports .models first (LightGBM ordering)
│   ├── config.py                   # TOML schema, validation, version constants
│   ├── store.py                    # Batch tick store, duplicate reporting, point-in-time lookup
│   ├── stream/                     # Sequenced events, candles, Parquet, recovery
│   ├── runtime.py                  # Candle-close inference and paper decisions
│   ├── sampler.py                  # Snapshot gate, continuity, entry/exit timing
│   ├── features.py                 # core16-v2 vector + amt-v4 diagnostics
│   ├── models.py                   # Calibration, walk-forward, model suite
│   ├── router.py                   # EV hurdle and proposal selection
│   ├── execution.py                # Paper broker, trade, journal
│   ├── backtest.py                 # Held-out replay
│   ├── reports.py                  # Calibration, importance, report bundle
│   ├── build.py                    # Pipeline assembly and artifact writing
│   └── domain/
│       ├── __init__.py
│       ├── timeframes.py           # Minute buckets and candles
│       ├── profile.py              # TPO profile, POC/VAH/VAL, excess
│       └── labels.py               # snapshot-horizon-v1 labels
├── chrome-extension/
│   ├── manifest.json               # MV3 manifest
│   ├── inject.js                   # Page-world WebSocket interception
│   └── content.js                  # Local forwarder with reconnect and queue
├── tests/                          # Unit tests for offline and streaming paths
├── docs/                           # Documentation tree (start at docs/00_ORIENTATION.md)
└── .gitignore
```

Removed and recoverable from git history: `amt/`, root `receiver.py`, root `test_receiver.py`, `sources/`, `scripts/`, scaffold tools.

---

## 3. How to Run / Setup

### Prerequisites

- Windows with PowerShell.
- Python 3.11 or newer.
- Google Chrome or a Chromium-based browser.
- An IQ Option account and access to the Traderoom.

### Create the environment

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

### Install the git hooks (once per clone)

```powershell
.\.venv\Scripts\python.exe tools\install_hooks.py
```

Points `core.hooksPath` at `.githooks/` so the `pre-commit` hook runs the documentation checker on every commit. Check it with `--status`; remove it with `git config --local --unset core.hooksPath`.

### Capture ticks

```powershell
.\.venv\Scripts\python.exe runner.py serve
```

Listens on `ws://localhost:8765` and persists accepted events and completed candles under `data/stream/`. Use `--capture-only` to store data without loading a model, or `--shadow` to load the model and journal decisions without opening paper trades; otherwise a compatible runtime `.joblib` artifact is required and paper trades are allowed. See [RUNBOOK.md](RUNBOOK.md).

### Load the extension

1. Open `chrome://extensions`.
2. Enable Developer mode.
3. Choose **Load unpacked** and select the `chrome-extension` folder.
4. Open or reload an IQ Option page.

### Build the dataset

```powershell
.\.venv\Scripts\python.exe runner.py diagnose --input data\ticks.csv
.\.venv\Scripts\python.exe runner.py build --input data\ticks.csv
```

Inputs may be `.csv`, `.jsonl`, or `.parquet`. Default input is `data/ticks.csv`. Outputs are `data/ticks.parquet`, `data/features.parquet`, `data/labels.parquet`, and `data/dataset.parquet`.

### Train and test

```powershell
.\.venv\Scripts\python.exe runner.py train
.\.venv\Scripts\python.exe runner.py backtest
```

`train` writes a timestamped `.joblib` suite and manifest; `model-check` validates runtime compatibility. `backtest` writes `reports/backtest.json` and `reports/backtest.md`.

### Run the tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
```

### Check the documentation

```powershell
.\.venv\Scripts\python.exe runner.py docs-check
```

Verifies that every doc under `docs/` has a status label, every relative link resolves, and every doc is reachable from `docs/index.md`. Exit code `0` means clean; `1` lists the offending files. Run it after any documentation change. It needs no configuration, so it works even when the TOML file is broken.

### Stop the receiver

Press `Ctrl+C`.

---

## 4. System Architecture

### Current Data Flow

```text
IQ Option Traderoom
    -> chrome-extension/inject.js        (MAIN world, filters name == "candle-generated")
    -> window.postMessage                (source = IQ_TICK_BRIDGE)
    -> chrome-extension/content.js       (isolated world, validates sender)
    -> ws://localhost:8765
    -> components/receiver.py            (validate, stamp received_at, buffer)
    -> engine.stream.StreamStore         (sequenced events, candles, state)
    -> engine.runtime.RuntimeEngine      (candle-close inference, paper decision)
    -> decision and trade journals       (JSONL; no broker orders)

Offline research:
    -> CSV / JSONL / Parquet
    -> runner.py build
    -> engine.store.TickStore            (stable timestamp/sequence order; duplicates preserved)
    -> engine.sampler                    (continuity gate, entry, exits)
    -> engine.features                   (core16-v2 + amt-v4)
    -> engine.domain.labels              (snapshot-horizon-v1)
    -> data/dataset.parquet
    -> engine.models                     (four calibrated classifiers)
    -> engine.router                     (EV hurdle, one proposal or no-trade)
    -> engine.backtest + execution        (paper trades, held-out replay)
    -> reports/backtest.{json,md}
```

The streaming runtime and offline path are implemented; they use the same causal feature function. The runtime router is deterministic and payout-aware. A learned selector, full risk layer, and broker execution remain unimplemented.

### Component Table

| Component | Responsibility | Location |
|-----------|----------------|----------|
| WebSocket intercept | Observe page WebSocket messages | `chrome-extension/inject.js` |
| Local forwarder | Forward raw payloads to the receiver | `chrome-extension/content.js` |
| Receiver | Validate, stamp `received_at`, buffer, call sink | `components/receiver.py` |
| Stream store | Sequenced events, candles, hourly Parquet, recovery | `engine/stream/` |
| Batch tick store | Contract, stable ordering, point-in-time lookup; preserves duplicates | `engine/store.py` |
| Snapshot sampler | Candle-close continuity gate, causal slice, entry/exit | `engine/sampler.py` |
| Domain primitives | Buckets, TPO profile, labels | `engine/domain/` |
| Feature engine | Stateless `core16-v2` + `amt-v4` | `engine/features.py` |
| Dataset builder | Join features and labels, write Parquet | `engine/build.py` |
| Model suite | Walk-forward training, calibration | `engine/models.py` |
| Router | EV hurdle, direction/horizon selection | `engine/router.py` |
| Paper broker | Open, hold, resolve paper trades | `engine/execution.py` |
| Backtest | Held-out replay | `engine/backtest.py` |
| Reports | Calibration, importance, JSON/Markdown | `engine/reports.py` |
| Runtime engine | Candle-close inference and paper decisions | `engine/runtime.py` |
| Risk controls | One open paper trade, cooldown, daily loss stop; not a full manager | `engine/runtime.py` |
| Execution adapters | Planned: demo/live | Planned |

---

## 5. Configuration

`config/default.toml` configures the engine. `engine/config.py` validates every section and raises `ConfigError` on unknown keys, wrong types, or impossible combinations. `runner.py --config <path>` selects another file.

| Section | Key | Default | Description |
|---------|-----|---------|-------------|
| `instrument` | `symbol` | `EURUSD` | Display name |
| `instrument` | `active_id` | `0` | Single active instrument |
| `instrument` | `pip_size` | `0.0001` | Pip size |
| `instrument` | `bin_size` | `0.00005` | TPO bin width |
| `candles` | `interval_seconds` | `60` | Bucket width |
| `context` | `macro_candles` | `7` | Completed bars in the macro window |
| `context` | `fast_candles` | `3` | Completed bars in the fast window |
| `context` | `profile_min_ticks` | `30` | Minimum ticks for a profile |
| `context` | `value_area_target` | `0.70` | Value Area share |
| `context` | `tail_bins` | `3` | Bins per tail |
| `context` | `single_print_max_ticks` | `1` | Single-print threshold |
| `context` | `volatility_min_changes` | `10` | Minimum changes for `sigma_7` |
| `context` | `epsilon` | `1e-9` | Numerical guard |
| `snapshot` | `entry_delay_ms` | `250` | Decision-to-entry delay |
| `snapshot` | `entry_tolerance_seconds` | `1.0` | Entry tick tolerance |
| `snapshot` | `exit_tolerance_seconds` | `5.0` | Exit tick tolerance |
| `snapshot` | `min_ticks_per_bar` | `1` | Completed-bar density gate |
| `labels` | `horizons_seconds` | `[60, 90, 120, 180]` | Prediction horizons |
| `labels` | `tie_policy` | `exclude` | `exclude` or `keep` |
| `router` | `min_ev` | `0.03` | EV hurdle per unit stake |
| `router` | `tie_break` | `earliest_horizon` | or `highest_ev` |
| `router.payouts` | per horizon | `0.80/0.82/0.84/0.86` | Payout by expiry |
| `models` | `engine` | `lightgbm` | or `sklearn` |
| `models` | `calibration` | `auto` | `isotonic`, `platt`, `none` |
| `models` | `purge_seconds` | `180` | Walk-forward purge |
| `models` | `embargo_seconds` | `0` | Optional embargo |
| `models` | `n_splits` | `5` | Walk-forward folds |
| `models` | `min_train_rows` | `500` | Skip threshold |
| `models` | `random_seed` | `7` | |
| `models` | `n_estimators` | `300` | |
| `models` | `learning_rate` | `0.03` | |
| `models` | `num_leaves` | `15` | |
| `models` | `min_child_samples` | `50` | |
| `models` | `runtime_path` | `data/models/suite.joblib` | Configured runtime artifact; timestamped training output is not auto-promoted |
| `execution` | `mode` | `paper` | `demo`/`live` are rejected |
| `execution` | `stake` | `1.0` | Fixed stake |
| `execution` | `max_open_trades` | `1` | Concurrency limit |
| `execution` | `cooldown_seconds` | `0` | Pause after a resolved paper trade |
| `execution` | `daily_loss_limit` | `5.0` | Daily realized-loss stop; `null` disables |
| `stream` | `root` | `data/stream` | Streaming event/candle store root |
| `stream` | `rotation_seconds` | `3600` | Validated setting; paths are fixed hourly |
| `stream` | `flush_events` | `500` | Count-based event flush threshold |
| `stream` | `max_buffer_events` | `50000` | Ingestion fails if this pending-event limit is exceeded |
| `store` | `root` | `data` | Artifact root |
| `store` | `ticks_path` | `data/ticks.parquet` | Tick store |
| `store` | `snapshots_path` | `data/snapshots.parquet` | Reserved |
| `store` | `models_path` | `data/models` | Suite directory |
| `store` | `reports_path` | `reports` | Report directory |
| `data` | `input_path` | `data/ticks.csv` | Default input |

### Receiver constants

| Key | Default | Description |
|-----|---------|-------------|
| `HOST` | `localhost` | Bind address |
| `PORT` | `8765` | WebSocket port |
| `HISTORY_LIMIT` | `500` | Raw messages per `active_id` |
| `ASSET_NAMES_PATH` | `asset_names.json` | Display-name map |

### Version constants

| Constant | Value |
|----------|-------|
| `FEATURE_VERSION` | `amt-v4` |
| `CORE_FEATURE_VERSION` | `core16-v2` |
| `LABEL_VERSION` | `snapshot-horizon-v1` |
| `CANDLE_VERSION` | `1m-clock-v1` |
| `DECISION_VERSION` | `candle-close-v1` |
| `MODEL_FORMAT_VERSION` | `joblib-v1` |

---

## 6. Key Domain Concepts

| Concept | Definition |
|---------|------------|
| Tick event | One accepted live price update forwarded by the extension; not an exchange trade print |
| `active_id` | Primary instrument key in the tick payload |
| Whole-minute bucket | Clock-aligned 60-second interval built from ticks |
| Forming bar | The current, incomplete minute; never enters the profile |
| TPO | Time-Price Opportunity: tick count per price bin, a volume proxy |
| POC | Price bin with the highest tick count |
| VAH / VAL | Edges of the range containing about 70% of recent ticks |
| Excess / single print | Rejection tail with very few ticks at an extreme |
| Snapshot | A validated decision point at a completed candle close |
| Continuity gate | Requirement for 7 contiguous completed candles with enough ticks |
| Delayed entry | First tick at or after snapshot time + 250ms within tolerance |
| Exit | First tick at or after actual entry + horizon within tolerance |
| Tie | Exit price equals entry price; non-directional, void in execution |
| Payout | Broker profit rate on a winning binary option |
| Breakeven win rate | `1 / (1 + payout)` |
| EV per trade | `q_hat * (1 + payout) - 1` |
| EV hurdle | Minimum EV required to trade (`router.min_ev`) |
| No-trade | Explicit abstention with a reason code |
| Held-out evaluation slice | Later 30% of walk-forward OOS; the only data the backtest may replay |
| Overlap weight | `1 / max(1, horizon / snapshot spacing)` |

---

## 7. Known Decisions and Rationale

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-11-18 | Describe the capture layer as a PoC | At the time it had no candles, persistence, features, or models |
| 2026-11-18 | Treat each accepted frame as a tick/price update | The frame is a live price update; exact candle semantics are unverified |
| 2026-11-18 | Do not trust the payload `volume` field | Not verified as traded volume; tick density is the TPO proxy |
| 2026-11-18 | Build 1-minute candles clock-aligned in absolute time | Avoids broker candle events and DST ambiguity |
| 2026-11-18 | Treat AMT on OTC as a hypothesis with a validation gate | OTC pricing may be synthetic and lacks real auction participants |
| 2026-11-18 | Payout-aware evaluation is mandatory | Accuracy below the payout breakeven loses money |
| 2026-11-18 | One timestamp per tick: local receipt time with offset | Removes the unverified `at` ambiguity |
| 2026-11-18 | One active instrument at a time | Simplifies storage, features, and validation |
| 2026-11-18 | Value Area expands in pairs over non-empty bins | Prevents empty edge bins from distorting VAH/VAL |
| 2026-11-18 | Drop exact duplicate `(timestamp, price)` ticks (superseded 2026-11-21) | Former policy to prevent inflated tick density |
| 2026-11-19 | Rename the entry point to `runner.py`; move capture to `components/receiver.py` | Tick capture is one component, not the system |
| 2026-11-19 | Absorb `amt/` into a single `engine/` package | One importable, testable engine with domain primitives separate |
| 2026-11-19 | Evaluate snapshots at configurable minute offsets, default `:30` (superseded 2026-11-21) | Former fixed decision point to avoid tick-level row explosion |
| 2026-11-19 | Require 7 contiguous completed bars before a snapshot | Makes the feature window unambiguous and gap-free |
| 2026-11-19 | Entry is the first tick at or after snapshot + 250ms | Prices the trade at a moment the engine could act |
| 2026-11-19 | Exit is measured from actual entry, not snapshot time | The contract expires from the real fill |
| 2026-11-19 | Keep exactly 16 model inputs (`core16-v1`, version superseded) | Normalised features transfer; raw levels and time features invite overfitting |
| 2026-11-19 | Four binary classifiers instead of one multi-class model | Horizons have different payouts and noise; skipping is clean |
| 2026-11-19 | Purged walk-forward with 180s purge and overlap weights | Overlapping label windows must not be treated as independent |
| 2026-11-19 | Split walk-forward OOS 70/30 chronologically | Calibrator and evaluation must not share rows |
| 2026-11-19 | The backtest may only replay the held-out evaluation slice | Prevents in-sample replay, which produced invalid results earlier |
| 2026-11-19 | Reject a non-increasing Platt fit | A negative slope would invert every decision |
| 2026-11-19 | EV hurdle `+0.03`, single best candidate, explicit no-trade | Conservative and auditable; never clamp a probability |
| 2026-11-19 | Paper execution only; demo/live raise `ExecutionError` | No risk layer or execution adapter exists |
| 2026-11-19 | Persist ticks as daily JSONL, analysis as Parquet (superseded 2026-11-21) | Former append-only capture design; streaming now writes hourly Parquet parts |
| 2026-11-19 | Import LightGBM before pandas | Prevents a Windows DLL access violation in `LGBM_DatasetSetField` |
| 2026-11-19 | Keep the two-stage regime design as research only | No validated regime rule and not enough rows per regime |
| 2026-11-20 | Version the pre-commit hook in `.githooks/` and install it by setting `core.hooksPath` | Hooks stay reviewable with the code; no copy step into `.git/hooks` |
| 2026-11-20 | Have the hook call `tools/check_docs.py` directly | Needs only the standard library, so it still runs when LightGBM or the venv is broken |
| 2026-11-20 | Treat Pocket Auto v3 as reference material, not the IQ Option implementation target | Keep repository facts and project plans distinct |
| 2026-11-20 | Plan `.joblib` as the runtime artifact naming convention; retain `suite.pkl` as current behavior (superseded 2026-11-21) | Former offline-only artifact design; current runtime uses manifest-validated `.joblib` |
| 2026-11-20 | Evaluate a learned direction/horizon/no-trade selector against the deterministic EV router; keep payout/risk/execution constraints as hard gates | ML selection is the target, but market evidence and non-ML safety limits remain mandatory |
| 2026-11-20 | Fail closed for ML proposals when a configured runtime artifact is missing or incompatible | No silent fallback to a stale or different model; surface an explicit diagnostic |
| 2026-11-21 | Candle-close streaming runtime uses `core16-v2` / `amt-v4` and manifest-validated `.joblib`; paper decisions do not place broker orders | Keep current runtime behavior distinct from the learned selector and demo/live execution |
| 2026-11-21 | Preserve repeated accepted events with distinct sequence identities; report exact timestamp/price repeats rather than deduplicating | Maintain the capture record and make tick-density impact measurable |
| 2026-11-21 | Use one candle-close decision per eligible minute instead of the former `:30` snapshot offset | Align offline snapshots and runtime decisions to finalized candles |
| 2026-11-21 | Synchronize operator and system docs with the streaming/runtime implementation | Document behavior and limitations without changing code |
| 2026-11-22 | Implement `serve --shadow`; shadow journals router and gate outcomes without opening paper trades | Record baseline predictions for parity comparison without accumulating paper positions |
| 2026-11-22 | Accept a stream events directory in `build` and `diagnose` | Close the capture-to-research loop without a manual conversion step |
| 2026-11-22 | Reload paper trades from `trades.jsonl` at startup and fail closed on a corrupt journal | Keep the one-open-trade, cooldown, and daily loss gates across restarts |
| 2026-11-22 | Use `docs/system/16_STREAMING_RUNTIME_AND_STORE.md` as the current implementation doc and keep the migration record in `docs/planning/streaming-runtime-and-store.md` | Separate current behavior from historical planning |
| 2026-11-22 | Keep `[stream]` paths fixed under `root`; do not add `state_file`/`decisions_dir` keys | One validated root avoids path combinations the store does not support |

### Known Limitations

- Frame semantics, real tick cadence, and feed completeness are unverified.
- Runtime inference, shadow mode, and paper decisions exist, but sustained shadow/paper parity and a real-data edge have not been established.
- No broker order adapter, learned selector, complete risk manager, or kill switch.
- Streaming events and candles persist in hourly parts; offline snapshots are not stored separately, and stream retention/compaction is undefined.
- Batch `build` is not incremental; the runtime rolling candle window warms up after restart.
- Single instrument only; the sampler filters to one `active_id`.
- Held-out evaluation is small; metrics are noisy.
- No rule-based baseline, drift monitoring, or per-fold/per-session report breakdowns.
- Receiver host/port have CLI overrides, but capture buffer and other receiver constants remain in code.
- The router is deterministic. Selector target, scope, and promotion criteria remain unimplemented.

See [`docs/system/10_LIMITATIONS_AND_BACKLOG.md`](docs/system/10_LIMITATIONS_AND_BACKLOG.md).

---

## 7a. Documentation Audiences

| Audience | Primary Docs | Purpose |
|----------|--------------|---------|
| Newcomers and returning developers | `docs/00_ORIENTATION.md` | Pipeline with real numbers, the 16/31 feature split, reading order |
| AI agents and developers | `AGENTS.md` | Source of truth, architecture, commands, decisions |
| Operators | `README.md`, `RUNBOOK.md` | Setup, running, troubleshooting |
| System designers | `docs/system/` | Current architecture and contracts |
| Data and ML researchers | `docs/data/`, `docs/research/` | Contracts, formulas, validation, OTC caveats |
| Project planning | `docs/planning.md`, `docs/planning/` | Phases, milestones, acceptance criteria |
| Everyone | `docs/index.md` | File finder; enforced by `runner.py docs-check` |

---

## 7b. Removed Features and Anti-Patterns

Removed and recoverable from git history: `amt/` package, root `receiver.py`, root `test_receiver.py`, `sources/`, `scripts/`, scaffold tools.

### Anti-Patterns

- Treating the payload `volume` field as real traded volume.
- Assuming `at` is a tick timestamp without verification.
- Using future data in features or labels.
- Random-splitting time-series data.
- Calling `predict_vector` in a backtest instead of replaying the held-out evaluation slice.
- Fitting a calibrator on the evaluation slice.
- Lowering `min_ev` until trades appear.
- Reporting AUC or accuracy as profitability.
- Mapping a tie or a missing exit to a direction.
- Trading before payout breakeven and calibration are measured.
- Martingale or loss-doubling without explicit limits.
- Live trading without a risk layer, kill switch, and audit log.
- Hard-coding configuration that belongs in `config/default.toml`.
- Writing bare `python` or `pytest`; use the virtual environment path.
- Storing credentials, SSIDs, or account data in the repository.
- Describing planned components as implemented.
- Importing pandas before `engine` on Windows.
- Adding or moving a doc without running `runner.py docs-check`.

---

## 8. Agent Rules

1. **Keep this file current** — update it when architecture, commands, or decisions change.
2. **Do not overstate the system** — runtime paper inference exists, but there is no broker execution or validated edge.
3. **Preserve the tick/candle distinction** — events are captured; streaming candles are persisted and offline candles are rebuilt from file inputs.
4. **Record decisions** — add a row to the decision log and a change-log entry.
5. **Use copy-paste-ready PowerShell commands** with the virtual environment path.
6. **Run tests after changes** — `.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v`.
7. **Keep docs organised** — concepts for why, data for what, system for how, research for history; `docs/00_ORIENTATION.md` is the entry point.
8. **Use status labels** — `Status: Current`, `Status: Planning`, or `Status: Historical`.
9. **Run the documentation checker** — `.\.venv\Scripts\python.exe runner.py docs-check` must exit `0` after any doc change. The `pre-commit` hook runs it automatically once `tools/install_hooks.py` has been run.
10. **No lookahead** — feature and label code must be causal by construction.
11. **No secrets in the repo** — `.env` and credentials stay local.
12. **No live execution without the gate** — see `docs/system/09_MODEL_VALIDATION.md`.
13. **Keep scaffold-time tools and removed inputs out of the repo.**
14. **Never replay in-sample probabilities** — the backtest uses `ModelSuite.evaluate_snapshot` only.
15. **Never map a tie or missing exit to a direction** — keep both explicit and unusable for directional training.
16. **Import `engine` before pandas** — protects the LightGBM Windows DLL ordering.
17. **Do not change a version string without changing the definition** — versions trace artefacts to code.
18. **Keep current and planned ML behavior separate** — runtime `.joblib` loading and deterministic paper decisions exist; the learned selector and broker order execution do not.
19. **Use Pocket Auto v3 only as reference material** — do not conflate its optimizer ML or signal engines with the IQ Option implementation.

---

## 9. Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-11-18 | Replaced the generic agent template with the project-specific guide | Documentation agent |
| 2026-11-18 | Documented the tick-capture PoC and separated it from the target bot | Documentation agent |
| 2026-11-18 | Added tick stream, candle, AMT, ML, validation, and backlog docs | Documentation agent |
| 2026-11-18 | Added the phased roadmap, improvement backlog, and go/no-go gate | Documentation agent |
| 2026-11-18 | Locked one receipt timestamp, one instrument, and the 7/3/forming model | Documentation agent |
| 2026-11-18 | Added the offline `amt` package with 36 unit tests | Implementation agent |
| 2026-11-18 | Removed `sources/` and `scripts/`; introduced the documentation checklist | Documentation agent |
| 2026-11-19 | Introduced `runner.py` and the `engine/` package; retired `amt/` and root `receiver.py` | Implementation agent |
| 2026-11-19 | Added tick store, snapshot gate, `core16-v1`, `amt-v3`, `snapshot-horizon-v1` | Implementation agent |
| 2026-11-19 | Added the calibrated model suite, held-out evaluation table, router, and paper backtest | Implementation agent |
| 2026-11-19 | Added system docs 11–15, data docs 07–09, and rewrote the affected docs | Documentation agent |
| 2026-11-19 | Rewrote README, RUNBOOK, and the docs index for the `engine/` layout and `runner.py` commands | Documentation agent |
| 2026-11-19 | Added `docs/00_ORIENTATION.md` and moved the docs checker into `tools/check_docs.py` with `runner.py docs-check` | Documentation agent |
| 2026-11-19 | Test suite expanded to 111 unit tests | Implementation agent |
| 2026-11-19 | Test suite expanded to 117 with `tests/test_docs.py` | Implementation agent |
| 2026-11-20 | Added the versioned `.githooks/pre-commit` documentation check and `tools/install_hooks.py`; test suite is 121 | Implementation agent |
| 2026-11-20 | Documented the distinction between current offline ML, deterministic routing, and the planned `.joblib` runtime and learned selector | Documentation agent |
| 2026-11-21 | Updated the guide for streaming persistence, candle-close inference, model manifests, paper runtime gates, and remaining validation gaps | Documentation agent |
| 2026-11-22 | Added shadow mode, stream-directory build input, and restart-safe paper gates; recorded the migration deviations | Implementation agent |

---

## 10. Last Updated

**2026-11-22 by Implementation agent**

# IQ Option Bot — Agent Guide

Status: Current

> **This file is the single source of truth for any AI agent or developer working in this repository.** Read it fully before making changes. Keep it current when architecture, commands, or decisions change.

---

## 1. What This System Does

IQ Option Bot is a local, documentation-driven project for capturing live IQ Option tick data through a Chrome extension and a Python WebSocket receiver, reconstructing auction-style market structure from those ticks, and eventually testing a payout-aware trading model. The current repository is a **live tick-capture proof of concept**: the extension forwards browser WebSocket messages to `receiver.py`, which validates and logs them. Candle generation, AMT features, machine learning, risk management, and order execution are planned and must not be described as implemented.

---

## 2. Repository Layout

Final merged layout:

```text
iqoption-bot/
├── README.md                       # Project entry point
├── AGENTS.md                       # THIS FILE — agent guide and source of truth
├── RUNBOOK.md                      # Operating procedures for the PoC
├── receiver.py                     # Local WebSocket receiver
├── test_receiver.py                # Receiver unit tests
├── requirements.txt                # Python dependencies
├── asset_names.json                # active_id → display-name map
├── chrome-extension/
│   ├── manifest.json               # MV3 manifest
│   ├── inject.js                   # Page-world WebSocket interception
│   └── content.js                  # Local forwarder with reconnect and queue
├── amt/                            # Offline AMT feature and label pipeline
│   ├── __init__.py
│   ├── config.py                   # TOML config loading and validation
│   ├── timeframes.py               # Minute buckets, forming vs completed
│   ├── profile.py                  # TPO profile, POC/VAH/VAL, excess
│   ├── features.py                 # amt-v2 features, one row per tick
│   ├── labels.py                   # Tick-horizon labels
│   ├── data.py                     # Tick loading, dedupe, CSV output
│   └── build.py                    # Offline CLI
├── config/
│   └── default.toml                # Active instrument and pipeline settings
├── tests/                          # AMT unit tests
│   ├── test_config.py
│   ├── test_data.py
│   ├── test_timeframes.py
│   ├── test_profile.py
│   ├── test_features.py
│   └── test_labels.py
├── docs/
│   ├── index.md
│   ├── planning.md
│   ├── planning/
│   ├── concepts/
│   ├── data/
│   ├── system/
│   └── research/
└── .gitignore
```

The documentation tree is the permanent home for project knowledge. Scaffold-time tools (`prompt.md`, `extract.md`, `MERGE_BACK.md`, `HOW_TO.md`, `profiles/`, `sources/`, and `scripts/`) were used only during migration and are no longer part of the repository. Their useful content is in `docs/`; raw inputs remain in git history.

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

### Run the receiver

```powershell
.\.venv\Scripts\python.exe receiver.py
```

The receiver listens on `ws://localhost:8765`.

### Load the extension

1. Open `chrome://extensions`.
2. Enable Developer mode.
3. Choose **Load unpacked** and select the `chrome-extension` folder.
4. Open or reload an IQ Option page.

### Run the tests

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_receiver
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
```

### Build AMT features and labels offline

```powershell
.\.venv\Scripts\python.exe -m amt.build --input data\ticks.csv
```

Input CSV columns: `timestamp,price` plus an optional `active_id`. Timestamps must be ISO 8601 with an offset. Outputs default to `data/features.csv` and `data/labels.csv`, which are gitignored.

### Stop the receiver

Press `Ctrl+C` in the receiver terminal.

---

## 4. System Architecture

### Current Data Flow

```text
IQ Option Traderoom
    -> page WebSocket
    -> chrome-extension/inject.js        (MAIN world, filters name == "candle-generated")
    -> window.postMessage                (source = IQ_TICK_BRIDGE)
    -> chrome-extension/content.js       (isolated world, validates sender)
    -> ws://localhost:8765
    -> receiver.py                       (validate, buffer, log)
    -> deque(maxlen=500) per active_id
```

### Target Data Flow

```text
Tick stream
    -> ingestion and validation
    -> raw tick store
    -> 1-minute candle builder
    -> TPO/Value Area + AMT feature engine
    -> label builder (binary outcome, payout-aware EV)
    -> two-stage model
    -> signal and risk layer
    -> paper/demo/live execution
    -> trade journal and monitoring
```

### Key Components

| Component | Responsibility | Location |
|-----------|----------------|----------|
| WebSocket intercept | Observe page WebSocket messages | `chrome-extension/inject.js` |
| Local forwarder | Forward raw payloads to the receiver | `chrome-extension/content.js` |
| Receiver | Validate, buffer, and log ticks | `receiver.py` |
| Asset map | Map `active_id` to display names | `asset_names.json` |
| Candle bucketing | Group ticks into whole-minute candles | `amt/timeframes.py` (offline) |
| TPO/profile engine | Compute POC/VAH/VAL, excess, tails | `amt/profile.py` (offline) |
| Feature engine | Build `amt-v2` rows, one per tick | `amt/features.py` (offline) |
| Label builder | 60/90/120/180s tick-horizon labels | `amt/labels.py` (offline) |
| Model service | Train, calibrate, and serve models | Planned |
| Risk manager | Stake sizing, limits, kill switch | Planned |
| Execution adapter | Paper, demo, and live orders | Planned |

"Offline" means implemented and tested as a library, but not yet wired to the live receiver.

---

## 5. Configuration

Receiver constants still live in code. The AMT pipeline reads `config/default.toml`.

### `config/default.toml`

| Section | Key | Default | Description |
|---------|-----|---------|-------------|
| `instrument` | `symbol` | `EURUSD` | Active instrument display name |
| `instrument` | `active_id` | `0` | Active instrument key |
| `instrument` | `pip_size` | `0.0001` | Pip size |
| `instrument` | `bin_size` | `0.00005` | TPO profile bin size |
| `candles` | `interval_seconds` | `60` | Candle bucket size |
| `context` | `macro_candles` | `7` | Completed candles in the macro window |
| `context` | `fast_candles` | `3` | Completed candles in the fast window |
| `context` | `profile_min_ticks` | `30` | Minimum ticks for a non-null profile |
| `context` | `value_area_target` | `0.70` | Value Area share |
| `context` | `tail_bins` | `3` | Bins inspected per tail |
| `context` | `single_print_max_ticks` | `1` | Tick count treated as a single print |
| `context` | `volatility_min_changes` | `10` | Minimum price changes for `sigma_7` |
| `labels` | `horizons_seconds` | `[60, 90, 120, 180]` | Prediction horizons |
| `labels` | `exit_tolerance_seconds` | `5.0` | Exit match tolerance |
| `labels` | `tie_policy` | `exclude` | `exclude` or `keep` |
| `data` | `input_path` | `data/ticks.csv` | Default tick input |
| `data` | `features_path` | `data/features.csv` | Default feature output |
| `data` | `labels_path` | `data/labels.csv` | Default label output |

### `receiver.py`

| Key | Default | Description |
|-----|---------|-------------|
| `HOST` | `localhost` | Bind address |
| `PORT` | `8765` | WebSocket port |
| `HISTORY_LIMIT` | `500` | Raw messages retained per `active_id` |
| `ASSET_NAMES_PATH` | `asset_names.json` | Display-name map path |

### `chrome-extension/content.js`

| Key | Default | Description |
|-----|---------|-------------|
| `SERVER_URL` | `ws://localhost:8765` | Receiver address |
| `RECONNECT_DELAY_MS` | `2000` | Reconnect delay |
| `MAX_QUEUED_MESSAGES` | `500` | Queue limit; oldest dropped when full |

Planned receiver and execution configuration is specified in [`docs/system/03_CONFIGURATION.md`](docs/system/03_CONFIGURATION.md).

---

## 6. Key Domain Concepts

| Concept | Definition |
|---------|------------|
| Tick event | One accepted live price update forwarded by the extension; not an exchange trade print |
| `active_id` | Primary instrument key in the tick payload |
| 1-minute candle | Planned clock-aligned UTC OHLCV aggregate built from ticks; not generated today |
| TPO | Time-Price Opportunity: tick count per price bin, used as a volume proxy |
| POC | Point of Control: price bin with the highest tick count |
| VAH / VAL | Value Area High / Low: edges of the range containing about 70% of recent ticks |
| Balance | Rotational trade inside the value area |
| Imbalance | Directional trade outside the value area with initiative velocity |
| Excess / single print | Rejection tail with very few ticks at an extreme |
| Initiative / responsive | Breakout continuation vs mean reversion at a value-area boundary |
| Payout | Broker profit rate on a winning binary option |
| Breakeven win rate | `1 / (1 + payout)` |
| EV per trade | `q_hat * payout - (1 - q_hat)` for predicted win probability `q_hat` |
| No-trade | Explicit abstention when edge, data quality, or risk is insufficient |

---

## 7. Known Decisions and Rationale

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-11-18 | Stage project docs in `docs-driven/` first, then merge | Keeps the scaffold workflow reviewable and the repo root untouched until the docs are coherent |
| 2026-11-18 | Describe the current system as a tick-capture PoC | The receiver has no candle generation, persistence, features, ML, or execution |
| 2026-11-18 | Treat each accepted frame as a tick/price update | The frame is a live price update; its exact candle semantics are unverified |
| 2026-11-18 | Do not trust the payload `volume` field | It is not verified as traded volume; tick density is the TPO proxy |
| 2026-11-18 | Build 1-minute candles from ticks, clock-aligned to UTC | User requirement; avoids relying on broker candle events |
| 2026-11-18 | Use tick count as candle volume | Payload volume is untrusted; tick count is reproducible |
| 2026-11-18 | Treat AMT on OTC as a hypothesis with a validation gate | The OTC feed may be synthetic and lacks real auction participants |
| 2026-11-18 | Approach A (two-stage regime) is primary; Approach B is research | Separating balance and imbalance avoids mixing incompatible behaviour |
| 2026-11-18 | Rule-based AMT baseline before ML | Establishes a performance floor and sanity check |
| 2026-11-18 | Paper/demo before live execution | Real-money automation requires tested risk controls and a kill switch |
| 2026-11-18 | Payout-aware evaluation is mandatory | Accuracy below the payout breakeven loses money |
| 2026-11-18 | One timestamp per tick: local receipt time with offset | Removes the unverified `at` ambiguity and keeps ordering local and explicit |
| 2026-11-18 | One active instrument at a time | Simplifies storage, features, and validation; multi-instrument is a future item |
| 2026-11-18 | Predictions are tick-based at 60/90/120/180s | Binary options allow arbitrary entry; candles are context, not decision points |
| 2026-11-18 | Macro 7 / fast 3 / forming context layers | Compares current activity against recent and slower context without fixed short windows |
| 2026-11-18 | `sigma_7` from tick price changes over completed candles | Matches the normalisation window and stays in price units |
| 2026-11-18 | Profile from the last 7 completed candles | Keeps the forming candle out of value until it completes |
| 2026-11-18 | Value Area expands in pairs over non-empty bins | Prevents empty edge bins from distorting VAH/VAL |
| 2026-11-18 | Drop exact duplicate `(timestamp, price)` ticks | Prevents inflated tick density |
| 2026-11-18 | The offline `amt` package is canonical; the external sample is a reference | The sample mixed features, labels, and a weak backtest and violated several specs |
| 2026-11-18 | Remove `sources/` and `scripts/` after absorption | Raw inputs and scaffold validators are preserved in git history |

### Known Limitations

- Tick cadence, frame semantics, and completeness are not yet verified.
- The receiver does not record receipt time yet; the offline pipeline assumes it exists.
- The receiver buffer is in memory and holds only 500 raw messages per `active_id`.
- No raw tick persistence, live candle store, or replay exists.
- The `amt` package is offline only and has no live receiver integration.
- The feature build loops per tick and is not yet vectorised or incremental.
- No labels join, model, calibration, backtest, risk, or execution exists.
- The extension can drop the oldest queued message while disconnected.
- Tests cover the receiver and the `amt` package, but not live-to-offline parity.

See [`docs/system/10_LIMITATIONS_AND_BACKLOG.md`](docs/system/10_LIMITATIONS_AND_BACKLOG.md).

---

## 7a. Documentation Audiences

| Audience | Primary Docs | Purpose |
|----------|--------------|---------|
| AI agents and developers | `AGENTS.md` | Source of truth, architecture, commands, decisions |
| Operators | `README.md`, `RUNBOOK.md` | Setup, running, troubleshooting |
| System designers | `docs/system/` | Current architecture and planned components |
| Data and ML researchers | `docs/data/`, `docs/research/` | Contracts, formulas, validation, OTC caveats |
| Project planning | `docs/planning.md`, `docs/planning/` | Phases, milestones, acceptance criteria |
| Everyone | `docs/index.md` | File finder |

---

## 7b. Removed Features and Anti-Patterns

No features have been removed yet.

### Anti-Patterns

- Treating the payload `volume` field as real traded volume.
- Calling the in-memory buffer “candle history”.
- Assuming `at` is a tick timestamp without verification.
- Using future data in features or labels.
- Random-splitting time-series data.
- Training a model before building a rule-based baseline.
- Trading before payout breakeven and calibration are measured.
- Martingale or loss-doubling without explicit limits.
- Live trading without a kill switch and audit log.
- Hard-coding configuration that should be in a config file.
- Writing bare `python` or `pytest` in documentation; use the virtual environment path.
- Storing credentials, SSIDs, or account data in the repository.
- Building execution before the validation gate passes.

---

## 8. Agent Rules

1. **Keep this file current** — update it when architecture, commands, or decisions change.
2. **Do not overstate the system** — the receiver is a PoC until the docs say otherwise.
3. **Preserve the tick/candle distinction** — ticks are current; 1-minute candles are planned.
4. **Record decisions** — add a row to the decision log and a change-log entry.
5. **Use copy-paste-ready PowerShell commands** with the virtual environment path.
6. **Run tests after changes** — `.\.venv\Scripts\python.exe -m unittest -v test_receiver`.
7. **Keep docs organised** — concepts for why, data for what, system for how, research for history.
8. **Use status labels** — `Status: Current`, `Status: Planning`, or `Status: Historical`.
9. **Do not link to non-existent docs** — every link in `docs/index.md` must resolve.
10. **No lookahead** — feature and label code must be causal by construction.
11. **No secrets in the repo** — `.env` and credentials stay local.
12. **No live execution without the gate** — see `docs/system/09_MODEL_VALIDATION.md`.
13. **Keep scaffold-time tools and removed inputs out of the repo** — `prompt.md`, `extract.md`, `MERGE_BACK.md`, `HOW_TO.md`, and `profiles/` are not project docs; do not recreate `sources/` or `scripts/` either.
14. **Raw inputs live in git history** — synthesize future changes into `docs/`.
15. **Run the AMT tests after changing `amt/`** — `.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v`.
16. **Use the documentation checklist** — `docs/system/05_TESTING.md` replaces the removed scaffold validator.
17. **Never map a tie or missing exit to a direction** — keep both explicit and unusable for directional training.

---

## 9. Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-11-18 | Replaced the generic agent template with the project-specific guide | Documentation agent |
| 2026-11-18 | Documented the current tick-capture PoC and separated it from the target bot | Documentation agent |
| 2026-11-18 | Added tick stream, candle aggregation, AMT, ML, validation, and backlog docs | Documentation agent |
| 2026-11-18 | Added the phased roadmap, improvement backlog, and go/no-go gate | Documentation agent |
| 2026-11-18 | Locked one local receipt timestamp, one active instrument, tick-based horizons, and the 7/3/forming context model | Documentation agent |
| 2026-11-18 | Added the offline `amt` package with `amt-v2` features and `tick-horizon-v1` labels, plus 36 unit tests | Implementation agent |
| 2026-11-18 | Removed `sources/` and `scripts/`; replaced the scaffold validator with a documented checklist | Documentation agent |

---

## 10. Last Updated

**2026-11-18 by Documentation and Implementation agents**

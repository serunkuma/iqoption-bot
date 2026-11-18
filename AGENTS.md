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
├── scripts/
│   ├── validate_scaffold.sh        # Documentation health checks
│   └── validate_scaffold.ps1       # Windows equivalent
├── sources/                        # Frozen inputs (historical)
│   ├── README.md
│   ├── PROJECT_CONTEXT.md
│   ├── INTERVIEW_TRANSCRIPT.md
│   └── AMT_ML_DISCUSSION.md
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

The documentation tree is the permanent home for project knowledge. Scaffold-time tools (`prompt.md`, `extract.md`, `MERGE_BACK.md`, `HOW_TO.md`, `profiles/`) were used only during the initial documentation migration and are not part of the repository.

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
```

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
| Candle builder | Aggregate ticks into 1-minute OHLCV | Planned |
| TPO/feature engine | Compute POC/VAH/VAL and AMT features | Planned |
| Model service | Train, calibrate, and serve models | Planned |
| Risk manager | Stake sizing, limits, kill switch | Planned |
| Execution adapter | Paper, demo, and live orders | Planned |

---

## 5. Configuration

There is no config file yet. Current constants live in code.

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

Planned configuration is specified in [`docs/system/03_CONFIGURATION.md`](docs/system/03_CONFIGURATION.md).

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

### Known Limitations

- Tick cadence, `at` semantics, and completeness are not yet verified.
- The receiver buffer is in memory and holds only 500 raw messages per `active_id`.
- No raw tick persistence, candle aggregation, AMT features, ML, or execution exists.
- The extension can drop the oldest queued message while disconnected.
- The current tests cover only a small part of the receiver.

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
13. **Keep scaffold-time tools out of the merged repo** — `prompt.md`, `extract.md`, `MERGE_BACK.md`, `HOW_TO.md`, and `profiles/` are not project docs.
14. **`sources/` is frozen** — do not edit raw inputs; synthesize changes into `docs/`.
15. **Run the docs validator after structural changes** — `scripts/validate_scaffold.ps1` on Windows.

---

## 9. Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-11-18 | Replaced the generic agent template with the project-specific guide | Documentation agent |
| 2026-11-18 | Documented the current tick-capture PoC and separated it from the target bot | Documentation agent |
| 2026-11-18 | Added tick stream, candle aggregation, AMT, ML, validation, and backlog docs | Documentation agent |
| 2026-11-18 | Added the phased roadmap, improvement backlog, and go/no-go gate | Documentation agent |

---

## 10. Last Updated

**2026-11-18 by Documentation agent**

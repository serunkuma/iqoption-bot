# IQ Option Bot

Status: Current

> **Current status: live tick-capture proof of concept, plus an offline AMT feature library.** The project captures IQ Option browser WebSocket messages and logs them locally. An offline `amt` package builds TPO/Value Area features and tick-horizon labels from a tick CSV. It does **not** persist live ticks, run a model, place trades, or manage risk. Do not use it with real money.

---

## What It Does Today

- A Chrome Manifest V3 extension runs on `*.iqoption.com`.
- `inject.js` observes the page's WebSocket messages.
- `content.js` forwards matching payloads to `ws://localhost:8765`.
- `receiver.py` validates each frame, keeps the last 500 raw messages per `active_id` in memory, and logs OHLCV fields.
- `asset_names.json` maps `active_id` values to human-readable names for logs.
- `amt/` builds `amt-v2` features and `tick-horizon-v1` labels offline from a tick CSV.

The receiver console has been manually verified to show live prices from the platform. The offline pipeline is unit-tested but is not yet fed by the receiver.

## What It Does Not Do Yet

- No live 1-minute candle generation.
- No persistent tick storage or replay.
- No live AMT feature computation; the `amt` package is offline only.
- No model, calibration, or signals.
- No risk controls.
- No order execution.
- No backtesting.

## Quick Start

### 1. Create the environment

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

### 2. Start the receiver

```powershell
.\.venv\Scripts\python.exe receiver.py
```

The receiver listens on `ws://localhost:8765`.

### 3. Load the extension

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Select **Load unpacked** and choose the `chrome-extension` folder.
4. Open or reload an IQ Option page.

The extension reconnects every two seconds after a disconnect. While disconnected it queues up to 500 messages and drops the oldest when full.

### 4. Verify ticks

Watch the receiver console. Each accepted frame logs the asset identity, `close`, `open`, `min`, `max`, `volume`, `at`, and buffer length.

### 5. Run the tests

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_receiver
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
```

### 6. Build AMT features and labels offline

Prepare a CSV with `timestamp,price` and an optional `active_id`, then run:

```powershell
.\.venv\Scripts\python.exe -m amt.build --input data\ticks.csv
```

Timestamps must be ISO 8601 with an offset. Outputs default to `data/features.csv` and `data/labels.csv`, which are gitignored.

## Architecture

```text
IQ Option page WebSocket
    -> chrome-extension/inject.js
    -> chrome-extension/content.js
    -> ws://localhost:8765
    -> receiver.py
    -> in-memory raw message buffer (500 per active_id)
    -> console log

Offline, from a tick CSV:
    -> amt/timeframes.py   (whole-minute candles, forming vs completed)
    -> amt/profile.py      (TPO, POC, VAH, VAL, excess)
    -> amt/features.py     (amt-v2, one row per tick)
    -> amt/labels.py       (60/90/120/180s tick-horizon labels)
```

The target architecture adds raw tick persistence, live candles, a two-stage model, risk controls, and paper/demo-first execution. See the [system overview](docs/system/01_OVERVIEW.md).

## Documentation

- [docs/index.md](docs/index.md) — full documentation index
- [AGENTS.md](AGENTS.md) — source of truth for agents and developers
- [RUNBOOK.md](RUNBOOK.md) — operating the current PoC
- [docs/system/01_OVERVIEW.md](docs/system/01_OVERVIEW.md) — current vs target architecture
- [docs/data/01_TICK_STREAM.md](docs/data/01_TICK_STREAM.md) — what a tick means here
- [docs/planning.md](docs/planning.md) — roadmap and phases
- [docs/system/10_LIMITATIONS_AND_BACKLOG.md](docs/system/10_LIMITATIONS_AND_BACKLOG.md) — what to improve next

## Roadmap Summary

1. Harden tick capture: verify semantics, persist raw ticks, add quality checks and configuration.
2. Build 1-minute candles and AMT/TPO features.
3. Build and validate the ML pipeline.
4. Add paper/demo execution, risk controls, and operations.

## Safety

- This is a research project, not financial advice.
- Automated trading may violate IQ Option’s terms or local regulations; verify eligibility and platform rules before any live use.
- Real-money trading is not supported by the current code.
- Live execution requires paper/demo testing, calibrated validation, hard risk limits, and a kill switch.
- Never commit credentials, SSIDs, or account data.

## Requirements

- Windows with PowerShell.
- Python 3.11 or newer.
- Chrome or a Chromium-based browser.
- `numpy>=1.26,<3` and `websockets>=12,<16`.

---

*Last updated: 2026-11-18*

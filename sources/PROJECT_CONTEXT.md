# Project Context — IQ Option Bot

Status: Historical
Date: 2026-11-18
Source: Extracted from the existing repository by the documentation migration.
For use with: docs-driven scaffolding and merge-back.

---

## Batch 1 — Project basics

- **Name:** IQ Option Bot
- **One-line description:** A local tick-capture and trading-bot project for IQ Option, currently composed of a Chrome extension and a Python WebSocket receiver.
- **Problem solved:** Capture live IQ Option tick/price-update data in a local process so it can be recorded, analysed, and eventually used by signal, risk, and execution layers.
- **Brand-new or existing:** Existing proof of concept.

## Batch 2 — Stack and shape

- **Primary language:** Python 3.11.1 (local environment).
- **Frameworks/runtimes:** `websockets` Python package; Chrome Manifest V3 extension; browser WebSocket interception.
- **Datastores:** None yet. The receiver keeps an in-memory buffer of the last 500 raw messages per `active_id`.
- **Runtime target:** Local service plus browser extension on a Windows machine.
- **Project type:** Local data-ingestion service / trading-bot project.

## Batch 3 — Audiences and operations

- **Who runs it:** The project owner, locally, for research and development.
- **Production-critical:** Not yet. The current receiver is a proof of concept. Future live trading would be real-money and production-critical.
- **Hard constraints:** Must run locally; the extension only runs on `*.iqoption.com`; no remote service is currently used; no credentials are stored in the repo yet.
- **Operator role:** The project owner acts as both developer and operator for now. A separate operator runbook becomes important before any live trading.

## Batch 4 — Source material

Authoritative inputs found in the repository:

- `README.md` — setup instructions for the receiver and extension.
- `receiver.py` — the current WebSocket receiver.
- `test_receiver.py` — the current `unittest` suite.
- `chrome-extension/manifest.json` — extension configuration.
- `chrome-extension/inject.js` — WebSocket interception in the page context.
- `chrome-extension/content.js` — local WebSocket forwarding and queueing.
- `asset_names.json` — `active_id` display-name mapping.
- `requirements.txt` — `websockets>=12,<16`.
- Pasted AMT/ML discussion from another AI conversation, preserved in `sources/AMT_ML_DISCUSSION.md`.

## Batch 5 — AI assistants used

- OpenCode reads `AGENTS.md` directly.
- No other assistant pointer files were present before this documentation migration.

---

## Repo layout (factual, before documentation merge)

```text
iqoption-bot/
├── chrome-extension/
│   ├── content.js
│   ├── inject.js
│   └── manifest.json
├── docs-driven/                 # temporary documentation staging area
├── .gitignore
├── asset_names.json
├── README.md
├── receiver.py
├── requirements.txt
└── test_receiver.py
```

## Existing commands

| Task | Command | Source |
|------|---------|--------|
| Create environment | `py -m venv .venv` | `README.md` |
| Activate environment | `.\.venv\Scripts\Activate.ps1` | PowerShell convention |
| Install dependencies | `py -m pip install -r requirements.txt` | `README.md` |
| Run receiver | `py receiver.py` | `README.md` |
| Run tests | `py -m unittest -v test_receiver` | `README.md` |

## Existing documentation found

- `README.md` — explains the receiver, asset-name mapping, extension loading, and test command.
- No project-specific `AGENTS.md`, `RUNBOOK.md`, or `docs/` tree existed before this migration.
- `docs-driven/` contains the universal documentation-driven scaffold, which is being used as the staging area.

## Existing AGENTS.md content (verbatim)

No existing project-specific `AGENTS.md` was found.

## Notable decisions and conventions observed

- The extension runs in two content-script contexts: `inject.js` in the page `MAIN` world to patch `WebSocket`, and `content.js` in the isolated extension world to forward messages.
- `inject.js` filters incoming WebSocket messages by `payload?.name === "candle-generated"` before posting them to `content.js`.
- `content.js` validates `event.source`, `event.origin`, `event.data.source === "IQ_TICK_BRIDGE"`, and that `payload` is a string.
- `content.js` reconnects to the local receiver every 2 seconds and queues up to 500 messages while disconnected, dropping the oldest message when full.
- `receiver.py` validates JSON, requires an outer object with `name == "candle-generated"`, requires a `msg` object and an `active_id`, then stores the full message dictionary.
- The receiver’s `history_by_active_id` is a `defaultdict` of `deque(maxlen=500)`. It stores raw message dictionaries, not generated candles.
- The receiver binds to `localhost:8765`, uses a 1 MiB maximum frame size, and sets ping interval/timeouts to 20 seconds.
- Asset names are display-only. The receiver still processes unmapped `active_id` values and logs them as `unmapped`.

## Open questions for the project owner

- Confirm the exact semantics of the `at` field and whether the intercepted frame is a tick, a partial-candle update, or a completed-candle event.
- Confirm whether 1-minute candles should be clock-aligned to UTC minute boundaries.
- Confirm the first instrument universe and whether asset metadata should include pip size, asset type, payout, and expiry options.
- Confirm the eventual order-execution route: separate IQ Option API session, extension-only injection, or manual execution.
- Confirm whether a live spot FX feed is available for comparison with OTC pricing.

---

*Last updated: 2026-11-18*

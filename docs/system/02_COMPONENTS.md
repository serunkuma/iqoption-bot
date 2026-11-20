# Components

Status: Current

> Six components run today: capture, store, sampler, features and labels, model suite, and router plus paper execution. Each has one responsibility and a plain-data boundary.

---

## Component Map

| Component | Location | Responsibility | Depends on |
|-----------|----------|----------------|------------|
| Page WebSocket intercept | `chrome-extension/inject.js` | Patch `window.WebSocket`, observe messages, filter `candle-generated`, post the raw payload to the isolated world | none |
| Local forwarder | `chrome-extension/content.js` | Validate page messages, connect to `ws://localhost:8765`, reconnect every 2s, queue up to 500 messages | interceptor |
| Tick capture | `components/receiver.py` | Validate the envelope, stamp `received_at`, buffer 500 raw messages per `active_id`, call the tick sink | forwarder |
| Tick sink | `runner.py` (`JsonlTickSink`) | Append accepted ticks to a daily JSONL file | capture |
| Tick store | `engine/store.py` | Enforce the tick contract, order, deduplicate, expose point-in-time price lookups | capture output |
| Snapshot sampler | `engine/sampler.py` | Verify continuity, freeze the causal feature slice, attach delayed entry and horizon exits | store, config |
| Domain primitives | `engine/domain/` | Minute buckets, TPO profile, and labels | config |
| Feature engine | `engine/features.py` | Stateless `core16-v1` vector plus `amt-v3` diagnostics | sampler snapshot, config |
| Dataset builder | `engine/build.py` | Join features to labels, write Parquet artifacts | sampler, features, labels |
| Model suite | `engine/models.py` | Walk-forward training, calibration, held-out evaluation table | dataset |
| Router | `engine/router.py` | EV hurdle, direction and horizon selection, reason codes | probabilities, config |
| Paper broker | `engine/execution.py` | Open, hold, and resolve paper trades under a one-open-trade limit | proposal, snapshot, config |
| Backtest | `engine/backtest.py` | Replay held-out probabilities through router and broker | suite, dataset, config |
| Reports | `engine/reports.py` | Calibration, reliability, importance, JSON/Markdown bundle | suite, trades |
| Entry point | `runner.py` | Lifecycle and wiring for `serve`, `build`, `train`, `backtest`, `diagnose` | all of the above |
| Asset-name map | `asset_names.json` | Map `active_id` to a display name for logs | none |

---

## Data Flow

```text
browser frame
  -> receiver.accept_frame          validate, stamp received_at
  -> JsonlTickSink                  data/raw/ticks-<date>.jsonl
  -> TickStore                      ordered, deduplicated ticks
  -> build_snapshots                gated evaluation points
  -> compute_features               core16-v1 + diagnostics
  -> snapshot_label_rows            long-format labels
  -> dataset.parquet                joined rows
  -> train_suite                    four calibrated models + evaluation table
  -> run_backtest                   router + paper broker
  -> reports                        JSON + Markdown
```

---

## Boundaries

1. **Capture is upstream.** `engine` never imports `components`. The engine consumes files and in-memory objects, not sockets.
2. **One-way data.** Each component returns a value; it does not mutate an upstream component.
3. **Plain objects.** `Tick`, `TickStore`, `Snapshot`, `FeatureVector`, `SignalProposal`, and `Trade` are the interfaces.
4. **No private access.** A component never reads another component's private attributes; the backtest reuses the public broker API.
5. **Configuration is injected.** Only `engine/config.py` parses TOML; every other module receives a validated `Config`.
6. **One entry point.** Only `runner.py` knows the full wiring.

---

## Testing Surface

| Component | Test file |
|-----------|-----------|
| Config | `tests/test_config.py` |
| Store | `tests/test_store.py` |
| Timeframes | `tests/test_timeframes.py` |
| Profile | `tests/test_profile.py` |
| Sampler | `tests/test_sampler.py` |
| Features | `tests/test_features.py` |
| Labels | `tests/test_labels.py` |
| Model suite | `tests/test_models.py` |
| Router | `tests/test_router.py` |
| Execution | `tests/test_execution.py` |
| Backtest | `tests/test_backtest.py` |
| Reports | `tests/test_reports.py` |
| Receiver | `tests/test_receiver.py` |
| Documentation checker | `tests/test_docs.py` |
| Hook installer | `tests/test_hooks.py` |

---

## Development Tooling

Not part of the runtime pipeline; used to keep the repository honest.

| Tool | Location | Responsibility |
|------|----------|----------------|
| Documentation checker | `tools/check_docs.py` | Verify status labels, relative links, and index coverage |
| Hook installer | `tools/install_hooks.py` | Point `core.hooksPath` at the versioned `.githooks/` directory |
| Pre-commit hook | `.githooks/pre-commit` | Run the documentation checker before each commit |

Invoked as `runner.py docs-check`. It reads markdown only and imports nothing from `engine`, so it is safe in a bare environment. The hook calls `tools/check_docs.py` directly for the same reason.

---

## Planned Components

| Component | Responsibility | Blocker |
|-----------|----------------|---------|
| Live feature service | Produce snapshots and vectors from the running stream | Live sampling does not exist |
| Live signal loop | Route live probabilities and log proposals | Needs the live feature service |
| Risk manager | Daily loss limit, consecutive-loss limit, stake sizing, kill switch | Not designed in code |
| Demo/live adapter | Place and reconcile real orders | Requires validation gate and risk manager |
| Session and gap tracker | Record reconnects and missing periods explicitly | Gaps are currently inferred |
| Monitoring | Metrics, alerts, drift detection | Reports are offline only |

These are not implemented and must not be described as working.

---

## Related Documentation

- [Runtime and entry point](11_RUNTIME_AND_ENTRYPOINT.md)
- [Interfaces](04_INTERFACES.md)
- [Data pipeline](07_DATA_PIPELINE.md)
- [ML pipeline](08_ML_PIPELINE.md)

---

*Last updated: 2026-11-20*

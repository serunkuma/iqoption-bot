# RUNBOOK: Operating IQ Option Bot

Status: Current

> **Scope:** This runbook covers streaming capture, offline build/train/backtest, runtime model checks, and replay. `serve` can record runtime paper decisions, but the project has no broker order path.

---

## Core Rules

1. **Documentation is authority.** Read `AGENTS.md` before changing or operating the system.
2. **Do not trade real money.** Runtime is paper-only; there is no broker adapter, complete risk manager, or kill switch.
3. **Check the status label.** Only follow docs marked `Status: Current`.
4. **Use the virtual environment.** Do not run bare `python`.
5. **Import `engine` before `pandas`.** See the LightGBM caveat below.
6. **Keep this runbook current.** Update it when commands or behaviour change.
7. **Treat captured data as sensitive.** Do not publish raw account or session data.

---

## Daily Workflow

### 1. Pre-flight

- [ ] Open PowerShell in the repository root.
- [ ] Confirm the virtual environment exists.
- [ ] Confirm dependencies are installed.
- [ ] Confirm the git hooks are installed.
- [ ] Confirm the extension is loaded in Chrome.

```powershell
Test-Path .\.venv\Scripts\python.exe
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip show websockets lightgbm
.\.venv\Scripts\python.exe tools\install_hooks.py --status
```

### 2. Start streaming capture

```powershell
.\.venv\Scripts\python.exe runner.py serve --capture-only
```

Expected log lines include:

```text
Listening for tick data on ws://localhost:8765
```

`--capture-only` persists accepted events and completed candles under `data\stream\` without loading a model. `--shadow` loads the model and journals decisions but never opens a paper trade. Without either flag, `serve` requires a compatible `.joblib` artifact and records candle-close paper decisions. It never places broker orders.

Optional overrides:

```powershell
.\.venv\Scripts\python.exe runner.py serve --host localhost --port 8766 --stream-dir data\stream-test --capture-only
```

Use `--model <path>` to select a runtime artifact explicitly. `--stream-dir` changes the stream store root.

### 3. Open IQ Option

- Open or reload the IQ Option Traderoom.
- Confirm the extension is enabled.
- Confirm the receiver logs `Extension connected.`

### 4. Verify ticks

Watch for lines containing:

```text
asset=... active_id=... close=... open=... min=... max=... volume=... at=...
```

If prices match the platform, capture is working. Accepted events and finalized candles are persisted in hourly Parquet parts; the forming candle is not force-finalized on shutdown.

### 5. Diagnose the capture

```powershell
.\.venv\Scripts\python.exe runner.py diagnose --input data\ticks.csv
```

Check:

| Output | Suspicious when |
|--------|-----------------|
| `rows` | Very small for the session length |
| `duplicate timestamp/price pairs` | Large relative to rows; duplicates are preserved, not removed |
| `out-of-order rows` | Non-zero and growing |
| `span seconds` | Shorter than the session |
| `minutes with ticks` | Noticeably fewer than the span in minutes |

`diagnose` reads a `.csv`, `.jsonl`, `.parquet`, or a stream events directory. Use `replay` to compare persisted stream events and candles.

### 6. Build the dataset

```powershell
.\.venv\Scripts\python.exe runner.py build --input data\ticks.csv
```

The build summary reports:

| Field | Meaning |
|-------|---------|
| `ticks` | Rows in the tick store |
| `duplicate_rows` | Exact duplicate timestamp/price pairs observed; events are preserved |
| `out_of_order` | Rows that arrived out of order |
| `snapshots` | Snapshots that passed the continuity gate |
| `feature_rows` | One row per snapshot |
| `label_rows` | One row per snapshot per horizon |
| `dataset_rows` | Joined rows |
| `usable_rows` | Rows with a directional label |
| `config_hash` | First 16 hex characters of the config digest |
| `candidate_minutes` | Whole minutes containing at least one tick |
| `skipped_insufficient_history` | Fewer than seven completed bars |
| `skipped_gap` | A minute is missing inside the macro window |
| `skipped_sparse_bar` | A completed bar has too few ticks |
| `skipped_no_entry_tick` | No entry tick inside the delay plus tolerance |
| `snapshots_with_missing_exits` | At least one horizon has no exit tick |

Expected artifacts: `data/ticks.parquet`, `data/features.parquet`, `data/labels.parquet`, `data/dataset.parquet`.

A high `skipped_gap` means the capture has holes. A high `skipped_no_entry_tick` means the feed is sparse or the entry tolerance is too tight.

### 7. Train

```powershell
.\.venv\Scripts\python.exe runner.py train
```

Writes `data/models/suite-<UTC timestamp>.joblib` plus a `.manifest.json` sidecar. It does not automatically promote the artifact to the configured runtime path.

Read the per-horizon line carefully:

```text
horizon   60s  rows=... oos=... eval=... brier=... auc=... cal=...
```

- `eval` is the held-out evaluation slice. If it is very small, the metrics are noise.
- `cal=none` with a note means the Platt fit was rejected as non-increasing and identity calibration shipped. That is an honest failure, not a bug.
- A horizon skipped for insufficient/one-class rows has no model; those candidate probabilities are unavailable.

Validate a candidate artifact before runtime use:

```powershell
.\.venv\Scripts\python.exe runner.py model-check --model data\models\suite-<UTC timestamp>.joblib
```

### 8. Backtest

```powershell
.\.venv\Scripts\python.exe runner.py backtest
```

Writes `reports/backtest.json` and `reports/backtest.md`.

Summary keys:

| Key | Meaning |
|-----|---------|
| `snapshots` | Snapshots routed to a proposal (the result's `routed` counter) |
| `skipped_no_model` | Snapshot not in the held-out evaluation slice, or no model for that horizon |
| `skipped_below_hurdle` | Routed snapshot whose best EV failed the hurdle |
| `skipped_overlap` | Blocked by the one-open-trade limit |
| `trades` | Trades opened by the paper broker |
| `closed` / `open` | Resolved / still open at the end of replay |
| `wins` / `losses` / `voids` | Resolution counts; a tie resolves to void |
| `pnl` | Sum of realised PnL at fixed stake |
| `win_rate` | Wins divided by closed trades |

`skipped_no_model` is normally large. That is correct: only held-out walk-forward evaluation probabilities are replayable.

### 9. Run the tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
```

The suite includes streaming, runtime, and offline tests; use the result printed by the current run rather than relying on a copied count.

### 10. Replay persisted stream data

```powershell
.\.venv\Scripts\python.exe runner.py replay --events data\stream\events --candles data\stream\candles
```

Replay rebuilds candles from stored events and compares them with recorded candles. It can optionally check feature parity with `--dataset`.

### 11. Stop capture

Press `Ctrl+C` in the receiver terminal. Pending data is flushed, state is saved, and the forming candle is not finalized.

---

## Troubleshooting

### Issue: No ticks in the receiver

**Check:**

1. The receiver is running and listening on the configured port.
2. The extension is loaded and enabled.
3. The IQ Option page was reloaded after loading the extension.
4. The page is on `*.iqoption.com`.
5. The browser console shows `[Tick Bridge] Connected to local Python server.`

**If still failing:**

- Reload the extension.
- Reload the IQ Option page.
- Check for a port conflict (below).

---

### Issue: Port 8765 already in use

**Diagnose:**

```powershell
Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue
```

**Fix:**

- Stop the other receiver process, or
- Restart `serve` with `--port 8766`, set `SERVER_URL` to `ws://localhost:8766` in `chrome-extension/content.js`, and reload the extension.

Receiver host and port are still module constants (with CLI overrides); they are not yet in `config/default.toml`.

---

### Issue: Extension keeps disconnecting

**Check:**

- The receiver process is alive.
- No firewall or endpoint protection is blocking localhost WebSockets.
- The browser console shows reconnect attempts every two seconds.

**Note:** While disconnected, the extension queues up to 500 messages and drops the oldest when full. Data loss is possible.

---

### Issue: Frames are ignored

The receiver ignores frames that are:

- Not valid JSON.
- Not a JSON object.
- Missing `name == "candle-generated"`.
- Missing `msg`.
- Missing `msg.active_id`.

Check the receiver console for warnings such as `Ignoring malformed JSON frame.`

A frame can pass the receiver envelope check but fail later store validation: invalid timestamps, non-numeric or non-positive prices, and `active_id` mismatches are rejected by the streaming or batch store.

---

### Issue: `active_id` shows as `unmapped`

Add the mapping to `asset_names.json`:

```json
{
  "42": "EUR/USD"
}
```

Restart the receiver. The mapping only changes the log label.

---

### Issue: Build fails with `TickStoreError`

The message includes the offending line. Common causes:

| Cause | Fix |
|-------|-----|
| Naive timestamp | Capture with `received_at`; never hand-write timestamps without an offset |
| Non-positive price | Inspect the raw payload; the record is bad |
| `active_id` mismatch | Set `instrument.active_id` in the config, or omit it to auto-select |

Never patch a bad row silently. Fix the capture or exclude the file.

---

### Issue: `build` produces very few snapshots

The continuity gate is strict by design. Check `skipped_gap` and `skipped_sparse_bar` first. A capture with holes will not produce snapshots, and the engine will not interpolate.

---

### Issue: `train` skips every horizon

`models.min_train_rows` defaults to 500 usable rows per horizon. A short capture does not clear it. Either capture longer or lower the threshold for a smoke test, and do not interpret the resulting metrics.

---

### Issue: `backtest` reports zero trades

Check, in order:

1. `skipped_no_model` — the suite may have no evaluation rows at all.
2. `cal` — identity calibration plus a wide probability spread can keep EV below the hurdle.
3. `router.min_ev` — `0.03` is deliberately conservative. Do **not** lower it until trades appear.

---

### Issue: LightGBM crashes inside `LGBM_DatasetSetField`

Symptom:

```text
OSError: exception: access violation reading 0x0000000000000000
```

Cause: `pandas` or `pyarrow` was imported before `lightgbm` on Windows.

Fix:

```python
import engine  # imports .models first
import pandas as pd
```

`runner.py` and the test suite already do this. Ad-hoc scripts must follow the same order.

---

### Issue: `docs-check` reports a broken link or orphan doc

**Read the output:** it names the source file and the offending target.

| Message | Fix |
|---------|-----|
| `broken link: <path>` | The target file was renamed, moved, or deleted — update the link, or restore the file |
| `orphan doc: <path>` | Add a link to the doc from `docs/index.md` |
| `missing status: <path>` | Add a `Status: Current`, `Planning`, or `Historical` line near the top |

Run it again until the counts are zero. Exit code `1` is a failure, not a warning.

---

### Issue: The pre-commit hook did not run

**Check:**

```powershell
.\.venv\Scripts\python.exe tools\install_hooks.py --status
```

If it prints `unset`, install it:

```powershell
.\.venv\Scripts\python.exe tools\install_hooks.py
```

Other causes:

| Cause | Fix |
|-------|-----|
| `git commit --no-verify` was used | Expected; the hook is deliberately bypassable |
| Hooks configured elsewhere (`core.hooksPath` in global config) | The installer sets the repository-local value, which takes precedence |
| Git GUI or IDE bypasses hooks | Commit from the terminal once to confirm |

---

### Issue: Tests fail

**Check:**

- The virtual environment is active or you are using its Python directly.
- Dependencies are installed.
- You are in the repository root.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
```

---

## Weekly Tasks

- [ ] Run the full test suite.
- [ ] Run `runner.py docs-check` and confirm exit code 0.
- [ ] Run `diagnose` on the newest capture and look for new duplicates or ordering inversions.
- [ ] Review the limitation backlog in `docs/system/10_LIMITATIONS_AND_BACKLOG.md`.
- [ ] Check for dependency updates.
- [ ] Review captured logs for repeated errors.

### Documentation validation

The checker is part of the repository:

```powershell
.\.venv\Scripts\python.exe runner.py docs-check
```

It verifies three things:

| Check | Fails when |
|-------|------------|
| Status label | A doc under `docs/` has no `Status: Current`, `Planning`, or `Historical` line |
| Link resolution | A relative markdown link points at a file that does not exist |
| Index coverage | A doc under `docs/` is not linked from `docs/index.md` |

Exit code `1` lists every offending file. Run it after moving, adding, or deleting docs. The same check runs automatically before every commit once the hooks are installed:

```powershell
.\.venv\Scripts\python.exe tools\install_hooks.py
.\.venv\Scripts\python.exe tools\install_hooks.py --status
```

The hook calls `tools/check_docs.py` directly, so it needs only the standard library and still works when LightGBM is broken. It is bypassable per commit with `git commit --no-verify`; use that only for an emergency and fix the docs immediately after.

Set `IQBOT_PRECOMMIT_TESTS=1` in the environment to make the hook run the full unit suite as well.

What it cannot check: whether the prose still matches the code, and whether commands in `AGENTS.md`, `README.md`, and this runbook agree. Check those by reading the three files together after a command change.

---

## Trading Operations

Not available.

Before any trading procedure is added:

- The validation gate in `docs/system/09_MODEL_VALIDATION.md` must pass.
- Paper replay must run without errors.
- A risk manager and kill switch must be implemented and tested.
- A demo adapter must be implemented and reconciled.
- Live execution must be explicitly approved.

---

## Quick Reference

| Task | Command |
|------|---------|
| Create environment | `py -m venv .venv` |
| Activate environment | `.\.venv\Scripts\Activate.ps1` |
| Install dependencies | `py -m pip install -r requirements.txt` |
| Capture ticks | `.\.venv\Scripts\python.exe runner.py serve` |
| Capture without model decisions | `.\.venv\Scripts\python.exe runner.py serve --capture-only` |
| Shadow decisions without paper trades | `.\.venv\Scripts\python.exe runner.py serve --shadow` |
| Diagnose a file capture | `.\.venv\Scripts\python.exe runner.py diagnose --input data\ticks.csv` |
| Diagnose a stream capture | `.\.venv\Scripts\python.exe runner.py diagnose --input data\stream\events` |
| Build store and dataset | `.\.venv\Scripts\python.exe runner.py build --input data\ticks.csv` |
| Build from stream events | `.\.venv\Scripts\python.exe runner.py build --input data\stream\events` |
| Train models | `.\.venv\Scripts\python.exe runner.py train` |
| Backtest | `.\.venv\Scripts\python.exe runner.py backtest` |
| Validate model artifact | `.\.venv\Scripts\python.exe runner.py model-check --model data\models\suite-<timestamp>.joblib` |
| Replay stream candles | `.\.venv\Scripts\python.exe runner.py replay --events data\stream\events --candles data\stream\candles` |
| Run tests | `.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v` |
| Check port | `Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue` |
| Check docs | `.\.venv\Scripts\python.exe runner.py docs-check` |
| Install git hooks | `.\.venv\Scripts\python.exe tools\install_hooks.py` |
| Check git hooks | `.\.venv\Scripts\python.exe tools\install_hooks.py --status` |

---

## Related Documentation

- [README](README.md)
- [AGENTS.md](AGENTS.md)
- [Runtime and entry point](docs/system/11_RUNTIME_AND_ENTRYPOINT.md)
- [System overview](docs/system/01_OVERVIEW.md)
- [Model validation](docs/system/09_MODEL_VALIDATION.md)
- [Limitations and backlog](docs/system/10_LIMITATIONS_AND_BACKLOG.md)
- [Tick stream contract](docs/data/01_TICK_STREAM.md)

---

*Last updated: 2026-11-21*

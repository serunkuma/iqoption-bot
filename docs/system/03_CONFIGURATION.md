# Configuration

Status: Current

> One TOML file configures the whole engine. Every section is validated at startup; an unknown key or an impossible combination fails loudly with exit code 2.

---

## Loading

| Source | Default |
|--------|---------|
| Config file | `config/default.toml` |
| Override | `runner.py --config <path>` |

`load_config` reads the file with `tomllib`, builds typed dataclasses, and validates them. `ConfigError` is raised for a missing file, an unknown key, a wrong type, an out-of-range value, or an inconsistent pair such as a payout for a horizon without labels. Snapshot timing has one candle-close cadence; there is no offset list.

There are no environment-variable overrides yet. CLI flags override only per-command arguments such as `--input`, `--dataset`, `--model`, `--host`, `--port`, `--stream-dir`, and `--capture-only`.

`config_hash(config)` serialises every field, sorts keys, and returns the first 16 hex characters of a SHA-256 digest. It is recorded in the build summary and on the model suite.

---

## `[instrument]`

| Key | Default | Validation |
|-----|---------|------------|
| `symbol` | `"EURUSD"` | Display only |
| `active_id` | `0` | Non-negative, or omitted/null to auto-select the first id present |
| `pip_size` | `0.0001` | Positive |
| `bin_size` | `0.00005` | Positive; TPO bin width in price units |

`active_id` is how single-instrument operation is enforced. The sampler filters the store to this id before building anything. `null` means "use whichever id appears first", which is convenient for a test capture but ambiguous in production.

`bin_size` should be small enough that a typical minute spans several bins and large enough that bins are not mostly single prints. For EURUSD, `0.00005` is five sub-pips.

---

## `[candles]`

| Key | Default | Validation |
|-----|---------|------------|
| `interval_seconds` | `60` | At least 1 |

Changing the interval changes the meaning of `macro_candles`, `fast_candles`, and `min_ticks_per_bar`. It also invalidates `CANDLE_VERSION`.

---

## `[context]`

| Key | Default | Validation |
|-----|---------|------------|
| `macro_candles` | `7` | At least 1 |
| `fast_candles` | `3` | At least 1, not greater than `macro_candles` |
| `profile_min_ticks` | `30` | At least 1 |
| `value_area_target` | `0.70` | In `(0, 1]` |
| `tail_bins` | `3` | At least 1 |
| `single_print_max_ticks` | `1` | Non-negative |
| `volatility_min_changes` | `10` | At least 1 |
| `epsilon` | `1e-9` | Positive; reserved for numerical guards |

The macro window supplies the profile and `sigma_7`; the fast window supplies recent activity; the last completed candle supplies the most recent activity values. The forming candle is excluded from the feature vector. See [TPO and Value Area](../data/04_TPO_VALUE_AREA.md) and [Model inputs](../data/09_MODEL_INPUTS.md).

---

## `[snapshot]`

| Key | Default | Validation |
|-----|---------|------------|
| `entry_delay_ms` | `250` | Non-negative |
| `entry_tolerance_seconds` | `1.0` | Non-negative |
| `exit_tolerance_seconds` | `5.0` | Non-negative |
| `min_ticks_per_bar` | `1` | At least 1 |

Offline sampling produces at most one snapshot per eligible minute at candle close. The runtime decision is triggered when the first event in a later minute closes the preceding candle. `entry_delay_ms`, entry tolerance, and exit tolerance apply after that close.

Raising `min_ticks_per_bar` trades data volume for density confidence. The default accepts any non-empty completed bar; a real capture should probably use a higher value once tick cadence is known.

---

## `[labels]`

| Key | Default | Validation |
|-----|---------|------------|
| `horizons_seconds` | `[60, 90, 120, 180]` | Non-empty, positive, unique, ascending |
| `tie_policy` | `"exclude"` | `exclude` or `keep` |

`tie_policy = "keep"` retains tie rows in the dataset but they still carry `label = "tie"`, so they remain non-directional. The model trains on `label == "call"`; ties are never a direction.

Every horizon must have a payout in `[router.payouts]`, and every payout must map to a configured horizon.

---

## `[router]`

| Key | Default | Validation |
|-----|---------|------------|
| `min_ev` | `0.03` | In `[-1, 1)` |
| `tie_break` | `"earliest_horizon"` | `earliest_horizon` or `highest_ev` |
| `payouts` | see below | Table of `horizon = payout`; payout positive |

```toml
[router.payouts]
60 = 0.80
90 = 0.82
120 = 0.84
180 = 0.86
```

Payouts are configured, not scraped. They must be updated when the platform changes its rates, because EV and the win threshold depend on them directly. A stale payout silently changes every decision.

`min_ev = 0.03` requires a 3% expected return per unit stake. See [Signal router](13_SIGNAL_ROUTER.md).

---

## `[models]`

| Key | Default | Validation |
|-----|---------|------------|
| `engine` | `"lightgbm"` | `lightgbm` or `sklearn` |
| `calibration` | `"auto"` | `auto`, `isotonic`, `platt`, or `none` |
| `purge_seconds` | `180` | Non-negative |
| `embargo_seconds` | `0` | Non-negative |
| `n_splits` | `5` | At least 2 |
| `min_train_rows` | `500` | At least 1 |
| `random_seed` | `7` | Any integer |
| `n_estimators` | `300` | Any positive integer |
| `learning_rate` | `0.03` | Any positive float |
| `num_leaves` | `15` | Any positive integer |
| `min_child_samples` | `50` | Any positive integer |
| `runtime_path` | `"data/models/suite.joblib"` | Required configured runtime artifact path |

`calibration = "auto"` selects isotonic when the calibration slice has at least 500 rows and Platt otherwise. A non-increasing Platt fit is rejected regardless of this setting.

`purge_seconds = 180` matches the longest horizon: a training row whose label window overlaps the first test row is excluded. See [Model suite](12_MODEL_SUITE.md).

---

## `[execution]`

| Key | Default | Validation |
|-----|---------|------------|
| `mode` | `"paper"` | `paper`, `demo`, or `live` |
| `stake` | `1.0` | Positive |
| `max_open_trades` | `1` | At least 1 |
| `cooldown_seconds` | `0` | Non-negative pause after a paper trade resolves |
| `daily_loss_limit` | `5.0` | Positive realized-loss limit, or `null` to disable |

The runtime paper engine applies the one-open-trade, cooldown, and daily realized-loss gates. `demo` and `live` validate but raise `ExecutionError` when the broker is constructed; no order adapter ships.

---

## `[stream]`

| Key | Default | Validation / behavior |
|-----|---------|-----------------------|
| `root` | `"data/stream"` | Required non-empty store root |
| `rotation_seconds` | `3600` | Positive multiple of `candles.interval_seconds`; hourly paths are currently fixed |
| `flush_events` | `500` | At least 1 event before a count-based flush |
| `compression` | `"zstd"` | `zstd`, `snappy`, `gzip`, or `none` |
| `max_buffer_events` | `50000` | At least `flush_events`; exceeding the limit fails ingestion |

`decisions_dir` and `state_file` are derived from `root`; they are not TOML keys.

---

## `[store]`

| Key | Default | Meaning |
|-----|---------|---------|
| `root` | `"data"` | Build output directory |
| `ticks_path` | `"data/ticks.parquet"` | Canonical tick store |
| `snapshots_path` | `"data/snapshots.parquet"` | Reserved; snapshots are not written separately yet |
| `models_path` | `"data/models"` | Model suite directory |
| `reports_path` | `"reports"` | Backtest report directory |

`build` writes `features.parquet`, `labels.parquet`, and `dataset.parquet` under `root` in addition to `ticks_path`.

---

## `[data]`

| Key | Default | Meaning |
|-----|---------|---------|
| `input_path` | `"data/ticks.csv"` | Default input for `build` and `diagnose` |

---

## Receiver Constants

The capture component still uses module constants rather than the TOML file:

| Constant | Default | Meaning |
|----------|---------|---------|
| `HOST` | `"localhost"` | Bind address |
| `PORT` | `8765` | WebSocket port |
| `HISTORY_LIMIT` | `500` | Raw messages retained per `active_id` |
| `ASSET_NAMES_PATH` | `asset_names.json` at the repo root | Display-name map |

`runner.py serve` can override host and port. Moving these into the TOML file is backlog, not done.

---

## Version Constants

| Constant | Value | Scope |
|----------|-------|-------|
| `FEATURE_VERSION` | `amt-v4` | Full diagnostic table |
| `CORE_FEATURE_VERSION` | `core16-v2` | Model inputs |
| `LABEL_VERSION` | `snapshot-horizon-v1` | Labels |
| `CANDLE_VERSION` | `1m-clock-v1` | Minute bucketing |
| `DECISION_VERSION` | `candle-close-v1` | Decision cadence |
| `MODEL_FORMAT_VERSION` | `joblib-v1` | Runtime model serialization |

These are not configurable. Changing a definition requires a code change and a version bump, so an artefact can always be traced to the code that produced it.

---

## Secrets

- `.env`, credentials, and account data stay local and gitignored.
- No SSID, token, or account identifier belongs in `config/`, `asset_names.json`, docs, or logs.
- Future execution credentials must come from environment variables or an OS secret store, never from the TOML file.

---

## Related Documentation

- [Runtime and entry point](11_RUNTIME_AND_ENTRYPOINT.md)
- [Model suite](12_MODEL_SUITE.md)
- [Signal router](13_SIGNAL_ROUTER.md)
- [Security](06_SECURITY.md)

---

*Last updated: 2026-11-21*

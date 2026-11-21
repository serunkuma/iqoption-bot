# Orientation

Status: Current

> Start here. This document explains the live stream path, the offline research path, and why the feature table has more columns than the model has inputs. It is the map; the specifications are the territory.

---

## 1. What This Is

A local streaming and offline research system. The live path makes candle-close paper decisions; it does not place broker orders.

```text
stream capture -> hourly event/candle store -> candle-close runtime -> paper decisions
offline files  -> TickStore -> snapshots + labels -> features -> models -> backtest
```

Each arrow is a module with a documented contract and its own tests. `runner.py` is the only thing that wires them together.

**What it is not:** an order-executing trading bot. It has a runtime feature/inference loop and paper broker, but no demo/live order placement, complete risk manager, kill switch, or multi-instrument support. No result so far is distinguishable from noise.

### Intended direction (not implemented)

The runtime currently loads validated `.joblib` suites and computes predictions at candle close, while offline training and backtesting remain available. Four calibrated classifiers estimate per-horizon outcomes; the final EV router is deterministic. A learned selector, demo/live execution, and an evidence-backed edge remain future work.

Features are market-description inputs to models, not trade signals by themselves. A future learned selector may choose direction, horizon, or abstention, while deterministic payout, risk, and execution gates remain hard constraints. See [ML Runtime and Signal Selection](planning/ml-runtime-and-signal-selection.md) for the target design and unresolved implementation choices. Pocket Auto v3 is a reference for selected architecture patterns, not the implementation target.

---

## 2. The Two Data Paths

The live store and offline dataset are distinct paths. `serve` stores events and closed candles; `build` consumes a file input and creates snapshots, features, labels, and a dataset.

```text
Live stream:
IQ Option page -> extension -> receiver -> StreamStore
    -> sequence-preserving event parts + closed-candle parts
    -> candle-close RuntimeEngine -> .joblib inference
    -> deterministic EV router -> paper broker -> JSONL journals

Offline research:
CSV / JSONL / Parquet -> TickStore -> candle-close snapshots and labels
    -> core16-v2 / amt-v4 dataset -> calibrated model suite
    -> held-out backtest -> reports/backtest.{json,md}
```

Older synthetic-run metrics in checked-in reports and previous docs describe the former intra-minute snapshot contract. They are historical, not evidence for the current candle-close contract. Do not quote them as current results without rebuilding, retraining, and regenerating the backtest.

Where each stage lives:

| Stage | Code | Specification |
|-------|------|---------------|
| Capture | `chrome-extension/`, `components/receiver.py` | [Tick stream](data/01_TICK_STREAM.md) |
| Tick table | `engine/store.py` | [Tick store](data/07_TICK_STORE.md) |
| Streaming store and runtime | `engine/stream/`, `engine/runtime.py` | [Streaming runtime and store](system/16_STREAMING_RUNTIME_AND_STORE.md) |
| Decision points | `engine/sampler.py` | [Snapshots and continuity](data/08_SNAPSHOTS_AND_CONTINUITY.md) |
| Market description | `engine/features.py` | [Model inputs](data/09_MODEL_INPUTS.md) |
| Outcomes | `engine/domain/labels.py` | [Labels, payouts, and EV](data/06_LABELS_PAYOUTS_AND_EV.md) |
| Models | `engine/models.py` | [Model suite](system/12_MODEL_SUITE.md) |
| Trade decision | `engine/router.py` | [Signal router](system/13_SIGNAL_ROUTER.md) |
| Paper fills | `engine/execution.py` | [Execution and resolution](system/14_EXECUTION_AND_RESOLUTION.md) |
| Honest replay | `engine/backtest.py` | [Model validation](system/09_MODEL_VALIDATION.md) |

Full command reference: [Runtime and entry point](system/11_RUNTIME_AND_ENTRYPOINT.md).

---

## 3. The Feature Layers

The model consumes exactly **16** ordered values. Feature and dataset tables also carry identity, version, diagnostic, and label columns; only the 16 core values enter the classifiers.

```text
identity / version metadata
snapshot_id, timestamp, active_id, price, feature_version,
core_feature_version, decision_version
+-- 16 CORE: the only columns any model sees -------------------+
| z_poc  z_vah  z_val  inside_va  va_width_norm                 |
| poc_position  edge_proximity                                  |
| excess_high  excess_low  excess_asymmetry                     |
| tick_rate_3_7  tick_rate_last_3                               |
| price_speed_3_7  price_speed_last_3                           |
| range_last_3  price_change_last                               |
+-- diagnostics: stored, never trained on ----------------------+
| poc  vah  val  sigma_7  profile_ticks  window_bars            |
| tail_length_high  tail_length_low                             |
| tick_rate_7  tick_rate_3  tick_rate_last                      |
| price_change_7  price_change_3  price_change_last              |
| price_speed_7  price_speed_3  price_speed_last                 |
| range_7  range_3  range_last                                  |
| range_speed_7  range_speed_3  range_speed_last  range_3_7      |
| time_sin  time_cos  day_of_week  is_weekend                   |
| profile_missing  volatility_missing  insufficient_ticks       |
| gap_in_window                                                 |
+---------------------------------------------------------------+
```

Diagnostics are the ingredients; the 16 core features are recipes built from them:

| Core feature | Built from | Form |
|---|---|---|
| `z_poc` | `poc`, `sigma_7`, price | `(price - poc) / sigma_7` |
| `z_vah`, `z_val` | `vah`, `val`, `sigma_7` | distance in volatility units |
| `inside_va` | `vah`, `val`, price | `1` inside the value area, else `0` |
| `va_width_norm` | `vah`, `val`, `sigma_7` | width in volatility units |
| `poc_position` | `poc`, `val`, `vah` | `(poc - val) / (vah - val)` |
| `edge_proximity` | price, `val`, `vah`, `sigma_7` | nearest edge in volatility units |
| `excess_high`, `excess_low` | tail bins, single-print count | share of each tail that is single print |
| `excess_asymmetry` | the two above | `excess_high - excess_low` |
| `tick_rate_3_7` | `tick_rate_3`, `tick_rate_7` | ratio |
| `tick_rate_last_3` | last completed candle vs fast tick rate | ratio |
| `price_speed_3_7` | `price_speed_3`, `price_speed_7` | ratio |
| `price_speed_last_3` | last completed candle vs fast speed | ratio |
| `range_last_3` | last candle range vs fast range | ratio |
| `price_change_last` | last completed candle first/last price | signed difference |

Every core input is dimensionless: a z-score, a ratio, a 0/1 flag, or a signed within-bar change. None is an absolute price, an absolute tick rate, or a clock time.

### Why the split

| Reason | Consequence |
|--------|-------------|
| Ratio features transfer across instruments and sessions | EURUSD at 1.08 and BTC at 64,000 produce comparable vectors |
| Absolute levels do not transfer | A tree split on `poc = 1.0843` never recurs and cannot generalise |
| The available sample is limited | Keep diagnostics out of the model input contract |
| Diagnostics are needed to audit a feature | When `z_poc` looks wrong you need the raw `poc` and `sigma_7` |
| Quality flags gate a build | `gap_in_window` must be `0` for any snapshot that passed the continuity gate |
| Regime research needs the raw ingredients | A future balance/imbalance gate uses `inside_va`, `edge_proximity`, `excess_*`, and the activity ratios |

The enforcement is a frozen tuple, not a convention:

```python
X = subset.loc[:, list(CORE_FEATURES)].to_numpy(dtype=float)
```

Adding a diagnostic cannot silently change the model. Adding a model input requires editing `CORE_FEATURES` and bumping `CORE_FEATURE_VERSION`.

Dataset outcome fields must never enter the feature matrix; the model uses only the fixed `CORE_FEATURES` order.

---

## 4. How Much Data Actually Reaches the Model

Model and backtest counts depend on the input capture and the current candle-close contract. Older synthetic counts in the checked-in reports describe the former intra-minute dataset and are historical only. Do not present them as current results without rebuilding, retraining, and regenerating the backtest.

---

## 5. What Is Proven vs Assumed

| Proven | Assumed or open |
|--------|-----------------|
| Frames arrive and are forwarded | What a frame is: tick, partial candle, or completed candle |
| `received_at` is stamped and persisted | That `msg.at` carries no usable information (stored, never used) |
| Batch and streaming ingestion preserve accepted repeated events | That tick density is a valid TPO proxy on OTC pricing |
| Candle-close snapshots use contiguous completed candles | That a 250 ms entry delay is realistic |
| The 16 features are computed without lookahead | That AMT structure predicts anything on real pricing |
| Models train, calibrate, or refuse to calibrate | That the configured payouts match the platform |
| The backtest cannot reach in-sample data | That 79 evaluation rows could detect an edge (they cannot) |
| Unit tests cover stream, runtime, replay, and offline behavior | That test coverage establishes operational readiness |

See [Model validation](system/09_MODEL_VALIDATION.md) for the go/no-go gate and [Limitations and backlog](system/10_LIMITATIONS_AND_BACKLOG.md) for the full list.

---

## 6. Reading Order

1. [System overview](system/01_OVERVIEW.md) — what exists, what does not
2. [Tick stream](data/01_TICK_STREAM.md) -> [Tick store](data/07_TICK_STORE.md) -> [Snapshots and continuity](data/08_SNAPSHOTS_AND_CONTINUITY.md)
3. [Model inputs](data/09_MODEL_INPUTS.md) — the 16/31 split in full detail
4. [Labels, payouts, and EV](data/06_LABELS_PAYOUTS_AND_EV.md) — why accuracy is the wrong target
5. [Model suite](system/12_MODEL_SUITE.md) -> [Signal router](system/13_SIGNAL_ROUTER.md) -> [Execution and resolution](system/14_EXECUTION_AND_RESOLUTION.md)
6. [Model validation](system/09_MODEL_VALIDATION.md) -> [Limitations and backlog](system/10_LIMITATIONS_AND_BACKLOG.md)
7. [Roadmap](planning.md) — what comes next
8. [ML Runtime and Signal Selection](planning/ml-runtime-and-signal-selection.md) — current/target boundary, runtime artifact plan, and learned selector decisions

---

## 7. How the Documentation Stays Honest

The repository is documentation-driven in a specific, mechanical sense:

```text
decision -> AGENTS.md decision-log row
         -> docs/ specification (Current / Planning / Historical)
         -> code + version string
         -> tests
         -> artefact carries the version and the config hash
```

Rules that are enforced rather than suggested:

| Rule | Enforced by |
|------|-------------|
| Every doc under `docs/` has a status label | `tools/check_docs.py` |
| Every relative link resolves | `tools/check_docs.py` |
| Every doc is reachable from the index | `tools/check_docs.py` |
| Every artefact records its versions | Feature rows, dataset, model suite |
| No in-sample replay | `ModelSuite.evaluate_snapshot` is the only backtest entry point |
| No live execution | `ExecutionError` on `demo` and `live` |

Run the checker with:

```powershell
.\.venv\Scripts\python.exe runner.py docs-check
```

What it cannot check: whether the prose still matches the code. That remains a human responsibility, and it is listed as a limitation.

---

## Related Documentation

- [Documentation index](index.md)
- [System overview](system/01_OVERVIEW.md)
- [Components](system/02_COMPONENTS.md)
- [Configuration](system/03_CONFIGURATION.md)
- [Model inputs](data/09_MODEL_INPUTS.md)
- [Testing strategy](system/05_TESTING.md)
- [AGENTS.md](../AGENTS.md)

---

*Last updated: 2026-11-20*

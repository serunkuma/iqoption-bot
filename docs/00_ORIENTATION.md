# Orientation

Status: Current

> Start here. This document explains what the system is, how one piece of data becomes a trade decision, and why the feature table has more columns than the model has inputs. It is the map; the specifications are the territory.

---

## 1. What This Is

A local, batch-oriented prediction engine fed by a live tick capture.

```text
capture  ->  store  ->  snapshots  ->  features + labels  ->  models  ->  router  ->  paper trades
```

Each arrow is a module with a documented contract and its own tests. `runner.py` is the only thing that wires them together.

**What it is not:** a trading bot. There is no live feature computation, no live signal loop, no order placement, no risk manager, and no multi-instrument support. Execution is a paper broker inside the backtest. No result so far is distinguishable from noise.

---

## 2. The Pipeline, With One Real Run

The numbers below came from the synthetic capture used as the repository smoke test (48,000 ticks over 800 minutes, one instrument). They are useful because they show the shape of every artefact.

```text
IQ Option page
    | WebSocket frames
    v
chrome-extension/  ->  components/receiver.py
    | validate, stamp received_at
    v
data/raw/ticks-YYYY-MM-DD.jsonl               append-only capture
    | runner.py build
    v
TickStore                48,000 ticks, 0 duplicates, 0 out of order
    | 800 whole minutes
    v
Sampler                  793 snapshots (7 skipped: not enough history)
    | continuity gate, 250 ms delayed entry, four horizon exits
    v
Features + labels        793 rows x 53 columns, 3,172 label rows
    | join on snapshot_id
    v
dataset.parquet          3,172 rows x 62 columns, 3,102 usable
    | runner.py train
    v
Model suite              4 models (60/90/120/180 s), ~775 rows each,
                         258 out-of-sample, 77-79 held out
    | runner.py backtest
    v
Router + paper broker    81 snapshots routed, 3 below the EV hurdle,
                         23 blocked by the one-open-trade limit,
                         55 trades, 25 wins / 30 losses, PnL -9.8
    |
    v
reports/backtest.{json,md}
```

Where each stage lives:

| Stage | Code | Specification |
|-------|------|---------------|
| Capture | `chrome-extension/`, `components/receiver.py` | [Tick stream](data/01_TICK_STREAM.md) |
| Tick table | `engine/store.py` | [Tick store](data/07_TICK_STORE.md) |
| Decision points | `engine/sampler.py` | [Snapshots and continuity](data/08_SNAPSHOTS_AND_CONTINUITY.md) |
| Market description | `engine/features.py` | [Model inputs](data/09_MODEL_INPUTS.md) |
| Outcomes | `engine/domain/labels.py` | [Labels, payouts, and EV](data/06_LABELS_PAYOUTS_AND_EV.md) |
| Models | `engine/models.py` | [Model suite](system/12_MODEL_SUITE.md) |
| Trade decision | `engine/router.py` | [Signal router](system/13_SIGNAL_ROUTER.md) |
| Paper fills | `engine/execution.py` | [Execution and resolution](system/14_EXECUTION_AND_RESOLUTION.md) |
| Honest replay | `engine/backtest.py` | [Model validation](system/09_MODEL_VALIDATION.md) |

Full command reference: [Runtime and entry point](system/11_RUNTIME_AND_ENTRYPOINT.md).

---

## 3. The Three Feature Layers

This is the part that surprises most readers: the model consumes **16** numbers, but the feature table stores **53** columns and the dataset stores **62**.

| Table | Columns | Composition |
|-------|---------|-------------|
| `data/features.parquet` | 53 | 6 identity + 16 model inputs + 31 diagnostics |
| `data/dataset.parquet` | 62 | the 53 above + 9 label columns |

```text
+-- 6 identity / meta ------------------------------------------+
| snapshot_id, timestamp, active_id, price,                     |
| feature_version, core_feature_version                         |
+-- 16 CORE: the only columns any model sees -------------------+
| z_poc  z_vah  z_val  inside_va  va_width_norm                 |
| poc_position  edge_proximity                                  |
| excess_high  excess_low  excess_asymmetry                     |
| tick_rate_3_7  tick_rate_forming_3                            |
| price_speed_3_7  price_speed_forming_3                        |
| range_forming_3  price_change_forming                         |
+-- 31 DIAGNOSTIC: stored, never trained on --------------------+
| poc  vah  val  sigma_7  profile_ticks  window_bars            |
| tail_length_high  tail_length_low                             |
| tick_rate_7  tick_rate_3  tick_rate_forming                   |
| price_change_7  price_change_3                                |
| price_speed_7  price_speed_3  price_speed_forming             |
| range_7  range_3  range_forming                               |
| range_speed_7  range_speed_3  range_speed_forming  range_3_7  |
| time_sin  time_cos  day_of_week  is_weekend                   |
| profile_missing  volatility_missing  insufficient_ticks       |
| gap_in_window                                                 |
+---------------------------------------------------------------+
```

The 31 diagnostics are the ingredients; the 16 core features are recipes built from them:

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
| `tick_rate_forming_3` | forming vs fast tick rate | ratio |
| `price_speed_3_7` | `price_speed_3`, `price_speed_7` | ratio |
| `price_speed_forming_3` | forming vs fast speed | ratio |
| `range_forming_3` | `range_forming`, `range_3` | ratio |
| `price_change_forming` | forming bar first/last price | signed difference |

Every core input is dimensionless: a z-score, a ratio, a 0/1 flag, or a signed within-bar change. None is an absolute price, an absolute tick rate, or a clock time.

### Why the split

| Reason | Consequence |
|--------|-------------|
| Ratio features transfer across instruments and sessions | EURUSD at 1.08 and BTC at 64,000 produce comparable vectors |
| Absolute levels do not transfer | A tree split on `poc = 1.0843` never recurs and cannot generalise |
| ~3,100 usable rows cannot support 53 inputs | 16 inputs is already generous; 53 would fit noise |
| Diagnostics are needed to audit a feature | When `z_poc` looks wrong you need the raw `poc` and `sigma_7` |
| Quality flags gate a build | `gap_in_window` must be `0` for any snapshot that passed the continuity gate |
| Regime research needs the raw ingredients | A future balance/imbalance gate uses `inside_va`, `edge_proximity`, `excess_*`, and the activity ratios |

The enforcement is a frozen tuple, not a convention:

```python
X = subset.loc[:, list(CORE_FEATURES)].to_numpy(dtype=float)
```

Adding a diagnostic cannot silently change the model. Adding a model input requires editing `CORE_FEATURES` and bumping `CORE_FEATURE_VERSION`.

### The 9 label columns

`dataset.parquet` adds outcome columns that must never enter the feature matrix: `entry_timestamp`, `entry_price`, `horizon_seconds`, `exit_timestamp`, `exit_price`, `exit_delay_seconds`, `label`, `usable`, `label_version`.

---

## 4. How Much Data Actually Reaches the Model

```text
3,172 dataset rows        (793 snapshots x 4 horizons)
  -70 unusable            (ties or missing exits)
= 3,102 usable
  / 4 horizons  ~  775 rows per horizon
    walk-forward OOS  ~  258 per horizon
      x 30% held out  ~  77-79 evaluation rows
```

Seventy-nine evaluation rows is why every AUC between 0.50 and 0.60 and every Brier near 0.25 must be read as *indistinguishable from noise*. The backtest arithmetic is consistent, which is a sign the plumbing is honest:

```text
81 routed - 3 below the EV hurdle - 23 blocked by the one-open-trade limit = 55 trades
```

Fifty-five trades at a 0.455 win rate against a 0.556 breakeven is a loss. On synthetic ticks that is the correct outcome; a profit here would indicate a bug.

---

## 5. What Is Proven vs Assumed

| Proven | Assumed or open |
|--------|-----------------|
| Frames arrive and are forwarded | What a frame is: tick, partial candle, or completed candle |
| `received_at` is stamped and persisted | That `msg.at` carries no usable information (stored, never used) |
| CSV, JSONL, and Parquet ingestion enforce one contract | That tick density is a valid TPO proxy on OTC pricing |
| Snapshots are gap-free and causal | That a 250 ms entry delay is realistic |
| The 16 features are computed without lookahead | That AMT structure predicts anything on synthetic pricing |
| Models train, calibrate, or refuse to calibrate | That the configured payouts match the platform |
| The backtest cannot reach in-sample data | That 79 evaluation rows could detect an edge (they cannot) |
| 117 unit tests pass | — |

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

*Last updated: 2026-11-19*

# Asset Identities and Metadata

Status: Current

> This document defines how instruments are identified today, what metadata is missing, and what the project needs before tick bins, payouts, and execution can be specified.

---

## Current Identity Model

The primary instrument key is `active_id`, supplied in every accepted tick payload.

`active_id` is stable enough for buffering and logging, but it is not human-readable. The project uses `asset_names.json` as a local display-name map:

```json
{
  "42": "EUR/USD",
  "77": "GBP/USD"
}
```

### Rules

- Keys must be strings.
- Values must be non-empty strings.
- The file must contain a JSON object.
- The mapping only changes log labels. It does not filter, rename, or modify ticks.
- An unmapped `active_id` is still processed and logged as `unmapped`.

`components/receiver.py` loads the map at startup and validates it with `load_asset_names`.

---

## Identity Fields in the Payload

The receiver recognises these payload fields when formatting logs:

| Field | Purpose |
|-------|---------|
| `symbol` | Broker symbol, if present |
| `ticker` | Alternative symbol field |
| `asset` | Asset identifier |
| `asset_name` | Human-readable asset name |
| `active_name` | Alternative active name |
| `instrument` | Instrument identifier |
| `instrument_name` | Human-readable instrument name |
| `underlying` | Underlying asset |
| `name` | Generic name field |

These fields are optional and inconsistent. They are not a substitute for a canonical metadata table.

---

## Metadata That Is Configured, Not Discovered

The engine does not read instrument metadata from the feed. Three values are configured in `config/default.toml` for the single active instrument:

| Value | Config key | Used by |
|-------|------------|---------|
| Active instrument | `instrument.active_id` | Sampler filter |
| Price bin width | `instrument.bin_size` | TPO profile |
| Pip size | `instrument.pip_size` | Reserved; not yet consumed |
| Payout per horizon | `router.payouts` | EV and the trade hurdle |

These are operator-supplied assumptions. They must be checked manually and updated when the platform changes them.

---

## Missing Metadata

The current project does not know, per `active_id`:

- Instrument type (forex, crypto, stock, index, commodity, OTC).
- Available expiry durations as offered by the platform.
- Trading session and weekend/OTC status.
- Minimum and maximum stake.
- Currency.

This metadata is required for:

| Use case | Required metadata |
|----------|-------------------|
| Price bins for TPO | Pip/tick size |
| Expected value | Payout rate |
| Label horizon | Expiry duration |
| Weekend/synthetic filter | Session and asset type |
| Risk and stake sizing | Min/max stake, currency |
| Execution | Instrument identifiers accepted by the platform |

---

## Planned Asset Metadata

The project should replace the display-only map with a metadata file, for example `assets.json`:

```json
{
  "42": {
    "symbol": "EURUSD",
    "display_name": "EUR/USD",
    "asset_type": "forex_otc",
    "pip_size": 0.0001,
    "tick_size": 0.00001,
    "payout": 0.82,
    "expiries_seconds": [60],
    "session": "24x5",
    "min_stake": 1.0,
    "max_stake": 1000.0,
    "currency": "USD"
  }
}
```

### Validation Rules

- `symbol` must be a non-empty string.
- `asset_type` must be from a fixed enum.
- `pip_size` and `tick_size` must be positive numbers.
- `payout` must be in `(0, 1)` when present.
- `expiries_seconds` must contain positive integers.
- `min_stake` must be greater than zero and less than or equal to `max_stake`.
- Unknown fields must be preserved rather than silently dropped.

Payout and expiry values may change over time. If the platform exposes them dynamically, the metadata file should store defaults and the runtime should record the observed values with timestamps.

---

## Open Questions

- Does the feed expose payout and expiry options, or must they be configured manually?
- Are `active_id` values stable across sessions and accounts?
- Should metadata be keyed by `active_id`, symbol, or both?
- What is the first instrument universe?
- How should weekend OTC instruments be flagged?

---

## Related Documentation

- [Tick stream contract](01_TICK_STREAM.md)
- [TPO and Value Area](04_TPO_VALUE_AREA.md)
- [Labels, payouts, and expected value](06_LABELS_PAYOUTS_AND_EV.md)
- [Configuration](../system/03_CONFIGURATION.md)

---

*Last updated: 2026-11-19*

# TPO and Value Area Specification

Status: Planning

> This document specifies how tick density becomes a rolling Time-Price Opportunity (TPO) profile and how the Point of Control (POC), Value Area High (VAH), and Value Area Low (VAL) are computed. It is not implemented yet.

---

## Purpose

The project has no trusted traded volume or Level 2 depth. Tick density is the volume proxy.

A TPO profile answers:

- Which prices did the market spend the most time at?
- What range contains most recent activity?
- Where is the current price relative to that range?

---

## Definitions

| Term | Definition |
|------|------------|
| Tick event | One accepted price update from the receiver |
| Tick price | The `close` value of the tick event |
| Price bin | A fixed-width price interval |
| Bin index | `floor(price / bin_size)` |
| TPO count | Number of tick events assigned to a bin |
| Window | Rolling time interval used to build the profile |
| POC | Bin with the highest TPO count |
| Value Area | Smallest contiguous set of bins around POC containing at least the target share of ticks |
| VAH | Upper edge of the highest included bin |
| VAL | Lower edge of the lowest included bin |

---

## Parameters

| Parameter | Default | Notes |
|-----------|---------|-------|
| Window length | 15 minutes | 30-minute preset also supported |
| Bin size | 0.5 pip | Instrument-specific; ATR-scaled alternative |
| Value Area target | 70% | Classic Market Profile convention |
| Minimum ticks | 30 | Below this, features are null |
| Update cadence | Every tick or every 5 seconds | Must be documented per implementation |

### Bin Size

For forex pairs:

```text
bin_size = 0.5 * pip_size
```

Examples:

| Instrument | Pip size | 0.5-pip bin size |
|------------|----------|------------------|
| EUR/USD | 0.0001 | 0.00005 |
| USD/JPY | 0.01 | 0.005 |

For non-forex instruments, or when volatility is very different, the bin size may be scaled by ATR:

```text
bin_size = max(tick_size, atr_multiplier * ATR(window))
```

The same bin size must be used for a given feature snapshot. Changing bin size is a feature-version change.

---

## Algorithm

### 1. Select ticks

Select accepted ticks for the instrument with `received_at` in `[t - window, t]`.

Exclude ticks flagged as duplicates or out of order.

### 2. Bin ticks

```text
for each tick in window:
    bin_index = floor(tick.price / bin_size)
    counts[bin_index] += 1
```

### 3. Find POC

```text
poc_bin = argmax(counts)
```

Tie-break rules, in order:

1. Highest count.
2. Bin closest to the current price.
3. Lower bin index.

The tie-break must be deterministic and documented in code.

### 4. Expand the Value Area

Classic Market Profile expands from POC in pairs until the target share is reached.

```text
included = {poc_bin}
included_count = counts[poc_bin]
target = 0.70 * total_ticks

while included_count < target:
    above = next two unincluded bins above the current included range
    below = next two unincluded bins below the current included range

    above_count = sum(counts[b] for b in above)
    below_count = sum(counts[b] for b in below)

    if above_count == 0 and below_count == 0:
        break

    if above_count >= below_count:
        include above bins
        included_count += above_count
    else:
        include below bins
        included_count += below_count
```

Notes:

- The pair expansion may overshoot the 70% target. That is expected and allowed.
- If fewer than two bins remain on one side, use the available bins.
- An alternative one-bin-at-a-time expansion may be documented as a variant, but the pair method is the default.

### 5. Compute edges

```text
VAL = lower edge of the lowest included bin
VAH = upper edge of the highest included bin
```

```text
bin_lower(i) = i * bin_size
bin_upper(i) = (i + 1) * bin_size
```

### 6. Emit profile

```json
{
  "active_id": 42,
  "window_seconds": 900,
  "bin_size": 0.00005,
  "total_ticks": 81,
  "poc": 1.25075,
  "poc_bin": 25015,
  "vah": 1.252,
  "val": 1.2495,
  "value_area_ticks": 70,
  "value_area_share": 0.8642,
  "computed_at": "2026-11-18T12:15:00Z"
}
```

`poc` is the midpoint of the POC bin unless the implementation documents otherwise.

---

## Worked Example

Window: 15 minutes. Bin size: 0.0005 for readability.

| Bin | Range | Tick count |
|-----|-------|------------|
| 0 | 1.2490–1.2495 | 2 |
| 1 | 1.2495–1.2500 | 5 |
| 2 | 1.2500–1.2505 | 12 |
| 3 | 1.2505–1.2510 | 25 |
| 4 | 1.2510–1.2515 | 18 |
| 5 | 1.2515–1.2520 | 10 |
| 6 | 1.2520–1.2525 | 6 |
| 7 | 1.2525–1.2530 | 3 |

Total ticks: 81. Target: `0.70 * 81 = 56.7`.

1. POC = bin 3 (25 ticks).
2. Two above: bins 4 + 5 = 28. Two below: bins 2 + 1 = 17. Include above. Included = 53.
3. Still below 56.7. Two above: bins 6 + 7 = 9. Two below: bins 2 + 1 = 17. Include below. Included = 70.
4. Included bins: 1, 2, 3, 4, 5.
5. `VAL = 1.2495`, `VAH = 1.2520`.

The value area contains 70 of 81 ticks, or 86.4%, because the pair expansion overshot.

---

## Edge Cases

| Case | Policy |
|------|--------|
| Fewer than minimum ticks | Emit `null` profile and mark `insufficient_data` |
| All ticks in one bin | POC = that bin; VAH/VAL = bin edges |
| Multiple POC ties | Use the documented tie-break |
| Price far outside VA | Still compute; distance features capture the extension |
| Large gaps in ticks | Compute on available ticks; flag `gap_in_window` |
| Window spans a session break | Document whether to reset; default is no reset unless configured |
| New instrument | No profile until minimum ticks are available |

---

## Validation Rules

- `VAL <= POC <= VAH`
- `VAH > VAL`
- `value_area_ticks >= 0.70 * total_ticks` unless the expansion exhausted all bins
- `total_ticks >= minimum_ticks` for a non-null profile
- `bin_size > 0`
- `window_seconds > 0`
- Profile computation uses only ticks with `received_at <= computed_at`

---

## Related Documentation

- [Tick stream contract](../data/01_TICK_STREAM.md)
- [AMT Feature Specification](../data/05_AMT_FEATURE_SPEC.md)
- [Auction Market Theory](../concepts/05_AUCTION_MARKET_THEORY.md)
- [Data Pipeline](../system/07_DATA_PIPELINE.md)

---

*Last updated: 2026-11-18*

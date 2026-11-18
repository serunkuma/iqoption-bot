# Configuration

Status: Current

> This document records the configuration that exists today and the configuration the target system will need. Secrets are never committed.

---

## Current Configuration

There is no configuration file yet. The PoC uses constants in code.

### `receiver.py`

| Constant | Default | Meaning |
|----------|---------|---------|
| `HOST` | `localhost` | Bind address |
| `PORT` | `8765` | WebSocket port |
| `HISTORY_LIMIT` | `500` | Raw messages retained per `active_id` |
| `ASSET_NAMES_PATH` | `asset_names.json` beside `receiver.py` | Display-name map |
| `IDENTITY_FIELDS` | Tuple of field names | Payload fields included in log identity |

Runtime limits:

| Setting | Value |
|---------|-------|
| `ping_interval` | 20 seconds |
| `ping_timeout` | 20 seconds |
| `max_size` | 1,048,576 bytes |

### `chrome-extension/content.js`

| Constant | Default | Meaning |
|----------|---------|---------|
| `SERVER_URL` | `ws://localhost:8765` | Local receiver address |
| `RECONNECT_DELAY_MS` | `2000` | Reconnect delay |
| `MAX_QUEUED_MESSAGES` | `500` | Queue while disconnected; oldest dropped when full |

### `chrome-extension/manifest.json`

| Setting | Value |
|---------|-------|
| `manifest_version` | 3 |
| Host permission | `http://localhost/*` |
| Matches | `*://*.iqoption.com/*` |
| Content scripts | `inject.js` in `MAIN` world, `content.js` in isolated world |

### `asset_names.json`

A JSON object mapping string `active_id` keys to non-empty display names.

---

## Planned Configuration

The planned configuration file is `config/default.toml`, overridable by environment variables.

```toml
[server]
host = "localhost"
port = 8765
log_level = "INFO"

[receiver]
history_limit = 500
asset_names_path = "asset_names.json"
capture_raw = true
data_dir = "data"

[time]
session_timezone = "UTC"

[profile]
window_seconds = 900
bin_size_mode = "pip"          # "pip" or "atr"
bin_size_pips = 0.5
min_ticks = 30

[features]
sigma_window_candles = 15
min_sigma_candles = 10
short_velocity_seconds = 30
long_velocity_seconds = 300

[labels]
expiry_seconds = 60
tie_policy = "exclude"          # "exclude", "refund", or "loss"

[model]
path = "models/current"
feature_version = "amt-v1"
label_version = "next-close-v1"

[risk]
max_stake = 1.0
daily_loss_limit = 20.0
max_consecutive_losses = 3
kill_switch = true

[execution]
mode = "paper"                  # "paper", "demo", "live"
```

### Environment Overrides

Planned precedence:

```text
CLI flag > environment variable > config file > default
```

Planned environment variables:

| Variable | Purpose |
|----------|---------|
| `IQBOT_CONFIG` | Config file path |
| `IQBOT_LOG_LEVEL` | Override log level |
| `IQBOT_EXECUTION_MODE` | `paper`, `demo`, or `live` |
| `IQBOT_DATA_DIR` | Data directory |
| `IQBOT_MODEL_PATH` | Model directory |
| `IQBOT_API_SSID` | Execution session identifier, if used |
| `IQBOT_API_TOKEN` | Execution token, if used |

---

## Secrets

- `.env` and local credential files must be gitignored.
- No credentials, SSID, session tokens, or account identifiers belong in `asset_names.json`, docs, or source.
- Future execution credentials should be loaded from environment variables or an OS secret store.
- Logs must never print secrets.

---

## Validation

Configuration validation must fail fast with a clear message when:

- A required value is missing.
- A numeric value is out of range.
- A mode is unknown.
- A path does not exist when required.
- A feature or label version is unsupported.

Invalid configuration must prevent the service from starting, not degrade silently.

---

## Related Documentation

- [System overview](01_OVERVIEW.md)
- [Interfaces](04_INTERFACES.md)
- [Security](06_SECURITY.md)
- [Tick stream contract](../data/01_TICK_STREAM.md)

---

*Last updated: 2026-11-18*

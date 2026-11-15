# IQ Option local tick bridge

This project forwards `candle-generated` WebSocket messages observed on
`*.iqoption.com` to a local Python WebSocket receiver. It does not place trades
or send data to a remote service.

## Run the receiver

From the project directory, create and activate a virtual environment, then
install the dependency and start the server:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py receiver.py
```

The receiver listens on `ws://localhost:8765`. Keep it running while using the
extension. Candle history is kept in memory per `active_id`, with the most
recent 500 candles retained. Every received candle is processed and logged
with its `active_id`, OHLCV values, and timestamp. Any identity fields present
in the candle payload (such as `symbol` or `ticker`) are included in the log.

## Identify active IDs

The candle payload always provides `active_id`, but it may not include a
human-readable asset name. Add names you know to `asset_names.json`, using the
ID shown by the receiver as a string key:

```json
{
  "42": "EUR/USD",
  "77": "GBP/USD"
}
```

The mapping changes log labels only; it does not filter or modify incoming
candles. If an ID is not mapped and the payload has no symbol/name field, the
receiver reports it as `unmapped` while still showing the numeric `active_id`.

Run the receiver tests with:

```powershell
py -m unittest -v test_receiver
```

## Load the Chrome extension

1. Open `chrome://extensions` and enable **Developer mode**.
2. Select **Load unpacked** and choose this project's `chrome-extension` folder.
3. Open or reload an IQ Option page on `iqoption.com`. The extension reconnects
   to the local receiver every two seconds after a disconnect.

The extension only runs on `*.iqoption.com`. If your Traderoom uses a different
official IQ Option hostname, update both `matches` entries in
`chrome-extension/manifest.json` to that specific host before loading the
extension.

Edit `process_tick` in `receiver.py` to add indicators or custom calculations.

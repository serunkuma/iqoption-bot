# RUNBOOK: Operating IQ Option Bot

Status: Current

> **Scope:** This runbook covers the current tick-capture proof of concept. There is no trading procedure yet because the project cannot place trades.

---

## Core Rules

1. **Documentation is authority.** Read `AGENTS.md` before changing or operating the system.
2. **Do not trade real money.** The current code has no execution, risk, or kill switch.
3. **Check the status label.** Only follow docs marked `Status: Current`.
4. **Use the virtual environment.** Do not run bare `python`.
5. **Keep this runbook current.** Update it when commands or behaviour change.
6. **Treat captured data as sensitive.** Do not publish raw account or session data.

---

## Daily Workflow

### 1. Pre-flight

- [ ] Open PowerShell in the repository root.
- [ ] Confirm the virtual environment exists.
- [ ] Confirm dependencies are installed.
- [ ] Confirm the extension is loaded in Chrome.

```powershell
Test-Path .\.venv\Scripts\python.exe
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip show websockets
```

### 2. Start the receiver

```powershell
.\.venv\Scripts\python.exe receiver.py
```

Expected output:

```text
Listening for tick data on ws://localhost:8765
```

### 3. Open IQ Option

- Open or reload the IQ Option Traderoom.
- Confirm the extension is enabled.
- Confirm the receiver logs `Extension connected.`

### 4. Verify ticks

Watch for lines containing:

```text
asset=... active_id=... close=... open=... min=... max=... volume=... at=...
```

If prices match the platform, capture is working.

### 5. Run tests

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_receiver
```

### 6. Stop

Press `Ctrl+C` in the receiver terminal. Confirm `Receiver stopped.`

---

## Troubleshooting

### Issue: No ticks in the receiver

**Check:**

1. The receiver is running and listening on port 8765.
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
- Change `PORT` in `receiver.py` and `SERVER_URL` in `chrome-extension/content.js`, then reload the extension.

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

### Issue: Tests fail

**Check:**

- The virtual environment is active or you are using its Python directly.
- Dependencies are installed.
- You are in the repository root.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest -v test_receiver
```

---

## Weekly Tasks

- [ ] Run the receiver tests.
- [ ] Review the limitation backlog in `docs/system/10_LIMITATIONS_AND_BACKLOG.md`.
- [ ] Confirm documentation status labels are current.
- [ ] Check for dependency updates.
- [ ] Review any captured logs for repeated errors.

### Documentation validation

```powershell
powershell -ExecutionPolicy Bypass -File scripts\validate_scaffold.ps1
```

---

## Trading Operations

Not available.

Before any trading procedure is added:

- The validation gate in `docs/system/09_MODEL_VALIDATION.md` must pass.
- Paper mode must run successfully.
- Demo mode must be tested.
- Risk limits and a kill switch must be implemented and tested.
- Live execution must be explicitly approved.

---

## Quick Reference

| Task | Command |
|------|---------|
| Create environment | `py -m venv .venv` |
| Activate environment | `.\.venv\Scripts\Activate.ps1` |
| Install dependencies | `py -m pip install -r requirements.txt` |
| Run receiver | `.\.venv\Scripts\python.exe receiver.py` |
| Run tests | `.\.venv\Scripts\python.exe -m unittest -v test_receiver` |
| Check port | `Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue` |
| Validate docs | `powershell -ExecutionPolicy Bypass -File scripts\validate_scaffold.ps1` |

---

## Related Documentation

- [README](README.md)
- [AGENTS.md](AGENTS.md)
- [System overview](docs/system/01_OVERVIEW.md)
- [Limitations and backlog](docs/system/10_LIMITATIONS_AND_BACKLOG.md)
- [Tick stream contract](docs/data/01_TICK_STREAM.md)

---

*Last updated: 2026-11-18*

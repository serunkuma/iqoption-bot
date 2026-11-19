# Security and Safety

Status: Current

> This document covers the current security posture, secret handling, live-trading safety, and platform/legal considerations. It is not legal advice.

---

## Current Security Posture

| Area | Current state |
|------|---------------|
| Receiver binding | `localhost` only |
| Authentication | None |
| Transport | Plain WebSocket on localhost |
| Remote access | None |
| Extension permissions | `http://localhost/*`; content scripts on `*://*.iqoption.com/*` |
| Secrets in repo | None detected |
| Logging | Plain text; no credentials logged today |

The capture layer is designed for a single local machine. It is not safe to expose the receiver to a network or the internet as-is. The analysis engine and the paper broker run locally in-process and touch no network resources.

---

## Threat Model

| Threat | Impact | Mitigation |
|--------|--------|------------|
| Malicious local process connects to the receiver | Can inject fake ticks | Bind to localhost; add an optional shared token before remote use |
| Malicious page posts forged `window` messages | Can inject fake ticks | `content.js` validates `event.source`, `event.origin`, and `source` marker |
| Extension compromised or updated unexpectedly | Can exfiltrate or alter data | Keep the extension local; review changes; minimal permissions |
| Dependency supply-chain attack | Code execution or data theft | Pin versions; review dependency updates; run in a virtual environment |
| Credentials leaked in logs or git | Account compromise | Never log secrets; use `.env`; gitignore local secrets |
| Over-permissive trading mode | Real-money loss | Demo/paper default; explicit live flag; kill switch |
| Broker or platform policy violation | Account restriction | Review platform terms and jurisdiction before live trading |

---

## Secrets

Planned secret sources:

- Environment variables.
- OS keychain or a local secret manager.
- A gitignored `.env` file for local development only.

Rules:

1. Never commit credentials, SSIDs, session tokens, or account identifiers.
2. Never print secrets in logs, errors, or screenshots.
3. Rotate any credential that appears in a log.
4. Do not store secrets in `asset_names.json`, docs, or source code.
5. Add `.env` and local secret files to `.gitignore` before execution work begins.

---

## Live-Trading Safety

The current project cannot place trades. `engine/execution.py` simulates paper trades only; `demo` and `live` are accepted by the config validator and then rejected with `ExecutionError`. Before any execution component is enabled:

- Paper mode must be the default.
- Demo mode must be tested before live mode.
- Live mode must require an explicit configuration flag and a confirmation step.
- A kill switch must block new orders immediately.
- Risk limits must include maximum stake, daily loss limit, and maximum consecutive losses.
- Every order must have an idempotency key and an audit record.
- The system must fail closed: if data quality or model state is uncertain, do not trade.
- No martingale or loss-doubling strategy without explicit, documented risk limits.
- A human must be able to stop the bot without editing code.

---

## Platform and Legal Considerations

- Automated trading may violate IQ Option's terms of service or local regulations.
- OTC binary options are restricted or prohibited in some jurisdictions.
- The project owner is responsible for confirming eligibility, tax obligations, and platform rules.
- This documentation is not financial, legal, or tax advice.
- Do not use real money until the validation gate in [Model Validation](09_MODEL_VALIDATION.md) is satisfied and the risk controls are tested.

---

## Data Handling

- Tick and trade data may reveal account behaviour. Treat local data as sensitive.
- Do not publish raw account data or credentials in issues, logs, or screenshots.
- Anonymise fixtures used in tests.
- Define a retention policy before capturing long histories.

---

## Related Documentation

- [Configuration](03_CONFIGURATION.md)
- [Execution and resolution](14_EXECUTION_AND_RESOLUTION.md)
- [Model Validation](09_MODEL_VALIDATION.md)
- [Limitations and backlog](10_LIMITATIONS_AND_BACKLOG.md)
- [RUNBOOK](../../RUNBOOK.md)

---

*Last updated: 2026-11-19*

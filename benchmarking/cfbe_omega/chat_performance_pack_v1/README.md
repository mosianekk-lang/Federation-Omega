# CFBE Chat Performance Pack v1.0.0

A standard-library Python package that turns the highest-value findings from the 2026-09-04 CFBE audit into executable, fail-closed controls. It is a locally tested production foundation, not a live ChatGPT or Federation deployment.

## Capabilities

- Producer-signed Recovery Snapshot: canonical HMAC-SHA256 envelope, source epochs, coverage bitmap, generation fence and expiry.
- Fenced O(1) Ledger Head: SQLite WAL transactions, compare-and-swap head, hash chain, idempotent identical retries and divergent-duplicate rejection.
- Task-bounded Context Capsule: deterministic hot context, omission manifest, stable digest and strict byte budget.
- Independent Canary Controller: fixed `B1,C1,B2,C2,C3_STABILITY` lifecycle, direct-measurement checks, proof/invariant/harm gates and terminal de-instrumentation.
- Evidence-aware Benchmark: separates verified score from design/readiness score.
- Stream Guard: payload, retry, concurrency, timebox, secret, raw-payload and unchanged-route controls.

## Quick start

```bash
python -m unittest discover -s tests -v
PYTHONPATH=src python -m cfbe_chatperf.cli stream examples/stream_input.json
PYTHONPATH=src python -m cfbe_chatperf.cli benchmark examples/benchmark_input.json
```

Snapshot signing requires `CFBE_SNAPSHOT_KEY`; the key is read from the process environment and is never written by the package.

## Proof boundary

`DESIGNED`, `IMPLEMENTED`, `TESTED`, `STORED`, `DEPLOYED`, `RUNNING`, `READ_BACK` and `OWNER_VALUE_PROVEN` are distinct. This package proves deterministic local behavior only. Provider-native latency, cache effectiveness, call-count reduction and production recovery require matched canaries after separately authorized integration.

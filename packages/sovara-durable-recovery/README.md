# SOVARA durable recovery soak v41

This controller extends—not replaces—the proven v40 recovery canary. Each
invocation validates the complete JSONL hash chain, suppresses duplicate cycle
IDs, runs at most one due canary, then atomically advances JSON state and emits
a sanitized receipt.

The immutable schedule is 24 hours: one initial observation plus 24 hourly
observations (minimum 25). Status stays `RUNNING` before the end boundary,
becomes `FAIL` on any corrupt record or failed canary, and becomes `PASS` only
at or after the end boundary when every required cycle passed.

Run the first tick and reuse the same three paths for every hourly invocation:

```bash
python3 run_durable_recovery_soak_v41.py \
  --state DURABLE_SOAK_STATE_V41.json \
  --ledger DURABLE_SOAK_LEDGER_V41.jsonl \
  --receipt DURABLE_SOAK_RECEIPT_V41.json
```

Schedulers may pass a stable `--cycle-id`; retrying it is a no-op after full
chain validation. `--at` and `--start-at` accept timezone-aware timestamps and
exist for deterministic replay. All persisted timestamps are normalized to
UTC `Z` form.

Verify locally:

```bash
python3 -m unittest -v test_durable_recovery_soak_v41.py
python3 validate_build_contract.py BUILD_CONTRACT_V41.json --require-proof
```

Rollback is non-destructive: stop scheduler invocation and preserve the state,
ledger and receipt for audit. The v40 runtime and canary remain unchanged.

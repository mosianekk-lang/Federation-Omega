# EvidenceOps RESOLVE

EvidenceOps RESOLVE is an independent, provider-agnostic evidence continuity and execution system. It operationalises the RESOLVE Method: resilient routing, segmented transport, adaptive failure recovery, append-only receipts, and independent verification.

## What it does

- models immutable evidence jobs and completion contracts;
- ranks multiple execution lanes and changes route after classified failures;
- prevents repeated use of a known-broken lane through circuit breakers;
- creates deterministic idempotency keys and resumable checkpoints;
- splits oversized files into hash-locked transport parts;
- reconstructs objects byte-for-byte and validates SHA-256;
- runs ZIP CRC and SQLite integrity checks;
- requires independent readback before verified completion;
- writes machine-readable receipts and a discrepancy log;
- learns reusable failure-to-recovery rules.

## Quick start

```bash
cd evidenceops/resolve
python -m unittest discover -s tests -v
python -m resolve.cli init ./workspace
python -m resolve.cli segment ./large_file.pst ./workspace/parts --part-size-mib 90
python -m resolve.cli verify ./large_file.pst --sha256 EXPECTED_HASH
python -m resolve.cli audit ./workspace
```

## Architecture

- `resolve/models.py` — jobs, lanes, constraints, attempts, receipts and policy.
- `resolve/engine.py` — adaptive execution, circuit breaking, resumability and closure.
- `resolve/transport.py` — segmentation, reconstruction and transport manifests.
- `resolve/verification.py` — independent hash, ZIP and SQLite checks.
- `resolve/ledger.py` — append-only JSONL ledger and discrepancy register.
- `resolve/cli.py` — standalone command line interface.

RESOLVE does not grant cloud authority by itself. External actions remain limited to the credentials and adapters supplied at runtime. It records that boundary rather than pretending it has been crossed.

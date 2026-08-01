# EvidenceOps Connector Foundry

This package supplies the first dependency-free reference connector for
`LANE-CONNECTOR-FOUNDRY`.

## Verified scope

- local JSON `put`, `get` and recursive `list`;
- connector-root path confinement;
- stable operation IDs;
- replay-safe execution;
- conflict rejection when an operation ID is reused with different input;
- SHA-256 content integrity checks;
- append-only hash-chained receipts;
- deterministic EvidenceOps Connector Test Standard (`ECTS-1.0`) execution.

It is a local-runtime reference implementation. It does not prove Google Drive,
Google Cloud, Secret Manager, Gmail or any other provider runtime integration.

## Run

```bash
python -m evidenceops.connector_foundry.conformance
python -m unittest tests.test_connector_foundry -v
```

A passing ECTS report proves the local reference connector only. Provider
adapters require their own authorised execution and readback receipts.

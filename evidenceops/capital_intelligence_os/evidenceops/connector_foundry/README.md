# EvidenceOps Connector Foundry

This package supplies the dependency-free reference connector and the first
provider-specific adapter contract for `LANE-CONNECTOR-FOUNDRY`.

## Verified local reference scope

- local JSON `put`, `get` and recursive `list`;
- connector-root path confinement;
- stable operation IDs;
- replay-safe execution;
- conflict rejection when an operation ID is reused with different input;
- SHA-256 content integrity checks;
- append-only hash-chained receipts;
- deterministic EvidenceOps Connector Test Standard (`ECTS-1.0`) execution.

## Google Drive provider adapter

`google_drive_adapter.py` defines the minimum provider contract for a reversible
native-document canary:

1. create a Google Doc;
2. write canonical JSON;
3. move the file into the authorised control folder;
4. read the text and parent metadata back independently;
5. reject content or parent-location mismatch;
6. issue a deterministic `ECTS-GDRIVE-1.0` receipt.

The first authorised provider canary is preserved in
`google-drive-canary-receipt-20260801-001.json`. It verifies one scoped Google
Drive create/write/move/readback cycle. It does not prove Google Cloud, Secret
Manager, Gmail, transcription, unrestricted Drive authority, or persistent
provider monitoring.

## Run

```bash
python -m evidenceops.connector_foundry.conformance
python -m unittest tests.test_connector_foundry -v
python -m unittest tests.test_connector_foundry_google_drive -v
```

A passing ECTS report proves the local reference connector. Provider adapters
require their own authorised execution and independent readback receipts.

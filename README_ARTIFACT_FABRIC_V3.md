# Federation Artifact Fabric v3 source candidate

This tranche adds a provider-neutral transactional artifact gateway, SQLite event ledger, fail-closed scanner, content-addressed idempotency, crash-safe resume, dead-letter handling, detached receipt-signing contract, Merkle roots, v2 migration and independent drift reconciliation.

Run:

```bash
python -m unittest discover -s tests -p 'test_phoenix_provider_cutover_v3*.py' -v
```

Current state: `SOURCE_IMPLEMENTED / DETERMINISTIC_TESTED / PROVIDER_DISABLED`.

No private Drive IDs, credentials, provider authority, workflow, cloud deployment, email send or production claim is included.

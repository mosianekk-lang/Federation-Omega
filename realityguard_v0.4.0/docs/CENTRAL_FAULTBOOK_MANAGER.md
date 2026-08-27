# RealityGuard central fault-book manager

RealityGuard 0.4.1 is the canonical manager contract for Federation and ChatGPT fault books. It verifies each JSONL event against the preceding hash, rejects duplicate event identifiers, preserves changed imports as revisions, deduplicates exact re-imports, stores full event content only in the private registry, and emits a redacted public manifest.

The manager separates three different claims:

- `VERIFIED_SOURCE`: reviewed source exists at a provider-read commit.
- `VERIFIED_INVOCATION`: one named invocation executed the manager and produced semantic readback.
- `VERIFIED_HOST_BOUND`: a current host invocation and semantic readback prove the host-level hook.

Unreachable, historical or unintegrated consumers must remain `ADAPTER_REQUIRED`, `BLOCKED` or `UNKNOWN`. Source presence, a registry pointer, a local test or another consumer's success cannot promote them. `universal_sync_claim_allowed` is true only when every registered consumer is `VERIFIED_HOST_BOUND`.

## Commands

```bash
PYTHONPATH=src python -m realityguard.cli faultbook-import --ledger FAULTS.jsonl --metadata IMPORT.json --registry PRIVATE_REGISTRY.json
PYTHONPATH=src python -m realityguard.cli faultbook-verify --registry PRIVATE_REGISTRY.json
PYTHONPATH=src python -m realityguard.cli faultbook-manifest --registry PRIVATE_REGISTRY.json
```

The import metadata may verify local artifact digests and retain private storage references. The public manifest excludes raw event content, artifact paths and storage references. A fault book cannot be marked `CLOSED` while regression tests remain open, and the central system remains `SYSTEMIC_OPEN` while any managed fault book is open.

The manager is invocation-driven, not a background daemon. Federation and ChatGPT surfaces still require their own authenticated adapter and provider-native readback before host binding can be claimed.

# EvidenceOps Secure Capability Box

Version 0.4 reconstructs the missing Secure Capability Box as a public-safe production foundation. It does not contain credentials and does not grant broad access. It provides the control path through which an approved workload may receive a short-lived, exact-purpose capability and use one credential without receiving or persisting the credential itself.

## Security contract

```text
verified workload identity
→ deny-by-default policy
→ short-lived signed handle
→ atomic one-time reservation
→ exact secret version resolution
→ one connector execution
→ redacted receipt + tamper-evident audit
```

- Handles are bound to mission version, operation, workload subject, audience, authority class, exact provider resource, connector and action.
- Lifetimes are capped at 15 minutes; exact secret versions are mandatory.
- Revocation, expiry, one-time consumption, concurrent replay and idempotency conflicts fail closed.
- Only `SecureCapabilityBroker.execute()` crosses the effectful boundary.
- Secret values are not stored in SQLite, audit events, receipts, logs, snapshots or source.
- Consequential `WRITE`, `DEPLOY` and `ADMIN` actions require a separate Formation effectful permit and are rejected by this foundation policy.
- The in-memory provider is test-only. Production readiness requires managed provider and connector bindings.

Python cannot guarantee erasure of every transient copy created by an interpreter or third-party HTTP library. The broker minimizes lifetime and overwrites its mutable buffer; process isolation, managed identity, memory controls and short-lived worker instances remain part of the production boundary.

## Production binding

Use `GoogleSecretManagerProvider` with Application Default Credentials from a dedicated workload identity. Grant only `secretmanager.versions.access` on the exact secrets required by the broker service. Configure `FederationOmegaConnector` with an HTTPS operator endpoint. Do not place secret values, service-account keys or private resource identifiers in this repository.

The Google adapter:

- accepts `projects/PROJECT/secrets/SECRET` plus an exact numeric version;
- uses the official Secret Manager client and ADC;
- verifies CRC32C when the service returns a checksum;
- returns a mutable byte buffer only to the broker;
- replaces provider failures with a safe error class.

## Local verification

From this directory:

```bash
python -m unittest discover -s tests -v
python -m compileall -q secure_capability_box
python ../security/public_repository_leak_guard.py
```

No network service is started and no cloud resource is changed by those commands.

## Recovery

`SecureBoxStore.snapshot()` exports grants, operation receipts and the audit chain only. `SecureBoxStore.restore()` accepts a verified snapshot into an empty database and rejects a broken hash chain. Provider payloads and the token signing key are intentionally excluded; production recovery must restore those independently from the managed secret/KMS control plane.

`SecureBoxStore.incomplete_operations()` identifies a consumed handle with no final receipt after a connector or persistence failure. Reconciliation must use the connector's semantic readback before a new handle is issued; it must never blindly repeat a possibly completed external effect.

## Current maturity

The package is implemented and locally tested as a `PROD_FOUNDATION`. It is not deployed, not connected to live credentials and not production-proven. Promotion requires private runtime configuration, workload identity, least-privilege IAM, live health/readback, rotation/revocation drills, deployment rollback proof and an external security review.

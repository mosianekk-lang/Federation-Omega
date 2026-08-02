# EvidenceOps Secure Capability Box

Version 1.0 adds the private service and deployment path to the public-safe Secure Capability Box foundation. It does not contain credentials. It provides the control path through which an approved workload may receive a short-lived, exact-purpose capability and use one credential without receiving or persisting the credential itself.

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

## Private service and deployment

`secure_capability_box.service` exposes health, authenticated readiness, issue, execute, revoke, audit and reconciliation endpoints. Runtime identity, provider resource and action allowlist come only from deployment configuration; callers cannot select a different credential, subject, audience or connector. `SCB_SECRET_VERSION` must be numeric and exact.

The Cloud control bootstrap creates a dedicated service identity and managed API/signing secrets, grants exact Secret Manager access, deploys the container privately with one instance/concurrent request, and performs an issue-to-Federation-Omega execution canary. Credential material is fetched at runtime and is not written into the proof artifacts.

The repository-native objective-completion guard evaluates every operational layer and terminal fruit. A source build, passing tests, a report, or expiry of a 24-hour cycle cannot close this mission.

## Recovery

`SecureBoxStore.snapshot()` exports grants, operation receipts and the audit chain only. `SecureBoxStore.restore()` accepts a verified snapshot into an empty database and rejects a broken hash chain. Provider payloads and the token signing key are intentionally excluded; production recovery must restore those independently from the managed secret/KMS control plane.

`SecureBoxStore.incomplete_operations()` identifies a consumed handle with no final receipt after a connector or persistence failure. Reconciliation must use the connector's semantic readback before a new handle is issued; it must never blindly repeat a possibly completed external effect.

## Current maturity

The package and automated private activation path are implemented and locally tested. The checked-in mission state remains open until the deployment workflow records private runtime configuration, workload identity, live health/readback, recovery proof and monitoring. Source or CI success alone is never promoted to operational completion.

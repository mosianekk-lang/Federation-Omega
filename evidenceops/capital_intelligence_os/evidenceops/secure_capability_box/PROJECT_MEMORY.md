# Project Memory

## Reconstructed baseline

The earlier v0.2/v0.3 package artifacts were not available in the connected workspace, Drive corpus or public repository. The surviving specification described encrypted references, policy, audit, grants and a read-only Drive adapter. Version 0.4 therefore reconstructs behavior from the surviving contract without claiming byte-for-byte recovery.

## Durable decisions

1. Managed secret storage is the production system of record; no home-grown encryption store is introduced.
2. A capability is a short-lived signed reference, never a returned credential.
3. Exact versions are required; `latest` is rejected to preserve reproducibility.
4. The broker persists metadata and digests only.
5. Token consumption is atomic and one-time; idempotent replay requires a newly issued handle with the same operation fingerprint.
6. Consequential actions are separated from this read/verify foundation.
7. In-memory credentials are permitted only in tests and make readiness report `NOT_PRODUCTION_READY`.
8. Source reconstruction does not equal live integration or estate-wide access.

## Open production obligations

- Bind the signing primitive to a managed KMS/HSM or a securely injected runtime key with rotation.
- Establish workload identity and least-privilege IAM for the broker service.
- Bind private policy rules without committing private identifiers.
- Exercise live Secret Manager checksum, Federation Omega health/action discovery and semantic readback.
- Add a production database/HA strategy if multiple broker replicas are required; SQLite is the local control proof.
- Complete threat modelling, penetration testing, rotation, revocation, backup/restore and rollback drills.

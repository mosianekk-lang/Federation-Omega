# Artifact Fabric v3 deployment plan

## Phase 0 — preserve v2

Keep the current private Drive repository, existing files, stable contract identity and owner-facing registry unchanged as the rollback floor. No migration may delete, move or overwrite the canonical v2 artifacts.

## Phase 1 — source and local proof

- Admit the provider-neutral gateway, ledger, scanner, migration and reconciliation modules.
- Run all standard-library adversarial tests through the existing Airlock provider-cutover-v3 suite.
- Keep provider effects disabled.

## Phase 2 — control-plane genesis

- Create the v3 transaction/event ledger projection in the private owner Drive.
- Import only v2 artifacts with verified private readback.
- Generate a genesis event-chain head and delivered-artifact Merkle root.
- Label the root `CONTROL_PLANE_ANCHOR_ONLY` until an independent immutable anchor exists.

## Phase 3 — bounded Drive canary

- Submit one harmless canary through the same required lifecycle.
- Upload once, read back exact name/parent/MIME/size/private state and register it.
- Replay the same idempotency key and prove no second provider object is created.
- Record a signed control receipt and manifest.

## Phase 4 — private runtime

- Deploy the gateway only in an authenticated private execution plane.
- Resolve exact provider IDs and signer keys inside that plane.
- Use short-lived identity and no public write endpoint.
- Persist runtime evidence outside the public source repository.

## Phase 5 — event-driven resilience

- Add Drive change notifications or a bounded change-log poller.
- Add dead-letter and replay transport.
- Exercise provider outage, projection outage, crash at every transition and missed-run recovery.
- Verify exact-byte restoration and rollback.

## Phase 6 — immutable evidence anchor

- Anchor only receipt/event-chain hashes or approved redacted evidence.
- Apply retention controls after a reversible canary and owner-governed policy review.
- Do not duplicate the private user-facing repository.

## Phase 7 — soak and promotion

- Measure owner actions, duplicate rate, secret-release rate, reconciliation coverage, recovery time and drift-detection time.
- Require JARVIS assurance, CFBE value acceptance and current Sentinel health.
- Promote only after the complete Fully Established record passes.

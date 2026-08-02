# Sovereign Intent Guardian

The Sovereign Intent Guardian (SIG) is a Formation-governed, read-only owner-intent audit foundation. It compares a proposed action with current mission, source, continuity, burden, cost and authority evidence. It can return `ALIGN`, `ALIGN_WITH_CONDITIONS`, `BLOCK` or `SOVEREIGN_DECISION_REQUIRED`.

Every result permanently states:

- `authorizes_action: false`
- `effect_performed: false`
- `release_authority: NONE`

An `ALIGN` result is never a permit. Formation remains the only governor and action router.

## Current maturity

`DURABLE_FOUNDATION_IMPLEMENTED_NOT_DEPLOYED`

The package implements and locally tests persistent single-host queue mechanics. It is not deployed, scheduled, multi-host, production-proven or autonomous. No provider was called while building or testing it. No cloud, connector, email, GitHub mutation, command-execution or secret-access adapter is included.

Current local proof: 51 focused guardian tests pass after repeated independent red-team waves. The current repairs add version-independent active stops, durable mission-version floors, complete request/action attestations, closed state/proof vocabularies, credential-name and secret-value screening on identifiers, closed stop/failure reason codes, a strict Boolean retry flag and an evidence-bound machine-verifiable learning ledger. Repository-wide, static-boundary, MODISA, OIFA and exact-head CI gates must be rerun before draft publication.

## Control plane

The standard-library-only SQLite store provides:

- canonical request hashing and idempotent enqueue;
- exact policy, Formation mission, source-readback, Local Bible and complete proposed-action fingerprints;
- explicit worker and boot identity;
- `BEGIN IMMEDIATE` claims, expiring leases and monotonic fencing;
- a global control generation that fences every pre-stop lease;
- global, mission and requirement stop latches;
- configured-record-bound resume with a newer mission version;
- durable global, mission and requirement minimum-version floors enforced at enqueue and claim;
- bounded retry only for typed transient transport codes supplied by a separately authorised future adapter;
- metadata-only dead letters;
- worker heartbeats;
- append-only hash-chained transition events;
- an idempotent, hash-chained delivered-output ledger for fifth-output cadence;
- deterministic semantic readback.

SQLite is intentionally classified as a local/single-host durable foundation. A live scheduler, supervisor, multi-host database, authentication boundary, encrypted production storage, deployed worker identity and independent runtime attestation remain future proof requirements.

## Advisory-receipt boundary

SIG accepts no provider object, callback or executable adapter. A separately authorised future integration may submit only a data-only advisory receipt containing a provider ID, observation hashes and a suggested verdict enum. The receipt is schema-validated and excluded from deterministic authority. It cannot reduce a block or create a permit; callable objects are rejected without execution.

## Governed learning

Every reproduced defect becomes a deterministic record in `LEARNING_INCIDENTS.json`, a smallest-control repair, a failure-first regression and a healthy-case test. The static verifier recomputes every fingerprint and checks its linked tests and non-promotion state. Independent frozen-source review and a Formation permit remain mandatory before promotion. See `LEARNING_LOOP.md`; this is controlled software improvement, not autonomous self-modification.

## Local verification

From this directory:

```bash
PYTHONPATH=. python -m unittest discover -s tests -v
python verify_guardian.py
python validate_build_contract.py BUILD_CONTRACT.json --require-proof
```

Initialize an explicit local database:

```bash
PYTHONPATH=. python -m sovereign_intent_guardian --database /tmp/sig-local.db init-db
```

The CLI also exposes `enqueue`, `work-once`, `status`, `readback`, `stop`, `resume` and `record-delivered-output`. All commands operate only on the explicit local SQLite file. `enqueue` requires a configured exact request/action allowlist. `resume` requires the expected stop generation, a newer mission version and an exact SHA-256-bound record in the configured resume allowlist.

These registries are local configuration allowlists, not proof of issuer identity, signature validity, expiry or authenticated external Formation authority. A future remote/deployed integration must add and independently verify that trust layer before claiming authenticated authority.

## Safety boundary

SIG must never impersonate or speak for an owner; sign, send, publish or file a communication; consent, waive or settle; choose legal strategy; spend; access secrets; deploy; merge; dispatch workflows; mutate IAM, APIs, billing, traffic or cloud resources; or treat model agreement, tests, a draft PR, heartbeat or SQLite row as proof of owner authority or autonomous runtime.

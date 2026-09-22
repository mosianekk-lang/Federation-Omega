# CFBE Autonomic Capability Fabric

This Genesis foundation turns the existing CFBE estate-audit doctrine into a
deterministic, provider-neutral desired-state and proof-control package. It does
not replace CFBE, SOVARA, JARVIS, Sentinel, Formation or KDV.

## Implemented

- Transactional Estate Twin storage with atomic snapshot ingestion.
- Typed provider descriptors and deterministic intent compilation.
- Reuse-first capability resolution across REUSE, REPAIR, ADAPT and FORGE.
- Sequential proof promotion with evidence readback, trusted verifier attestations,
  predecessor binding, recovery and soak gates.
- Desired-state reconciliation with automatic blocker creation.
- CloudEvents-compatible observation envelopes and W3C trace context.
- Signed, expiring, single-use Formation permits bound to immutable execution contracts.
- Fenced execution journals that execute once and hold ambiguous outcomes for readback.
- Independently keyed event/state checkpoints, a rollback-resistant external
  compare-and-swap anchor, pinned store identity, application-row verification
  and signed provenance-bound atomic restore.
- Explicit blocker generations, strict JSON types and secret-safe persistence.
- Dry-run observation adapters with explicit non-inheritance of provider authority.

## Truth boundary

Current maturity is TESTED_LOCAL only after the local test suite passes.
Repository publication is not provider deployment. Connector observations do
not prove that this package owns provider credentials or can execute external
effects. Durable autonomous status still requires deployed worker identity, a
scheduler, provider-native idempotency and semantic canaries, an externally
protected production identities, recovery proof and measured soak. Local HMAC
authorities and externally supplied test keys prove behavior, not production identity.

## Run

From this directory:

    PYTHONPATH=. python -m cfbe_acf --db /tmp/cfbe-acf.sqlite init
    PYTHONPATH=. python -m cfbe_acf --db /tmp/cfbe-acf.sqlite ingest examples/estate_snapshot.json
    PYTHONPATH=. python -m cfbe_acf --db /tmp/cfbe-acf.sqlite plan examples/intent.json examples/providers.json
    PYTHONPATH=. python -m cfbe_acf --db /tmp/cfbe-acf.sqlite reconcile examples/desired_state.json
    PYTHONPATH=. python -m cfbe_acf --db /tmp/cfbe-acf.sqlite health

## Test

    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python -m unittest discover -s tests -v

## Recovery

Create a verified backup:

    export CFBE_ACF_INTEGRITY_KEY_HEX=<64-or-more-hex-characters>
    export CFBE_ACF_INTEGRITY_AUTHORITY_ID=<trusted-authority-id>
    export CFBE_ACF_ANCHOR_URL=<https-origin-with-atomic-cas-endpoint>
    export CFBE_ACF_ANCHOR_BEARER_TOKEN=<runtime-only-anchor-credential>
    export CFBE_ACF_EXPECTED_STORE_ID=<independently-assigned-store-id>
    PYTHONPATH=. python -m cfbe_acf --db state.sqlite backup backup.sqlite

Restore uses `FabricStore.restore`; it requires the generated provenance
manifest, verifies its SHA-256 and application integrity, stages into a
same-filesystem temporary database, verifies the authority signature and
checkpoint, and atomically activates only after proof. Keys are supplied at
runtime and are never written to the database or manifest. Restore also requires
the external trusted-anchor service and independently pinned store identity used
to seal the source database. A local signed file is deliberately not offered as
a security anchor because coordinated replay of that file and the database is
otherwise indistinguishable from valid historical state.

The anchor service contract is `GET /anchors/{store_id}` plus an atomic
compare-and-swap `PUT` carrying `expected_checkpoint_id` and `anchor`. It must
return the committed anchor and reject stale expected checkpoint IDs with HTTP
409. The client rejects all redirects so bearer credentials cannot cross origin
or downgrade transport. `init` performs a one-time Genesis seal only when both
the database is empty and the external store ID has no anchor; missing local
checkpoints are never automatically recreated. The service is an external
production dependency and is not deployed by this source package.

Every governed database mutation verifies the current application state against
the external anchor inside its SQLite write lock, then seals the resulting state
before commit. A later legitimate operation therefore cannot bless prior
out-of-band tampering.

## Extension contract

A provider adapter must supply an explicit identity, capabilities, authority
ceiling, proof stage, freshness, included-cost class, reversibility,
failure-domain identity and semantic-readback support. Raw authentication
material is prohibited from descriptors, events, receipts, payloads and adapter
results. Provider proof stages are admitted only when derived from the current
mission's validated receipt chain.

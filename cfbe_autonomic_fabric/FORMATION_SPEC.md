# Formation specification

Mission: CFBE-ACF-GENESIS-20260826

Authority:

- Local design, implementation and deterministic testing: A1.
- Reversible GitHub branch and pull request: A2 with a current single-use permit.
- Provider execution, identity changes, paid infrastructure and production
  cutover: not inherited and not granted by this package.

Sovereign boundaries:

- CFBE owns benchmark, estate-intelligence and proof scoring.
- SOVARA owns authorized route and effect execution.
- JARVIS owns independent assurance and promotion holds.
- Sentinel owns health, freshness and drift observation.
- Formation owns mission, authority, cost, burden and permit gating.
- KDV retains canonical durable state.

One effectful path is allowed at a time. Every execution requires an immutable
contract and a trusted, expiring, single-use Formation permit bound to mission
version, action, provider, route, payload, authority, cost and SOVARA executor
identity. Effectful adapters require a non-dry-run effectful route; observation
adapters remain non-effectful. Unknown cost, stale authority, missing semantic
readback, missing rollback or insufficient proof fails closed.

Permit issue reads the canonical mission registry. Final current-mission
validation, permit consumption, effect-lease acquisition and PENDING execution
reservation are one atomic write transaction that rejects stopped, held,
superseded or non-current versions. A database-backed global effect lease prevents
distinct effectful contracts from overlapping; an UNKNOWN outcome holds that
lease until separately governed recovery.

Genesis uses keyed reference authorities to prove the enforcement behavior.
Production binding requires externally held Formation/JARVIS identities and an
externally held keys for signed event/state checkpoints plus an independently
assigned expected store identity and a rollback-resistant external HTTPS CAS
anchor; those production identity bindings and the anchor service are not
claimed as deployed by this source package. A replayable local signed-file
anchor is not an admissible production substitute.

Genesis anchor provisioning is a one-time action that requires an empty database
and an absent external anchor. Missing local checkpoints fail closed and cannot
be automatically resealed. Bearer-authenticated anchor calls reject all redirects.

Stop conditions:

- user supersession;
- mission-version or provider-contract drift;
- any detected sensitive material;
- non-zero unapproved cost or user burden;
- semantic mismatch;
- test or integrity failure;
- unavailable rollback or independent verifier.

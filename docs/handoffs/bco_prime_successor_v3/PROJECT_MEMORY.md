# Project memory — BCO-Prime successor v3

## Checkpoint

The additive successor is implemented in an isolated tree. It preserves v2 and
the canonical 100-capability core and adds fourteen governed v3 operations.
The first adversarial run discovered two genuine contract gaps: empty adaptive
candidate acceptance and camelCase effect-key escape. Both were repaired, and
the complete repository suite then passed. A third proof-discovered defect in
the standalone verifier's repository-path bootstrap was repaired. The final
suite passes 53/53, and the direct verifier passes 100 core, 24 legacy, 2 v2
meta, 8 expected-blocked engine and 14 successor routes.

Fresh extraction of the first thin archive exposed a fourth real defect: three
inherited v2 integration tests could not locate the verified adjacent
`cff_unpacked` engine/dependency. The corrected release topology packages
`upstream/` and `cff_unpacked/` as siblings; this is a portability repair, not a
runtime-code change.

The topology-correct candidate then passed in a fresh root: 18/18 source
hashes, 53/53 tests including inherited CFF integration, the exhaustive route
verifier, MODISA proof validation and RealityGuard. Local scoped proof is now
true; deployment, registration, provider mutation and full-meta readiness
remain false.

## Capability boundary

- Flight ledger: append-only JSONL, causal IDs, sequence, timing, taxonomy,
  chain verification, checkpoint, replay and drift.
- Harvesting: local authorized roots only, safe parsing, redaction, provenance,
  licence, tenant/matter binding, content dedupe plus occurrence preservation.
- Compilation: acyclic opportunity graph and declarative non-executable shadow
  package.
- Qualification: at least 30 paired cases, minimum 0.03 uplift, zero hard
  regressions, rollback and independent verification.
- Adaptation: telemetry-derived reversible candidates only; no self-promotion.
- Meta closure: exact-path and SHA-256 verification for three genuine artifacts;
  no stubs.

## Resume order

1. README.md
2. BUILD_CONTRACT.json
3. docs/architecture/BCO_PRIME_SUCCESSOR_V3.md
4. benchmarking/cfbe_omega/BCO_PRIME_SUCCESSOR_V3.json
5. proof/bco_prime_successor_v3/RELEASE_PROOF.json

Then validate the source manifest, run all tests, execute the 100-core sweep and
confirm an unconfigured meta closure returns `BLOCKED_WITH_ROUTE` with
`safeSubsetReady=true`.

## Truth boundary

The runtime is local and on demand. It is not a deployed autonomous system.
Provider registration, network harvesting, credential collection, generated
code execution and stable promotion remain false. The full meta runtime remains
blocked unless the three real dependencies are independently supplied and
hash-pinned.

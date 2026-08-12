# JFRIE v2 / EACIA — assurance extension slice 1

## Purpose

This additive slice reuses the admitted `jfrie_v2.py` core-parity implementation and closes a bounded set of execution-assurance gaps without replacing or weakening the core.

It is `A1_INTERNAL` and has no authority to file, send, mutate evidence, create provider effects or self-promote doctrine/maturity.

## Controls added

`jfrie_v2_assurance.py` adds deterministic fail-closed controls for:

1. **EA-02 execution receipts** — every assurance control emits a structured object/source/test/expected/observed/state/limitation/tool/time/release-effect receipt.
2. **T008 / D017 node freshness** — a stored readback does not prove the executing node is current.
3. **T003 / D003 date drift** — originating-instrument and derivative dispute-date conflict blocks release pending reconciliation.
4. **T004 / D005 transmission-to-knowledge** — sending/delivery does not prove reading or knowledge.
5. **T005 / D006 silence-to-agreement** — non-response does not prove acceptance/agreement.
6. **T009 / D013 attachment completeness** — referenced attachment IDs must all be independently verified.
7. **EA-07 hash scope** — a hash claim without explicit object/byte/semantic scope is release-blocking.
8. **EA-08 role is not authority** — role/title and act-specific authority must be separately sourced for material authority claims.
9. **T011 / C098 generated-detector promotion** — generated detectors remain shadow-only until shadow testing and false-positive criteria both pass.

## Controls intentionally reused, not duplicated

The admitted core remains authoritative for:

- v1/v1.1 referral/jurisdiction hard gates and T001 semantic-laundering protection;
- stable claim/source identities and provenance;
- derivative-source-root collapse (T002);
- explicit claim release eligibility;
- quarantine and contamination-radius propagation (T007/T010/T012 family);
- excluded-matter blocking (T006);
- core node readback/snapshot/recheck/owner-exclusion release firewall;
- recall identification and downstream dependency review.

The assurance wrapper is monotonic: **it may add blockers; it may never clear a blocker returned by the core.**

## Remaining full-v2 parity gaps

This slice does not establish full C001–C100 executable parity. Remaining work includes the families already listed in `V2_CORE_PARITY_SCOPE.md`, especially generalized semantic paraphrase detection, automatic thread reconstruction, current-law retrieval, infected-template child discovery, broad prompt/memory pollution scanning, provider-bound immutable release snapshots, complete post-release monitoring, and full automatic detector lifecycle orchestration.

## Admission and maturity boundary

Source and tests are only a candidate until exact-head Airlock and Public Repository Leak Guard pass and the admitted source is read back from current `main`.

Even after source admission, this slice is not `SHADOW_VALIDATED`, `ADVERSARIALLY_VALIDATED`, `CANARY_VALIDATED`, `LIMITED_WORKFLOW_VERIFIED`, `FULL_V2_PARITY` or `OPERATIONAL_VERIFIED` without the separate proof required for those states.

# Federation Omega — Superior Logic Runtime

This repository hosts the Superior Logic v3.2 multi-route runtime, deployment assets, recovery tooling, resolver registry and hosted CI.

## ECASP corpus-selection gate

`ALG-ECASP-001` prevents inventory, pagination, indexing, metadata, snippets, familiar names or polished artefacts from being reported as exhaustive corpus analysis.

The runtime exposes `POST /ecasp/evaluate`. It evaluates gates G1–G10 and releases only one honest state:

- `DISCOVERY_INCOMPLETE`
- `INVENTORY_COMPLETE_ANALYSIS_INCOMPLETE`
- `PROVISIONAL_SHORTLIST`
- `BOUNDED_SELECTION`
- `EXHAUSTIVE_FINAL`

Every evaluation is written into the hash-chained Superior Logic event ledger. `EXHAUSTIVE_FINAL` is fail-closed until inventory, bodies, attachments, capability decomposition, version lineage, conflicts, requirement coverage, counterexample search, independent readback and claim-language matching all pass.

## SLRK execution and claim controls

The Superior Logic Runtime Kernel adds typed controls that turn the earlier Governor and engine-lifecycle doctrines into runtime-enforced state:

- `POST /capabilities/register` — register an explicit capability contract.
- `POST /capabilities/assess` — fail closed when required capabilities are missing, authority-gated, runtime-dependent or design-only.
- `POST /claims/govern` — prevent words such as `live`, `deployed`, `complete`, `final` and `fully automated` from exceeding their proof and lifecycle gates.
- `POST /faults` — persist a fault and automatically ban its linked route.
- `GET /routes/{route_id}` — read the route-memory state.
- `POST /routes/{route_id}/clear` — clear a banned route only after a material condition change.
- `POST /engines/evaluate-promotion` — enforce sandbox, staging and production promotion gates.

Capability contracts, assessments, claim decisions, faults, route changes and engine-promotion decisions are written into the hash-chained event ledger. A ledger entry is not treated as execution proof.

CI runs runtime, ECASP and typed FastAPI endpoint tests, including false-completion, authority-gate, route-memory and production-promotion regressions.

CI trigger checkpoint: 2026-07-29T03:10:00+02:00

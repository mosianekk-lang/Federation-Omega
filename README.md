# Federation Omega — Superior Logic Runtime

This repository hosts the Superior Logic v3.1 multi-route runtime, deployment assets, recovery tooling, resolver registry and hosted CI.

## ECASP corpus-selection gate

`ALG-ECASP-001` prevents inventory, pagination, indexing, metadata, snippets, familiar names or polished artefacts from being reported as exhaustive corpus analysis.

The runtime exposes `POST /ecasp/evaluate`. It evaluates gates G1–G10 and releases only one honest state:

- `DISCOVERY_INCOMPLETE`
- `INVENTORY_COMPLETE_ANALYSIS_INCOMPLETE`
- `PROVISIONAL_SHORTLIST`
- `BOUNDED_SELECTION`
- `EXHAUSTIVE_FINAL`

Every evaluation is written into the hash-chained Superior Logic event ledger. `EXHAUSTIVE_FINAL` is fail-closed until inventory, bodies, attachments, capability decomposition, version lineage, conflicts, requirement coverage, counterexample search, independent readback and claim-language matching all pass.

CI trigger checkpoint: 2026-07-29T00:00:00+02:00

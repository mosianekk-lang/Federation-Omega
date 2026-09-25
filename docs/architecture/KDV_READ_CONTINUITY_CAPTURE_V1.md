# KDV_READ_CONTINUITY_CAPTURE_V1

## Purpose

F313 closes only the remaining composition gap between an already-authenticated
KDV row reader and the admitted F312 AS_OF continuity archive.

It does not implement Google authentication or transport. The estate already has
KDVSheetsReader-compatible authenticated reads. It does not create a datastore,
writer, scheduler, truth root, or memory root.

## Live shape canary

A bounded provider read of BMF_SHADOW_EVENTS during the F312/F313 workstream
returned the same 21-field contract consumed by FKCM.from_bmf_row, including
event/stream identity, version, truth/privacy, payload/source/proof JSON, lineage,
provider-persisted time, contradiction/supersession fields, and schema version.

The source candidate stores only the contract result, not the live KDV payload.

## Pipeline

authenticated provider reader -> verified BMF row set -> strict row validation
-> immutable row-set digest -> FKCM.from_bmf_row -> F312 deterministic AS_OF archive

## Boundary

Source admission proves the compiler logic only. The live shape canary proves
transport compatibility, not deployed runtime binding. A caller must still supply
a verified provider read at execution time. The resulting archive remains
non-authoritative and AS_OF_ONLY.
# Federation Omega 24-Hour Alpha→Omega Implementation Plan

## Mission

Consolidate Federation Omega, Secondary Brain, MODISA, Sol/Omega-Max, EvidenceOps pointers, CloudOps, Direct Runtime, Bible, GitHub and related systems into one proof-carrying canonical control model before `2026-08-05T00:04:07+02:00`.

## Stage plan

| Window | Stage | Deliverables | Release gate |
|---|---|---|---|
| H00-H02 | Baseline and freeze | rollback snapshot; no-new-family rule; owner-workstream map | baseline hashes and collision exclusions |
| H02-H06 | Canonical truth | 20-system state register; maturity model; receipt schema | unique IDs; one system of record |
| H06-H10 | Lineage and triage | lineage graph; open PR triage; version policy | all open PRs classified |
| H10-H14 | Kernel consolidation | Secondary Brain query contract; MODISA compact kernel; route registry | deterministic validation |
| H14-H18 | E2E proof | intake/readback/restart/rollback canary | zero duplicate effect; hash-linked receipt |
| H18-H21 | Control-plane rationalisation | CloudOps source/operational/read-model split; WIF truth table | ownership and TTL explicit |
| H21-H24 | Publication and value | GitHub merge; Drive tabs; health snapshot; licences | provider readback or exact held state |

## Completion predicate

Completion is achieved only when the canonical register, route registry, lineage, PR triage and Alpha→Omega release gate pass; the end-to-end canary proves readback, restart and rollback; GitHub and Drive publication are independently read back or explicitly held with an exact route; and no EvidenceOps P09 collision occurs.

## Selected external worker

GitHub Actions is selected for A0/A1 validation, artifact generation and provider proof because it has current scoped operational evidence. Direct Google connector remains the canonical Workspace write route.

## Prohibited shortcuts

- no new top-level system family
- no bot-count inflation
- no backup treated as a live source
- no CI treated as Cloud deployment
- no WIF global claim from a route-specific success
- no provider mutation without exact identity, project, scope and readback

# Formation specification — BCO-Prime Chat Forensics v2

## Mission

- Mission ID: CFBE-BCO-V2-BUILD-20260901
- Mission version: 1
- Source: owner reply n
- Goal: repair v1 truth/output defects and unify the harvested local capability
  layers without external deployment.
- Authority ceiling: A1 local internal.
- Cost ceiling: zero.
- Manual user tasks: none.

## Requirements

| ID | Required fruit | State |
|---|---|---|
| R1 | v1.1 truth/output repair | PROVEN_LOCAL |
| R2 | unified v2 registry/kernel | PROVEN_LOCAL |
| R3 | preserve 100 core and v1 compatibility | PROVEN_LOCAL |
| R4 | typed contracts, controls, observability and continuity | IMPLEMENTED |
| R5 | syntax, unit, integration, failure and deterministic proof | PROVEN_LOCAL |
| R6 | no external publication, merge, deployment or registration | PRESERVED |

## Authority boundary

Formation permits in this mission authorize only local reads, code writes,
documentation writes and tests. They do not grant connector, OAuth, IAM,
provider, GitHub, deployment or registration authority.

## Single effectful path

The only runtime write path is
CFFEngineAdapter.run_native_audit(source, title, output_dir, prefix). It writes
seven bounded local artifacts and immediately validates them. Pure registry
operations have no I/O. External effects are rejected.

## Stop and cancellation

ownerActionRequired=false and manualUserTasks=[]. A caller cancels by terminating
the local process. No background worker, lease, queue or scheduled task survives
cancellation. Stop after local contract proof; do not extend the mission into
publish, merge, deploy, register, cross-chat restore, or original incident
re-audit without new authority.

## Claim boundary

Local status is TESTED and READY. Registration, deployment and behavioral proof
are false. Full meta runtime readiness is false because the harvested snapshot
lacks three dependencies. The source-bound safe subset is ready.

# KIOAS Audit-to-Repair Compiler v1

ARC is the thin deterministic bridge between a KIOAS audit finding and the existing Federation repair/execution fabric.

`AUDIT -> CLASSIFY -> CAUSAL COURT -> CFBE PREPASS -> RCSG -> ROUTE TOURNAMENT -> PLAN -> FENCE/CANARY -> EXECUTE THROUGH EXISTING OWNER -> SEMANTIC READBACK -> INDEPENDENT ASSURANCE -> VALUE -> LEARN -> TERMINALITY`

It does not create another scheduler, state store, proof plane, provider executor, or authority plane.

## Classification

- `AUTO_REPAIR_NOW`: reversible, zero/included-cost, A0/A1, callable and independently readable back.
- `AUTO_REPAIR_FENCED`: same, but shared/canonical state mutation requires FDOF fencing.
- `AUTO_REPAIR_CANARY`: repair is plausible but needs a shadow/canary before bounded promotion.
- `WAITING_EXACT_CAPABILITY`: repair is known but the exact executor/capability is currently unavailable; persist a resumable trigger.
- `OWNER_OR_PROVIDER_TRIGGER_REQUIRED`: the exact effect requires provider/owner authority beyond the current ceiling.
- `QUARANTINE_AND_REROUTE`: repeated unchanged failure fingerprint; circuit-break and choose a materially different route.
- `NOT_APPLICABLE` / `REJECTED_WITH_EVIDENCE`: evidence-backed terminal dispositions.

## Completion

An audit cannot close while a material finding still has an executable repair. A repair is verified only after semantic target-native readback, independent assurance, no regression, rollback proof, authority/cost preservation and positive value or a separately justified safety/proof gain.

Recurring wake/resume work belongs only to the existing Google Apps Script GNS3 scheduler.

## CFBE-Ω benchmark binding

Every material compilation requires a relevance-bounded CFBE pre-pass reference. ARC binds the current CFBE practices for AgentOps (`P-012`), autonomous incident/change lifecycle (`P-017`), bounded cells (`P-022`), progressive promotion (`P-023`), Kubernetes-style reconciliation (`P-024`), shared-state conflict/idempotency control (`P-025`), cross-session failure mining (`P-033`) and durable resumable steps (`P-011`). It also consumes the standing high-scale opportunity and V100 pre/closure lenses without becoming a benchmark engine itself.


## Content-addressed candidate concurrency control

ARC candidate bytes are immutable per digest. Parallel lanes may form candidates concurrently, but each candidate receives a unique content-addressed file identity. A serving/current pointer is the only mutable projection and can move only through compare-and-set against a freshly read expected digest followed by exact readback. Stale pointer writers return `HOLD_CONCURRENT_DRIFT`. Superseded candidates/revisions remain preserved; no destructive cleanup is implied.

This rule was added after `FLT-ARC-CONCURRENCY-001`, where parallel ARC work reused one mutable Drive candidate ID and stale metadata crossed into a GNEN artifact row. The recovery proved the correct pattern: preserve history, compute the real provider-file digest, repair only the corrupted pointer fields, and promote a new immutable candidate through a fresh pointer court.

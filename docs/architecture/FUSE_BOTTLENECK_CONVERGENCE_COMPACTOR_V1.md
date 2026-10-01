# FUSE Bottleneck Convergence Compactor v1

## Purpose

This tranche removes recurring coordination bottlenecks without creating another sovereign controller, scheduler, truth root, memory root, mission bus, authority root or Judge.

It extends the existing vNext Mission Execution Kernel with a small deterministic convergence layer.

## Residual defects addressed

1. **Cross-plane transition drift** — mission, lease, source, effect, proof, reducer and receiver state can temporarily disagree.
2. **Over-broad source serialization** — unrelated source domains can be unnecessarily blocked by one repository-wide writer.
3. **Repeated failed-route consideration** — a route can be reconsidered without a material prerequisite change.
4. **Broad invalidation** — unrelated proofs/currentness can be re-evaluated after a narrow dependency change.
5. **Routing entropy** — completed/superseded history can remain visible to the live election graph.
6. **Slow simple actions** — exact current/callable/authorized routes can still pay full orchestration cost.
7. **Mission/lease binding defects** — an active source lease can exist without an explicit canonical mission identity.

## Mechanisms

### TransactionEnvelope

A material transition is coordination-complete only when its exact semantic fan-in is satisfied:

- source state is explicit;
- lease is RELEASED;
- unknown effects have been read back;
- proof is PASS;
- reducer projection is APPLIED;
- every required receiver is ACKED.

This does not collapse proof maturity. It prevents a source event from being treated as globally coordinated before its required projections converge.

### ScopedFenceSet

Fences are bound to canonical resource scopes. Pairwise-disjoint scopes may execute concurrently. Overlapping scopes fail closed. Fencing tokens remain monotonic.

This is a compatibility mechanism for gradually reducing repository-wide critical sections. It does not itself modify the existing FDOF provider lock or grant write authority.

### NegativeRouteMemory

A failed route is suppressed for the same operation and material context until either:

- its context hash changes; or
- one of its declared wake signals occurs.

This makes `NO_UNCHANGED_RETRY` executable routing state rather than prose-only guidance.

### CausalInvalidationGraph

A changed node invalidates only its causal descendants. Unrelated siblings remain valid.

The existing vNext proof invalidation semantics remain authoritative for kernel-bound proofs; this graph generalizes the same mechanism to other typed state.

### Active graph compaction

Operational routing is partitioned into:

- ACTIVE/live;
- DORMANT/event-waiting;
- HISTORICAL/terminal; and
- UNKNOWN.

History remains immutable and hash-addressed but historical nodes are excluded from ordinary live route election.

### Fast path

Direct execution is eligible only when the exact capability is:

- current;
- callable now;
- authorized for the action;
- proof-scope compatible;
- readback-capable; and
- rollback-capable for effectful fast-path operations.

Otherwise normal FUSE orchestration remains in force.

### Cross-plane invariant audit

The first invariant set includes:

- no ACTIVE lease without a canonical mission;
- no overlapping ACTIVE scoped fences;
- no duplicate fencing token in the audited set.

Additional invariants can be appended without changing authority semantics.

## Integration boundary

This module is provider-neutral and effect-free.

It does not:

- mutate provider IAM;
- deploy runtime infrastructure;
- change traffic;
- send communications;
- create recurring spend;
- self-certify runtime, behavioural, owner-value or COMPLETE maturity.

Existing FDOF source coordination, ProofOS/Reality Judge, Capability Truth, Work Plane, KDV and provider-native readback remain authoritative in their existing roles.

## Promotion sequence

1. local deterministic court;
2. exact branch/head hosted tests;
3. Airlock/Bubbles/Leak Guard;
4. source admission under the active FDOF lease;
5. release the lease from provider-native readback;
6. project mission/lease/proof/currentness receivers;
7. separately bind runtime consumers;
8. separately measure owner-effect latency and owner-value improvement.

## Owner-facing target

The success metric is not number of new mechanisms.

The target is lower:

**OWNER INTENT -> TERMINAL OWNER EFFECT latency**

while preserving zero unintended writes, proof-before-claim, current authority boundaries and recoverability.

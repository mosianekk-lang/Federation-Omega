# FUSE Runtime Convergence Binding v6 — FRCB-006

Status: SOURCE CANDIDATE / STACKED ON FRCB-005 / PROVIDER-EXECUTION CONVERGENCE

## Mission

FRCB v6 closes the largest remaining gap between capability callability and actual
provider execution.

V5 proves that a qualifying FDOF executor route was selected and fenced. V6 requires
that the exact route/fence then produces:

1. one durable provider dispatch record;
2. an accepted provider dispatch;
3. provider-native semantic readback;
4. readback correlation to the provider operation;
5. semantic state that matches the request's expected readback contract;
6. a verified SOL 6.2/FDOF event chain.

Only then may provider execution be promoted.

## Existing execution plane reused

V6 does not introduce a new provider runtime. It reuses:

- `FederationDistributedOperatingFabric`
- `FederationProviderBridge`
- the V5 `FDOFCapabilityActivationReceipt`
- the existing FDOF route decision
- the existing SOL 6.2 transition lease/fence
- the existing provider adapter dispatch function
- the existing provider adapter readback function
- the existing FDOF event chain

The V6 adapter is a thin bridge from the existing execution state into an
FRCB-specific immutable receipt.

## Provider-bridge hardening

The existing FDOF provider bridge already separated dispatch from semantic readback.
V6 hardens that distinction:

- a dispatch with `accepted=False` and no uncertain-effect condition becomes
  `DISPATCH_REJECTED` and is never promoted to execution;
- a `ReadbackReceipt(verified=True)` is insufficient by itself;
- provider-native evidence must be present;
- a provider correlation identifier must be present;
- the semantic readback must match `ProviderExecutionRequest.expected_readback`;
- the supplied dispatch receipt must match the durable provider-request record.

This removes a self-attestation seam in which an adapter could set
`verified=True` without provider-native semantic evidence.

## Exact V5→V6 binding

The V6 execution receipt binds:

- mission ID
- FDOF route ID
- transition ID
- executor ID
- provider
- operation
- target
- V5 activation receipt digest
- lease epoch
- fencing token
- exact provider request SHA-256
- idempotency key
- provider request ID
- provider correlation ID
- semantic state
- readback-evidence digest
- verification epoch

The provider execution must occur while the V5 transition fence is still valid.

A later V6/FRCB evaluation may consume this historical provider proof after that
lease expires; it does not pretend that the original lease remains live forever.

## Stage maturity after v6

- AAREK — PRODUCER_INVOCATION_VERIFIED
- OH50 — PRODUCER_INVOCATION_VERIFIED
- Formation Innovation — FOUNDRY_CYCLE_RECEIPT_VERIFIED
- Alpha-Omega — LOCAL_BUILD_RECEIPT_VERIFIED when required
- Capability Activation — CAPABILITY_ROUTE_FENCE_VERIFIED
- Provider Execution + Readback — PROVIDER_EXECUTION_READBACK_VERIFIED
- F130 terminal completion — NOT VERIFIED

## Promotion exclusions

The following remain insufficient for V6 promotion:

- HTTP/transport success alone
- provider dispatch acknowledgement alone
- source code
- CI green
- local build
- selected provider route
- healthy executor
- a `verified=True` readback Boolean without provider-native evidence
- readback with no provider correlation
- readback that does not match the expected semantic state
- a provider receipt from another mission/route/transition/executor/target
- a stale or substituted V5 activation receipt

## Bubbles / SOVARA relationship

The Bubbles Provider Cell Mesh remains a valid provider-routing and provider-readback
host surface, and SOVARA remains an effect/provider execution authority layer where
applicable. V6 deliberately does not dispatch the same effect through multiple
provider runtimes merely to obtain redundant receipts.

The canonical V6 path in this tranche is the V5 FDOF route/fence followed by the
existing FDOF ProviderBridge. A future normalization adapter may consume equivalent
Bubbles/SOVARA receipts without re-executing the effect.

## ProofOS topology

V6 introduces:

- `FUSE_FDOF_PROVIDER_EXECUTION_READBACK_V1`
- `FUSE_RUNTIME_CONVERGENCE_BINDING_V6`

V6 depends on:

- FUSE_RUNTIME_CONVERGENCE_BINDING_V5
- FUSE_FDOF_PROVIDER_EXECUTION_READBACK_V1
- FEDERATION_CORE

The V6 court is GLOBAL blocking.

## Truth boundary

A green V6 court proves source-level correctness of the binding and deterministic
provider-execution/readback fixtures. It does not itself prove that an arbitrary
real-world provider operation has occurred unless the runtime receipt comes from an
actual provider adapter and provider-native readback.

V6 still does not prove:

- authoritative whole-owner-mission snapshot compilation;
- F130 PREPARE_TERMINAL;
- terminal state/epoch/ledger CAS;
- F130 COMMIT;
- whole-mission COMPLETE_VERIFIED;
- native ChatGPT response interception.

## Next tranche — V7

V7 should compile the durable mission estate into the authoritative
`MissionRuntimeSnapshot` consumed by F130.

Its source inputs should include the durable mission ledger, MissionProofPassport and
the V1→V6 convergence receipts. Caller-provided terminal booleans must not be the
evidentiary root.

# FUSE Runtime Convergence Binding v5 — FRCB-005

Status: SOURCE CANDIDATE / STACKED ON FRCB-004 / A1_INTERNAL / NO PROVIDER DISPATCH

## Mission

FRCB v5 advances the convergence chain from source/local-build maturity to verified,
time-bounded **capability activation**.

A qualifying FDOF executor must be selected under fresh health evidence and a live
SOL 6.2 transition fence. That makes the route callable at the recorded epoch. It
does not mean the provider action was dispatched or that any external effect happened.

## Existing estate reused

V5 reuses:

- FederationDistributedOperatingFabric route selection;
- existing ExecutorSpec and HealthObservation contracts;
- existing FDOF health TTL and capability/target/authority/cost filters;
- SOL 6.2 execution fencing;
- the existing SOL 6.2 hash-chained event integrity court;
- FRCB v4 for all upstream convergence evidence.

No duplicate scheduler, provider plane, authority plane or proof database is created.

## Activation sequence

The FDOF FRCB adapter performs:

1. exact RouteRequest compilation by the caller;
2. FDOF route selection;
3. independent recomputation of the RouteRequest SHA-256;
4. readback of the selected executor definition;
5. readback of the current executor health observation;
6. a second FDOF health-state check;
7. acquisition of the SOL 6.2 transition fence;
8. FDOF/SOL 6.2 event-chain integrity readback;
9. construction of an immutable activation receipt.

The activation receipt binds:

- mission;
- route and transition;
- operation and target;
- required capabilities;
- request authority ceiling;
- executor/provider identity;
- executor authority ceiling;
- route score/version/request hash;
- health observation, TTL, proof reference and evidence class;
- transition lease epoch/fencing token/expiry;
- exact activation verification epoch.

## Freshness rule

Activation is not a permanent property.

The receipt is usable only while its transition fence remains live. A V5 receipt records
that capability activation was verified at a specific epoch and explicitly states that
downstream execution must revalidate freshness.

An expired fence fails V5 admission.

## Alpha-Omega target binding

When an AlphaOmegaPacket exists, its `runtime_target` is the exact FDOF target expected
by V5. A different FDOF target cannot be substituted into the convergence chain.

## Stage maturity after v5

The existing V1-V4 stages remain unchanged. V5 adds:

- CAPABILITY_ACTIVATION — CAPABILITY_ROUTE_FENCE_VERIFIED

Still unverified:

- provider dispatch
- provider effect
- provider-native execution outcome
- provider semantic readback
- F130 terminal completion

## ProofOS topology

V5 explicitly registers the relevant FDOF/SOL 6.2 source surface as:

`FUSE_FDOF_CAPABILITY_ACTIVATION_V1`

That subsystem covers the FDOF router, SOL 6.2 runtime/fencing primitives, the new thin
FRCB activation adapter and the immutable activation receipt contract.

FRCB v5 depends on:

- FUSE_RUNTIME_CONVERGENCE_BINDING_V4
- FUSE_FDOF_CAPABILITY_ACTIVATION_V1
- FEDERATION_CORE

The V5 court is GLOBAL blocking.

## Truth boundary

V5 can prove that a qualifying FDOF route and live transition fence existed at the
recorded epoch under current deterministic health evidence and SOL 6.2 integrity.

V5 does not prove provider dispatch, provider execution, provider semantic readback,
provider-created authority, F130 terminal commit, native ChatGPT interception or
whole-mission COMPLETE_VERIFIED.

## Next convergence tranche

V6 should consume the existing FDOF Provider Bridge and/or Bubbles ProviderExecutionReceipt
and promote provider runtime only after exact provider-native execution plus independent
semantic readback. Dispatch acknowledgement alone must remain insufficient.

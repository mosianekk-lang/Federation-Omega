# FUSE Runtime Convergence Binding v1 — FRCB-001

Status: SOURCE CANDIDATE / SCREEN-FIRST / A1_INTERNAL / NO EXTERNAL EFFECTS

## Problem

FUSE already has strong specialist contracts, but some composition points still accept
caller-supplied references or typed objects without proving that the producer stage
actually executed.

A reference is useful for identity. It is not execution evidence.

## v1 scope

FRCB-001 performs an actual AAREK evaluation and binds the resulting receipt digest into
the existing OF50 request. It also validates mission, objective and authority identity
across the OH50 SwarmManifest, FormationDecision and AlphaOmegaPacket.

v1 deliberately labels those latter three stages STRUCTURALLY_BOUND because validating
their typed objects is not yet producer-attested execution.

## No new sovereign plane

FRCB is an adapter. It does not schedule work, authorize effects, execute providers,
persist canonical memory, replace ProofOS, replace OF50, or create another foundry.

## Promotion ladder

- V1 — AAREK real invocation binding
- V2 — OH50 producer-attested receipt binding
- V3 — Formation foundry-cycle receipt binding
- V4 — Alpha-Omega build/lifecycle receipt binding
- V5 — RAEFI/FDOF capability-activation receipt binding
- V6 — Bubbles/SOVARA semantic execution readback binding
- V7 — whole-owner-mission snapshot producer binding into F130

## Acceptance

- fake/nonmatching AAREK receipt ref is rejected;
- AAREK is actually invoked;
- exact mission/objective/authority are preserved;
- OH50 and Formation objects are structurally validated;
- Alpha-Omega is mandatory when implementation is required;
- stage maturity is not inflated;
- convergence receipt is deterministic;
- OF50 remains the completion governor.

## Truth boundary

FRCB v1 proves only that an actual AAREK evaluation is performed and cryptographically
bound into the OF50 request inside this adapter, while the supplied OH50, Formation and
Alpha-Omega objects pass their existing structural validation and identity checks. It does
not prove that OH50, the Formation Foundry or Alpha-Omega producer runtimes executed, and
it does not inherit provider execution, authority, deployment, semantic readback, owner
value or COMPLETE_VERIFIED.

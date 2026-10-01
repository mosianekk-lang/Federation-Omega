# FUSE Runtime Convergence Binding v1 — FRCB-001

Status: SOURCE CANDIDATE / SCREEN-FIRST / A1_INTERNAL / NO EXTERNAL EFFECTS

## Rerouted mission

FRCB-001 is now treated as the first stage of a wider Evidence-to-Terminal-Truth
Convergence route. It is not another completion controller and must not become one.
Its job is to turn producer evidence into increasingly authoritative, cryptographically
bound mission state that can eventually be consumed by the existing F130 terminal
interlock.

The completion chain remains:

AAREK -> OH50 -> Formation Innovation -> Alpha-Omega when required -> execution ->
semantic readback -> OF50 stage completion -> Bubbles production/proof closure ->
F130 PREPARE_TERMINAL -> F130 terminal commit -> COMPLETE_VERIFIED.

FRCB is an adapter across that chain. It must preserve the authority of the existing
courts rather than replace them.

## Problem

FUSE already has strong specialist contracts, but some composition points still accept
caller-supplied references or typed objects without proving that the producer stage
actually executed.

A reference is useful for identity. It is not execution evidence.

A second risk is equally important: a real producer receipt must carry its producer
state. A receipt from AAREK that says more work is required cannot be used merely as a
non-empty reference to support a downstream completion request.

## v1 scope

FRCB-001 performs an actual AAREK evaluation and binds the resulting receipt digest into
the existing OF50 request. It validates mission, objective and authority identity across
the OH50 SwarmManifest, FormationDecision and AlphaOmegaPacket.

When OF50 completion is requested, FRCB also requires the freshly evaluated AAREK
receipt to be COMPLETE_VERIFIED / ALLOW_COMPLETE_VERIFIED. AAREK invocation therefore
cannot be reduced to a non-empty receipt reference at the completion boundary.

v1 deliberately labels OH50, Formation and Alpha-Omega STRUCTURALLY_BOUND because
validating their typed objects is not yet producer-attested execution.

## Terminal-truth boundary

FRCB v1 is not allowed to emit whole-owner-mission terminal completion. Its receipt
separates:

- `of50_completion_verified`: the embedded OF50 court's result;
- `f130_terminal_completion_verified`: always false in v1;
- `provider_execution_verified`: always false in v1;
- `completion_verified`: terminal-safe compatibility alias for the F130 field and
  therefore false in v1.

The convergence receipt self-verifies against its deterministic payload, and its truth
boundary is exposed as an immutable mapping.

## ProofOS dependency topology

FRCB is a dependent of all three of these admission roots:

- FEDERATION_CORE
- FUSE_AAREK_V1
- FUSE_OF50_ACE_V1

That direction matters. A change to either AAREK or OF50 must impact FRCB and select its
compatibility courts. FRCB-specific tests remain GLOBAL blockers while using ProofOS's
existing failure-class taxonomy; FRCB does not widen or weaken ProofOS core.

## No new sovereign plane

FRCB does not schedule work, authorize effects, execute providers, persist canonical
memory, replace ProofOS, replace OF50, replace F130, or create another foundry.

## Promotion ladder

- V1 — AAREK real invocation and completion-state binding
- V2 — OH50 producer-attested receipt binding
- V3 — Formation foundry-cycle receipt binding
- V4 — Alpha-Omega build/lifecycle receipt binding
- V5 — RAEFI/FDOF capability-activation receipt binding
- V6 — Bubbles/SOVARA semantic execution readback binding
- V7 — authoritative whole-owner-mission snapshot producer binding into F130

Each version must preserve the prior truth boundary and may only promote a stage when the
producer's own receipt and verification contract are available.

## Acceptance

- fake/nonmatching AAREK receipt ref is rejected;
- AAREK is actually invoked;
- an incomplete AAREK receipt cannot support an OF50 completion request;
- exact mission/objective/authority are preserved;
- OH50 and Formation objects are structurally validated;
- Alpha-Omega is mandatory when implementation is required;
- stage maturity is not inflated;
- OF50 completion is never presented as F130 terminal completion;
- convergence receipt is deterministic and self-verifying;
- receipt truth-boundary state is immutable;
- AAREK/OF50 upstream changes impact the FRCB ProofOS court;
- F130 remains the final whole-mission terminal commit authority.

## Current truth boundary

FRCB v1 proves only that an actual AAREK evaluation is performed and cryptographically
bound into the OF50 request inside this adapter, that an OF50 completion request cannot
proceed unless that evaluated AAREK state permits completion, and that the supplied OH50,
Formation and Alpha-Omega objects pass their existing structural validation and identity
checks.

It does not prove that OH50, the Formation Foundry or Alpha-Omega producer runtimes
executed. It does not inherit provider execution, deployment, semantic readback, owner
value, F130 terminal commit, native ChatGPT serving-stack interception, or
COMPLETE_VERIFIED.

## Rerouted execution sequence

1. Admit V1 without weakening ProofOS.
2. Verify dependency impact from AAREK and OF50 into FRCB.
3. Add producer-attested receipts for OH50, Formation and Alpha-Omega.
4. Bind provider/runtime semantic readback from existing Bubbles/SOVARA execution
   surfaces rather than creating a new execution plane.
5. Compile an authoritative whole-owner-mission snapshot from durable evidence rather
   than treating caller-supplied JSON as terminal provenance.
6. Bind that snapshot into the existing F130 two-phase terminal court.
7. Claim whole-mission COMPLETE_VERIFIED only after F130 terminal commit and all
   mission-required provider/readback proof is present.

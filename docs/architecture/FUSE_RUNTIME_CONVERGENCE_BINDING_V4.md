# FUSE Runtime Convergence Binding v4 — FRCB-004

Status: SOURCE CANDIDATE / STACKED ON FRCB-003 / A1_INTERNAL / NO PROVIDER EFFECTS

## Mission

FRCB v4 advances Alpha→Omega from a structural lifecycle packet to verified **local
BUILD** evidence when implementation is required.

It deliberately does not pretend that a successful local package build proves testing,
provider deployment, provider-native verification, operation, semantic readback or
whole-mission completion.

## Existing engine reused

V4 reuses the existing AlphaOmegaEngine and its `execute_local_build` path. The
existing engine already materializes:

- `architecture.json`
- `work_packets.json`
- `maintenance.json`
- `README.md`

and emits `LOCAL_OPERATIONAL_PACKAGE_BUILT`.

The new FRCB lifecycle adapter calls that existing path rather than creating a second
builder.

## Content-addressed local-build receipt

After the existing local BUILD executes, V4:

1. requires the packet/build-plan identity to agree;
2. requires the engine build state to be `LOCAL_OPERATIONAL_PACKAGE_BUILT`;
3. requires the engine truth boundary to say artifacts were built;
4. rejects any provider-deployed, provider-readback or operational-verification claim;
5. reads back the four expected artifacts from the current local build directory;
6. hashes each artifact;
7. binds the exact AlphaOmegaPacket digest;
8. emits a self-verifying immutable local-build receipt.

The V4 binder re-reads those artifacts at convergence time. An artifact changed after
receipt creation invalidates the receipt.

## Stage maturity after v4

- AAREK — PRODUCER_INVOCATION_VERIFIED
- OH50 — PRODUCER_INVOCATION_VERIFIED
- Formation Innovation — FOUNDRY_CYCLE_RECEIPT_VERIFIED
- Alpha-Omega — LOCAL_BUILD_RECEIPT_VERIFIED when implementation is required
- Alpha-Omega TEST — not verified
- provider DEPLOY — not verified
- provider VERIFY/readback — not verified
- OPERATE — not verified
- F130 terminal completion — not verified

If Formation says implementation is not required, Alpha-Omega remains NOT_REQUIRED and
no build receipt may be smuggled into the terminal chain.

## Anti-substitution

V4 fails closed when:

- required implementation has no local-build receipt;
- the packet was changed after receipt creation;
- packet/build-plan identity differs;
- any expected artifact is missing;
- any current artifact hash differs;
- the local engine receipt attempts to claim provider deployment or provider readback.

## ProofOS topology

V4 registers the existing Turnkey local-build files as an explicit upstream subsystem:

`FUSE_ALPHA_OMEGA_TURNKEY_LOCAL_BUILD_V1`

FRCB v4 depends on:

- FUSE_RUNTIME_CONVERGENCE_BINDING_V3
- FUSE_ALPHA_OMEGA_TURNKEY_LOCAL_BUILD_V1
- FUSE_OF50_ACE_V1
- FEDERATION_CORE

Therefore changes to the actual AlphaOmegaEngine, its models, OF50 adapter or FRCB
lifecycle adapter impact the V4 convergence court. The V4 court is GLOBAL blocking.

## Truth boundary

V4 can prove local BUILD execution and current local artifact readback within the
calling execution environment. It does not prove independent remote attestation,
provider deployment, provider execution, semantic readback, live operation,
F130 terminal commit, native ChatGPT serving-stack interception or whole-mission
COMPLETE_VERIFIED.

## Next convergence tranche

V5 should bind capability activation/execution-plane admission using existing FDOF/RAEFI
or equivalent admitted capability surfaces. V6 then binds actual provider-native
execution and semantic readback from Bubbles/SOVARA. Source, local build and CI must
remain insufficient for provider-runtime truth.

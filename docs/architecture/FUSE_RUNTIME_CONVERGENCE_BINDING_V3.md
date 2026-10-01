# FUSE Runtime Convergence Binding v3 — FRCB-003

Status: SOURCE CANDIDATE / STACKED ON FRCB-002 / A1_INTERNAL / NO EXTERNAL EFFECTS

## Mission

FRCB v3 advances one additional maturity boundary: Formation Innovation is promoted
only when the exact EvidenceOps FoundryCycleResult receipt is verified and is the
foundry reference carried by the FormationDecision consumed by OF50.

V3 does not create or replace the EvidenceOps foundry.

## Reused mechanisms

V3 reuses:

- EvidenceOps FoundryCycleResult and its deterministic receipt SHA-256;
- the EvidenceOps registry, learning and algorithm-evolution chain verification
  already summarized into the foundry proof;
- the existing EvidenceOps Formation-to-OF50 adapter;
- FRCB v2 for AAREK + OH50 convergence;
- OF50 for downstream completion governance.

The Formation OF50 adapter is tightened so an actual foundry result binds
`receipt_sha256` in preference to the human-readable `cycle_id`. Mappings that do
not contain a receipt SHA retain the cycle-id fallback for compatibility.

## Promotion requirements

A Formation stage can become `FOUNDRY_CYCLE_RECEIPT_VERIFIED` only when:

1. the foundry cycle status is exactly `PASSED`;
2. `PASSED_WITH_HELD_GATES` is rejected;
3. authority remains `A1_INTERNAL`;
4. external effect remains false;
5. the foundry proof SHA-256 recomputes;
6. the registry receipt chain is `PASSED`;
7. the Federation learning chain is `PASSED`;
8. the algorithm-evolution chain is `PASSED`;
9. the FormationDecision carries the exact foundry receipt SHA-256.

A shared cycle identifier is not sufficient. Two foundry results with the same
`cycle_id` but different bodies have different receipt hashes and cannot substitute
for one another.

## Important identity boundary

FoundryCycleResult does not currently contain a native `mission_id`. V3 therefore
does not claim that the foundry receipt independently attests mission identity.

V3 proves:

- exact foundry-cycle body integrity;
- internal foundry proof-chain integrity;
- exact digest attachment to the FormationDecision;
- FormationDecision mission/authority consistency through the existing OF50/FRCB
  chain.

The receipt explicitly records that native foundry mission identity is not proven.

## Stage maturity after v3

- AAREK — PRODUCER_INVOCATION_VERIFIED
- OH50 — PRODUCER_INVOCATION_VERIFIED
- Formation Innovation — FOUNDRY_CYCLE_RECEIPT_VERIFIED
- Alpha-Omega — STRUCTURALLY_BOUND or NOT_REQUIRED
- provider runtime — not verified
- F130 terminal completion — not verified

## ProofOS topology

The V3 subsystem depends on:

- FUSE_RUNTIME_CONVERGENCE_BINDING_V2
- EVIDENCEOPS
- FUSE_OF50_ACE_V1
- FEDERATION_CORE

The V3 court is a GLOBAL blocker. Changes to the V2 convergence layer, the
EvidenceOps foundry, or the Formation OF50 adapter must select the V3 court.

## Truth boundary

V3 does not prove independent external cryptographic attestation, Alpha-Omega runtime
execution, provider execution, provider semantic readback, F130 terminal commit,
native ChatGPT serving-stack interception, or whole-mission COMPLETE_VERIFIED.

## Next convergence tranche

V4 should bind Alpha-Omega lifecycle evidence. A BuildPlan or AlphaOmegaPacket alone
must remain structural; V4 should promote only lifecycle stages backed by actual
BUILD/TEST/DEPLOY/VERIFY evidence while preserving rollback and semantic-readback
requirements.

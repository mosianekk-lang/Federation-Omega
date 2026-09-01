# BCO-Prime × Modisa × SOL 6.1 Cognitive Binding v1

Status: IMPLEMENTED_ON_REVIEW_BRANCH / CI_PENDING  
Date: 2026-09-01

## Purpose

Bind three already-existing systems without collapsing their authority:

1. **BCO-Prime** observes, challenges, ranks and proposes.
2. **Modisa** validates mission identity, source/authority/proof boundaries, continuity and hold state.
3. **SOL 6.1** provides durable event-sourced commit, receipt-backed completion, checkpointing and the only provider-admission route used after this binding.

The binding is intentionally **NO_EFFECT**. It never dispatches a provider action.

## Control flow

```text
Mission + evidence
    ↓
BCO-Prime strategy tournament / PrimeDecisionIR
    ↓
Modisa compact-kernel gate
    ├─ objective hash
    ├─ doctrine invariant integrity
    ├─ authority boundary
    ├─ proof requirements
    ├─ owner hold
    └─ provider-runtime hold
    ↓
SOL 6.1 durable workstream
    ├─ BCO_PRIME_DECISION receipt
    ├─ MODISA_GATE receipt
    ├─ SOL61_INTERNAL_COMMIT receipt
    ├─ completion contract
    └─ checkpoint
```

A fully admitted internal binding reaches `VERIFIED` only after all three receipt types exist.
Owner/provider holds remain `PARTIALLY_VERIFIED`; no missing commit is fabricated.

## Why the dependency is asymmetric

SOL 6.1 remains independently operable. The SOL runtime does **not** import BCO-Prime,
Modisa, or this binding module.

The adapter imports the three owners and composes them externally:

```text
BCO-Prime ─┐
           ├─> triad adapter ─> SOL 6.1 event/receipt API
Modisa ────┘
```

This avoids turning intelligence into execution authority or making SOL dependent on the
availability of the advisory systems.

## Fail-closed invariants

The adapter refuses or holds when:

- the BCO observation objective hash differs from the SOL mission objective;
- the Modisa compact kernel loses a required invariant or stage;
- a BCO decision claims direct dispatch authority;
- a BCO decision claims external-effect authority;
- owner approval is required;
- provider runtime is required but unavailable;
- an existing SOL mission conflicts with the requested objective or success definition.

## External effects

This binding never executes them.

A future external action must independently pass normal SOL 6.1 provider capability
registration/admission and must return provider-native readback. BCO-Prime and Modisa may
recommend or gate the action, but neither can manufacture SOL/provider authority.

## Idempotency

The workstream ID is derived from mission identity and the deterministic BCO decision
receipt. Re-running an already verified binding returns the existing verified binding
without appending new events.

## Files

- `benchmarking/cfbe_omega/bco_modisa_sol61_binding_v1.py`
- `benchmarking/cfbe_omega/BCO_MODISA_SOL61_BINDING_V1.json`
- `tests/test_bco_modisa_sol61_binding_v1.py`
- `governance/proofos_omega_policy_extension_bco_modisa_sol61_binding_v1.json`

## Promotion boundary

This change proves only the deterministic internal binding logic after its tests pass.

It does **not** prove:

- external/provider execution;
- background autonomy;
- stable BCO self-promotion;
- estate-wide Modisa enforcement;
- production superiority.

Those remain separately evidence-gated.

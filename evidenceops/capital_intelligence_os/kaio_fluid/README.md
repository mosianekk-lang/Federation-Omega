# KAIO Ω Fluid Intelligence Core

This package is the first executable implementation slice of the KAIO Ω Fluid Intelligence Roadmap.
It reuses the Federation Alpha→Omega turnkey build contract and the EvidenceOps Formation Innovation / Algorithm Foundry rather than creating a parallel foundry.

## Scope implemented

- P0-02 cognitive data model: evidence state, hypotheses, problem context, reasoning plans.
- P0-04 novelty scoring.
- P0-05 abstraction-oriented reasoning budget inputs.
- P0-06 multi-frame reframing.
- P0-07 competing hypothesis generation.
- P0-08 information-gain prioritization.
- P0-09 constraint/assumption challenge primitives.
- P0-11 Cognitive Compiler v0.1.
- P0-12 prediction/calibration ledger foundation.
- P0-13 Cognitive Immune MVP.
- P0-14 Synthetic Problem Laboratory baseline.

P0-01 constitutional tests are represented by deterministic invariants in the test suite; the full cross-Federation constitutional suite remains a promotion gate rather than a claimed completed runtime deployment.

## Non-negotiable boundaries

- authority ceiling: `A1_INTERNAL`;
- external effect: `false`;
- hypothesis generation never changes proof state;
- repeated/derivative evidence does not become independent corroboration;
- no provider/runtime success claim without provider readback;
- no self-granted authority expansion;
- no source evidence mutation;
- no Verified Facts Register mutation;
- owner-governed promotion remains required.

## Cognitive compile contract

Input:

`OBJECTIVE + STAKES + UNCERTAINTY + NOVELTY + IRREVERSIBILITY + EVIDENCE + CONSTRAINTS + ASSUMPTIONS`

Output:

`MODE + TEMPORARY SPECIALISTS + COGNITIVE PRIMITIVES + VERIFICATION DEPTH + SIMULATION DEPTH + STOPPING THRESHOLD`

Modes:

`REFLEX | ANALYTICAL | INVESTIGATIVE | ADVERSARIAL | DISCOVERY | DEEP_SYNTHESIS`

## Promotion ladder

`DESIGN_ONLY → DETERMINISTIC_TESTED → SHADOW_VALIDATED → CANARY_VALIDATED → WORKFLOW_VERIFIED → OPERATIONAL_VERIFIED`

No stage may be skipped by assertion.

## Deterministic validation

```bash
python -m pytest -q tests/test_kaio_fluid_core.py
```

## 24-hour compression strategy

The 24-hour target is handled by parallelizing only independent lanes:

1. cognitive kernel + tests;
2. Formation Innovation registration;
3. Alpha→Omega build/deploy specification;
4. Federation governance and readback bindings;
5. shadow/canary evidence generation where an executable runtime is available.

Provider/runtime promotion is not conflated with source implementation. Unavailable provider evidence is recorded as a bounded dependency while all independent build lanes continue.

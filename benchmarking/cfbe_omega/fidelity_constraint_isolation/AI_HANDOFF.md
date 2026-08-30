# AI Handoff

## Purpose

Continue the CFBE-Ω fidelity-isolation work without collapsing canonical fidelity, route readiness, source admission, deployment, or readback proof into one state.

## First reads

1. `contract_v1.json`
2. `FORMATION_SPEC.md`
3. `core.py`
4. `tests/test_cfbe_fidelity_constraint_isolation.py`
5. `evidenceops/caseforge/capability_decision.py`
6. `federation_consolidation/provider_constraint_resolver.py`

## Verification

```bash
python -m unittest -v tests.test_cfbe_fidelity_constraint_isolation
python -m compileall -q benchmarking/cfbe_omega/fidelity_constraint_isolation
```

Then run the repository anti-dilution, ProofOS, and regression gates required by `AGENTS.md` before admission.

## Change rule

Changes must be additive or preserve every protected invariant. Do not relax evidence rungs, raw-content exclusion, atomic output, `NOT_EXECUTED`, authority/cost/effect limits, or stable build-trigger behavior. Any platform-specific mutation belongs behind the existing provider resolver and a fresh governed permit.

# EvidenceOps Capital Intelligence OS — Genesis

This package is the first executable vertical slice of the EvidenceOps Capital Intelligence OS. It composes existing Federation/EvidenceOps doctrine with new deterministic capital-domain primitives instead of creating another disconnected control plane.

## Implemented in v0.1.0

- `ProofGraph`: provenance-bound claims, contradiction detection and dependency impact propagation.
- `AuthorityGuard`: fail-closed private-M&A/public-market information firewall and A1 internal authority ceiling.
- `Autopilot`: event → evidence → contradiction → impact → attention → authority → learning loop.
- `GravityEngine`: transparent cross-option capital allocation ranking.
- `DealLifecycle`: 60-stage M&A lifecycle vocabulary plus prerequisite gates for consequential stages.
- `LearningLedger`: append-only hash-linked learning events for runtime use; generated receipts are not written into canonical source.
- `MaturityGovernor`: blocks false promotion from code/test state to deployed/production state.
- Six Genesis algorithms: Epistemic Shock Index, Trust Decay Clock, Attention Compression, Decision Reversal Threshold, Counterfactual Capital Regret and Fragility Cascade.
- `CapitalIntelligenceService`: provider-neutral application facade.

## Constitutional boundaries

The initial release is intentionally A1 internal. It denies live orders, withdrawals, transfers, autonomous financial effects, evidence deletion and attempts to disable information barriers. Consequential external actions are human-gated. Private, clean-team, potentially-MNPI, restricted, privileged and unknown information cannot flow from private M&A into public-market/trading pathways.

Public information may flow into private M&A analysis when otherwise lawful and licensed.

## Maturity truth

Source code is not deployment. Local tests can establish `TESTED`; repository CI and independent readback can support `VERIFIED`; `DEPLOYED` additionally requires a target-runtime receipt, health, persistence and rollback proof. `PRODUCTION_VERIFIED` additionally requires the required security review.

## Acceptance harness

```bash
PYTHONPATH=. python -m unittest discover -s evidenceops/capital_intelligence_os/tests -v
PYTHONPATH=. python -m evidenceops.capital_intelligence_os.verify_release
python -m compileall -q evidenceops/capital_intelligence_os
```

## Federation reuse

The production integration route composes rather than duplicates existing EvidenceOps Algorithm Foundry, Provenance Passport, Secure Capability Box, capability heartbeat, AO-CRA, Formation Engine and Alpha-to-Omega controls. Provider adapters remain replaceable.

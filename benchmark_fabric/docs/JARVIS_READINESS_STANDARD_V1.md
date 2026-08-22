# JARVIS Operational Readiness Standard v1

The canonical target for every critical JARVIS/Federation capability is **R6 — CONTINUOUSLY_ASSURED**. R4 is the minimum state for a bounded provider pilot and R5 is the minimum state for controlled production use. R6 is required for the enduring system.

| Level | State | Promotion proof |
|---:|---|---|
| R0 | Unverified | No acceptable proof yet |
| R1 | Defined | Definition and accountable owner |
| R2 | Implemented | Reviewed source or configuration |
| R3 | Tested | Automated success, failure and exact-head CI receipts |
| R4 | Provider-bound | Real identity, semantic canary and provider readback |
| R5 | Production-proven | Controlled release, live SLO and rollback/restore |
| R6 | Continuously assured | Monitoring, continuous evaluation, fresh benchmark evidence and incident learning |

## Release law

Readiness is never an average. Each release profile takes the minimum effective state of its critical components. A missing secret binding, invalid identity, failed provider canary, absent rollback, unmanaged SLO breach or missing cost guardrail therefore blocks the profile even when code and CI are strong.

Promotion is monotonic only while its evidence remains current. Active failure events and stale provider/live evidence apply deterministic demotion before a release decision. Automated discovery may propose changes to comparator sources, but it cannot promote JARVIS evidence or rewrite reviewed targets.

## Three separate benchmark views

1. **Frontier control alignment** compares 52 public controls with the Microsoft/Alphabet/SoftBank/standards frontier envelope.
2. **Architecture and capability alignment** compares the private 20-dimension CFBE model.
3. **Operational readiness** assigns an ordinal R0–R6 state to each release profile.

These views have different units, scopes and evidence populations. Combining or averaging them is invalid and is rejected by the readiness engine.

## Current strict profile result (22 August 2026)

- Benchmark operations: **R2**, bottlenecked by the not-yet-machine-enforced canonical score contract.
- JARVIS provider runtime: **R0**, bottlenecked by unverified Secret Manager and cost/capacity controls.
- Full Federation operating system: **R0**, with the same provider gaps plus an unbound optional OpenAI provider route.

This strict result is intentionally lower than a narrative maturity estimate: it prevents stronger components from concealing any critical zero-state dependency.

## Machine execution

```bash
python -m benchmark_fabric.readiness \
  --standard benchmark_fabric/catalog/readiness_standard.json \
  --assessment benchmark_fabric/evidence/readiness_assessment_2026-08-22.json \
  --output /tmp/jarvis-readiness
```

The report returns separate score views, effective component states, release-profile bottlenecks and a deterministic promotion backlog. It has no provider mutation authority.

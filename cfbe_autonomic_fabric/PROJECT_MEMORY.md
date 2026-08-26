# Project memory

## Canonical objective

Create the smallest production foundation that continuously represents the
Federation estate, compiles owner intent, selects the strongest admissible
capability route, requires matching proof, detects drift and creates actionable
blockers.

## Current state

- Architecture: implemented locally.
- Provider-neutral source: implemented locally.
- Adversarial verification: 44 local tests pass, including fake/replayed permit,
  concurrent effect, ambiguous outcome, forged proof, tamper, secret, blocker,
  mission supersession/stop race, cross-contract lease, timestamp, signed-restore,
  signed-checkpoint rollback, auto-reseal, cross-store substitution and anchor
  redirect and post-tamper legitimate-write attacks.
- External provider execution: not inherited.
- Durable autonomous runtime: not proven.
- Canonical baseline observed during design: CFBE raw 71.6667 and
  proof-adjusted 50, explicitly not production certification.

## Reuse lineage

The design extends patterns already present in Federation-Omega: capability
heartbeat, capability twin, provider recovery, immutable receipts, idempotency,
fencing and proof-state separation.

## Next proof gates

Build-contract validation, public leak scan, reversible source publication,
hosted checks, production Formation/JARVIS/Sentinel identity binding, connector
semantic canaries, deployment of the rollback-resistant anchor service, recovery
exercise and measured soak.

# MCE v2 / SOE Omega v1 — Autonomic Mission Convergence + Strategic Objective Ecology

## Purpose

This release is the additive evolution path above Mission Convergence Engine (MCE) v1.

MCE v1 remains the deterministic closure kernel. The new layers do not replace it:

1. **AMCF — Autonomic Mission Convergence Fabric** chooses the strongest proof-directed path inside a mission.
2. **SOE Omega — Strategic Objective Ecology** chooses which missions should exist, which should be merged or held, which shared capabilities deserve investment, and how bounded resources should be allocated across the mission population.

The architecture preserves proof-before-claim, surface-local authority, exact readback, rollback, and owner control over consequential objectives.

## Evolution ladder

```text
MCE v1
  deterministic mission closure kernel
      |
      v
AMCF v1
  proof-directed scheduling
  monotonic closure gate
  counterfactual planner
  failure horizon
  mission genomes
  authority-isolated swarms
      |
      v
SOE Omega v1
  mission genesis
  portfolio allocator
  capability centrality
  mission deduplication
  strategic genomes
  estate-wide objective ecology
```

## AMCF core algorithms

### Proof-Directed Scheduler

Candidate actions are ranked by a bounded closure utility:

```text
score =
  closure_leverage
  * information_gain
  * success_probability
  * reversibility
  * (1 + log(1 + unlock_count))
  /
  ((1 + cost) * (1 + risk) * (1 + latency))
```

Shared-state operations are serialized by `shared_state_key`. External effects and actions above the fabric's authority ceiling are held rather than silently executed.

### Monotonic Closure Gate

An action is admissible only when the projected mission-state vector produces measurable progress and no regression across:

- verified closure;
- information;
- safety;
- recoverability;
- unlock leverage.

A no-op is rejected. A regression is rejected. The gate is deterministic and does not self-certify provider execution.

### Counterfactual Planner

Alternative routes are compared across expected closure gain, information gain, safety, recoverability, unlock leverage, option value, evidence strength, success probability, cost, risk and latency.

### Failure Horizon

Failure forecasts combine probability, impact, precursor confidence, prevention leverage and lead time. High-priority forecasts become preemption candidates before the failure occurs.

### Mission Genome

Each mission can be represented as a reusable pattern:

```text
objective class
+ invariants
+ proof axes
+ required capabilities
+ failure fingerprints
+ recovery routes
```

Genomes are matched by weighted semantic/structural similarity. Reuse is advisory and never transfers authority.

### Mission Swarm

A mission can be decomposed into seven scoped cells:

- Builder
- Falsifier
- Evidence
- Route
- Sentinel
- Recovery
- Witness

The Witness and Falsifier are explicitly independent. No cell can self-certify. No authority is inherited between cells.

## SOE Omega core algorithms

### Mission Genesis

Evidence-bound GAP, OPPORTUNITY, RISK, DEPENDENCY and CAPABILITY signals can be converted into mission proposals. Proposals requiring external effects remain owner/effect gated.

### Strategic Utility

Mission candidates receive a bounded strategic utility using outcome value, unlock leverage, probability of success, learning value, reusability, cost, risk and latency.

### Capability Centrality

The ecology measures shared capability pressure across all missions. A capability demanded by many high-value missions receives a higher build priority, allowing the system to prefer one enabling capability build over repeated local repairs.

### Portfolio Allocator

Missions compete for a declared `ResourceEnvelope`. The allocator is dependency-aware, authority-aware, external-effect-aware, capacity-bounded, deterministic and explainable.

It uses a utility-per-scarce-resource frontier rather than pretending to solve an unbounded enterprise optimization exactly.

### Mission Deduplication

High-overlap mission intent is detected using semantic objective similarity plus required and produced capabilities. The system produces merge suggestions; it does not delete history.

### Strategic Genome

Verified historical mission sequences can be registered with measured realized value and reliability. The ecology recommends similar patterns for future portfolios without transferring proof or authority.

## Authority model

The public-safe implementation recognizes four ceilings:

- `A0_OBSERVE`
- `A1_INTERNAL`
- `A2_BOUNDED_EFFECT`
- `A3_CONSEQUENTIAL`

AMCF and SOE Omega default to `A1_INTERNAL`. External effects are held unless a downstream execution layer has separate authority and readback proof. Consequential owner intent cannot be silently rewritten.

## Maturity and proof boundary

This release can prove only source-level algorithm behavior until admission completes.

It does **not** prove provider deployment, credentials or authentication, browser/native-host installation, Google Apps Script execution, external communications, financial effects, current-chat capture, resilience/soak, or Fully Established maturity.

Those states require their own provider-native/runtime receipts.

## High-scale operating model

At scale the intended loop is:

```text
owner strategic intent
  -> strategic objective graph
  -> mission population
  -> capability pressure + resource market
  -> selected mission frontier
  -> AMCF/MCE mission execution
  -> independent closure witness
  -> measured outcomes
  -> mission genome + strategic genome
  -> next ecology cycle
```

The governing optimization principle is:

> Do not merely continue work. Recompute the shortest independently provable path to the owner objective while preserving authority, evidence and rollback boundaries.

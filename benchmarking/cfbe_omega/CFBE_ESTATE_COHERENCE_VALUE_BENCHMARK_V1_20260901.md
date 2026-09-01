# CFBE Estate Coherence + Owner-Value Benchmark v1 — 2026-09-01

## Decision

The sweep-derived operating order is correct and should become the default estate-management path:

**COHERENCE FIRST -> OWNER VALUE SECOND -> NEW CAPABILITY ONLY FOR A MEASURED GAP**

This is an internal evidence-based CFBE benchmark, not an external market certification.

## Why this operating model wins

The Federation already has high source velocity, broad orchestration, proof gates, event/state primitives and substantial capability coverage. The limiting factor is no longer absence of code. It is the lag between source changes and canonical projections, stale change-set entropy, and insufficient measured owner-value evidence.

The optimal response is therefore not another meta-system. It is a bounded reconciliation controller that composes existing capabilities and continuously drives the estate toward a fresh, low-entropy, value-proven state.

## Leader-pattern harvest

| Leader / standard | Harvested pattern | Federation application |
|---|---|---|
| Kubernetes | level-based desired/observed-state reconciliation | keep reconciling current-state projections until observed state matches fresh source truth |
| Argo CD | self-heal, retry limit, backoff, visible drift | repair stale projections automatically without hiding failed convergence |
| Backstage | catalog ownership, lifecycle and discoverability | attach explicit owner/lifecycle/replacement state to every canonical surface and eliminate orphan/current-label ambiguity |
| Temporal | durable checkpoints, replay-safe workflow progress | generation-fenced reconciliation that resumes without replaying uncertain effects |
| GitHub | latest-base validation and merge-queue safety | restack/retest unique stale work; close duplicate/superseded PRs instead of accumulating branch entropy |
| DORA | speed and stability measured together | optimize time-to-current, repair latency, failure rate and burden rather than raw feature output |
| SLSA | verifiable provenance | bind closure receipts to exact source/input identities and deterministic receipt hashes |
| OpenFeature | before/after/error/finally lifecycle hooks | separate preflight, plan, failure classification and final receipt semantics |

Reference documentation used for the benchmark:
- https://kubernetes.io/docs/concepts/architecture/controller/
- https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/
- https://backstage.io/docs/features/software-catalog/
- https://docs.temporal.io/
- https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- https://dora.dev/guides/dora-metrics/
- https://slsa.dev/spec/v1.2/provenance
- https://openfeature.dev/specification/sections/hooks/

## CFBE scorecard

Scoring scale: 0 absent, 1 weak, 2 partial, 3 useful, 4 strong, 5 target-grade design coverage.

| Dimension | Sweep baseline | Target | Key upgrade |
|---|---:|---:|---|
| Desired-state reconciliation | 2 | 5 | one level-based reconcile loop across current-state surfaces |
| Freshness / as-of semantics | 3 | 5 | TTL + present-tense fresh-read requirement + generation fencing |
| Self-heal / bounded retry | 3 | 5 | visible drift + bounded recovery rather than silent stale state |
| Catalog ownership / lifecycle | 3 | 5 | CURRENT / DRIFTED / STALE / HISTORICAL / SUPERSEDED / UNKNOWN |
| Durable replay safety | 4 | 5 | checkpoint/generation semantics and deterministic receipts |
| Current-head change safety | 2 | 5 | restack/retest against current main |
| PR entropy / supersession | 1 | 5 | automatic KEEP / RESTACK / CLOSE / HOLD disposition |
| Supply-chain provenance | 4 | 5 | exact source/input receipt binding |
| Owner-burden measurement | 2 | 5 | reuse observable-burden court and matched observations |
| Strict owner-value gate | 2 | 5 | reuse owner-value deployment court; feature count cannot promote |
| Cognitive-load minimization | 2 | 5 | owner cognitive burden becomes a first-class optimization cost |
| Anti-bloat / no-new-system discipline | 4 | 5 | REUSE -> EXTEND -> SPECIALISE -> MERGE -> NEW LAST |

**Baseline design coverage: 32/60 = 53.33%.**

**Target design coverage after this bounded controller: 60/60 = 100%.**

The target score describes design coverage only. Live automated Drive/KDV propagation, PR cleanup, and owner-value proof remain empirical execution gates.

## Reuse audit

No new scheduler, memory store, provider executor, proof plane, Bible authority, owner-value court or stable-promotion controller is justified.

The implementation reuses:
- Bubbles work-graph, durability, freshness and anti-stall primitives;
- CFBE benchmark/champion-challenger logic;
- Kim Dataverse current-state and bitemporal projection model;
- existing owner-value and observable-burden courts;
- existing SLSA/GitHub attestation route;
- existing source/current-head Airlock and ProofOS discipline;
- existing Failure-Win / RealityGuard fail-closed recovery principles.

## New bounded control added

`benchmarking/cfbe_omega/estate_coherence_value_closure_v1.py` adds only the missing composition layer:

1. classify canonical surfaces against fresh current source;
2. reconcile DRIFTED / STALE / UNKNOWN projections;
3. preserve HISTORICAL evidence instead of rewriting it;
4. mark SUPERSEDED surfaces explicitly;
5. classify open PRs as KEEP / RESTACK / CLOSE / HOLD;
6. enforce REUSE-first capability admission;
7. block new top-level systems without a real gap and strict owner-value proof;
8. emit deterministic source-bound closure receipts;
9. expose coherence/value metrics without granting provider authority.

## High-leverage harvested controls

The controller captures the following advanced controls without creating extra architecture:

- level-triggered reconciliation instead of edge-triggered one-shot updates;
- generation fencing to reject stale/replayed reconciliation attempts;
- TTL-based freshness leases;
- bitemporal-safe historical preservation;
- supersession without deletion of provenance;
- stale-base PR restack routing;
- semantic-duplicate PR closure;
- provider/effect-gated PR HOLD state;
- exact source identity on closure receipts;
- deterministic receipt hashing;
- fail-closed unknown-state handling;
- partial-failure isolation;
- bounded retry doctrine;
- owner/value evidence separated from source novelty;
- machine-observable burden below strict owner-value proof;
- cognitive load as an explicit cost;
- anti-bloat capability decision hierarchy;
- no proof/authority/maturity inheritance;
- present-tense claims require current source readback;
- source velocity and canonical-state velocity measured separately.

## Promotion rule

A capability is not preferred because it is newer, larger, more complex or more autonomous.

Preferred promotion requires:
1. a real measured gap;
2. insufficient existing capability coverage;
3. a measurable owner-value hypothesis;
4. proof that reuse/extension/composition is insufficient;
5. strict owner-value evidence before a genuinely new top-level system can become canonical.

## Truth boundary

This benchmark and controller do not themselves:
- update Google Drive/KDV automatically;
- close or merge PRs;
- grant provider or IAM authority;
- prove owner value;
- authorize stable promotion;
- prove market superiority.

Those outcomes require live provider/source readback and the existing authority/proof gates.

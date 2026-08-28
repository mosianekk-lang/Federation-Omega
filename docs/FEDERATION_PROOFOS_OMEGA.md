# Federation ProofOS Ω — Evidence-Directed Software Admission Fabric

## Objective

Replace the monolithic Federation Omega Airlock regression sequence with a proof operating system that preserves the hard admission kernel while compiling the minimum sufficient proof set for each change.

ProofOS is additive to GitHub/source governance. It does **not** create GitHub branch protection, rulesets, provider authority, remote execution, remote cache, deployment authority, or external effects.

## Formation result

The route tournament rejected four weaker endpoints:

1. remove the Airlock — loses valuable source/provenance/authority controls;
2. keep the full suite on every PR — preserves coverage but creates unrelated blocking and excessive coupling;
3. static thin-Airlock mappings only — improves speed but will drift as the repository evolves;
4. predictive-only test selection — can silently under-test hidden dependencies.

The selected architecture combines a deterministic dependency/risk floor, empirical historical associations, add-only future prediction, explicit omission proof, fail-safe unknown-path fallback, content-addressed proof identity, and CFBE promotion gates.

## Architecture

```text
GitHub PR / merge group
        |
        v
P0 AIRLOCK KERNEL
  ancestry / provenance / leak / authority / workflow policy
        |
        v
CHANGE IMPACT COMPILER
  paths + subsystem graph + risk + historical failure associations
        |
        v
HASH-BOUND PROOF MANIFEST
  selected tests + reasons
  omitted tests + reasons
  policy / graph / base / head identity
        |
        v
MANIFEST-SELECTED COURTS
  subsystem / ABI / security / export / Federation / SOVARA / JARVIS / CFBE
        |
        v
ADMISSION RECEIPT
```

## Hard invariants

- authority ceiling remains `A1_INTERNAL`;
- external effect remains `false`;
- unknown production paths activate the full Federation fallback suite;
- a predictive selector may add tests but may never remove the deterministic floor;
- every registered proof is either selected with reasons or omitted with reasons;
- P0 security/provenance/source-integrity proofs are always blocking;
- no arbitrary shell commands are admitted as proof definitions;
- selected test targets are validated before execution;
- source changes do not become provider-live claims;
- cached proof may be reused only under exact content/policy/environment identity;
- failed proof is never cached as success;
- selector sentinel failures become `SELECTOR_ESCAPE` evidence.

## Current-main guard preservation

ProofOS does not discard recently admitted controls merely because they no longer run as fixed workflow steps. The policy explicitly registers the current EvidenceOps Algorithm Foundry action-proof regression, Architron action-specific semantic contract, SOVARA provider-recovery court, and Frontier Convergence OS v1 court. Matching changes select those tests deterministically.

This specifically prevents a repeat of the failure mode where a new guard is lost during CI simplification.

## Risk tiers

- `R0_DOCS` — documentation only;
- `R1_ISOLATED` — mapped isolated implementation;
- `R2_SHARED` — shared library/runtime;
- `R3_SECURITY_ABI` — security, workflow authority, authentication, ABI or semantic-readback boundary;
- `R4_CORE` — Federation/ProofOS/JARVIS/Formation shared core;
- `R5_RELEASE` — build/release/deployment boundary.

Risk only increases proof depth; it never grants authority.

## Omission Proof Obligation

The distinctive control is not just selecting tests, but accounting for tests that were *not* selected. Each manifest partitions the registered proof universe into:

`SELECTED ∪ OMITTED = ALL_REGISTERED_PROOFS`

with no overlap. Omitted proofs carry reasons such as no dependency path, no risk floor, no historical association and not selected as a sentinel. This makes under-testing auditable instead of invisible.

## Content-addressed proof

A proof key binds the manifest identity, ProofOS policy, test ID/kind/target, hashes of changed source that exists in the checkout, hashes of selected test source and the runtime identity. A local cache is implemented as the first deterministic contract; no persistent/remote CAS is claimed until a provider-backed store and independent readback are proven.

## Failure isolation

The manifest gives each proof a failure class and block scope. Current v1 still blocks the PR for `GLOBAL` and `SUBSYSTEM` failures because GitHub exposes one required admission result. The classification is preserved so later orchestration can isolate unrelated lanes without weakening security/provenance invariants.

## CFBE benchmark

`benchmarking/cfbe_omega/proofos_admission_spec_v1.json` benchmarks the challenger against the incumbent on latency, CI compute, unrelated-test execution, false blocking, security/regression escape, selector false negatives, critical invariant coverage, omission attribution, cache hit ratio, owner intervention and mean time to root cause.

The 10x target is operational, not rhetorical: major speed/compute/false-block reductions are accepted only if security and regression escape are no worse than the incumbent, critical invariant coverage is 100%, omission attribution is 100%, and selector false negatives stay within the hard threshold.

CFBE evidence factors remain truth-bound. Source/design proof cannot become `TEN_X_FRONTIER_CANDIDATE`; that state requires provider-live independent readback and proof references.

## Market-frontier harvest

The design intentionally combines publicly evidenced patterns from protected admission/merge queues, affected dependency graphs, predictive test selection, content-addressed/hermetic build systems, dynamic CI, policy-as-code, supply-chain provenance and build observability. The differentiating Federation layer is the combination of omission proof, selector falsification, risk-adaptive proof depth, proof economics and CFBE evidence-adjusted promotion.

## Maturity path

`SOURCE_IMPLEMENTED → DETERMINISTIC_TESTED → SHADOW_SELECTOR_CALIBRATED → MERGE_GROUP_VERIFIED → REMOTE_CAS_BOUND → REMOTE_EXECUTION_BOUND → OPERATIONAL_METRICS_VERIFIED → CFBE_FRONTIER_CANDIDATE`

No stage is inherited from source existence.

## Next evolution after v1 admission

1. shadow full-suite calibration and selector-escape learning;
2. persistent content-addressed store with provider readback;
3. hermetic remote execution workers;
4. merge-group speculative proof reuse;
5. add-only predictive selector driven by empirical marginal information gain;
6. flake court that can quarantine ordinary noise but never security/provenance invariants;
7. SLSA/Sigstore-style artifact/proof attestations;
8. proof-graph observability and root-cause UI;
9. provider-native branch/ruleset activation and exact readback.

These remain future gates until separately implemented and proven.

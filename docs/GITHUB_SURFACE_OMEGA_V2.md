# Federation Omega GitHub Surface v2

## Purpose

GitHub Surface v2 strengthens the existing Federation Omega GitHub Control Plane. It is not a new sovereign system. Human-First, SOVARA, FDOF, ProofOS, Airlock and existing Federation controls retain their authority.

The objective is a smaller, harder, faster and more intelligent GitHub surface: provider prevention before mutation, least-privilege workflow and agent execution, exact-current proof, strong software-supply-chain provenance, change-aware proof selection and aggressive convergence of stale source lanes.

## Market-frontier benchmark harvested 2026-09-05

The design was compared against current primary documentation and implementation patterns from GitHub, GitLab, Azure DevOps, Harness, Buildkite, SLSA and OpenSSF Scorecard.

### GitHub genes

- repository rulesets and pull-request/status-check enforcement;
- code-scanning merge protection where provider/account support exists;
- artifact attestations and reusable-workflow SLSA provenance;
- custom Copilot agents with explicit tool lists and MCP declarations;
- Copilot hooks capable of pre-tool allow/deny decisions;
- merge-group semantics where provider/account topology supports merge queues.

### GitLab genes

- explicit agent tool governance;
- composite human + service identity for agent-originated activity;
- security-review reasoning over business-logic changes;
- security policy injection before ordinary pipeline execution.

### Azure DevOps genes

- protected-resource branch controls;
- build validation, status checks and policy-gated branch admission.

### Harness genes

- OPA policy-as-code applied to pipeline/service/security entities;
- auditable scorecards that can block promotion below a required control threshold;
- reusable remote templates rather than duplicated delivery logic.

### Buildkite genes

- dynamic/change-aware pipeline generation;
- workload routing and test fan-out;
- OIDC trust constrained by pipeline/job/branch/commit identity;
- signed pipeline decisions for sensitive execution.

### SLSA / OpenSSF genes

- signed build provenance and artifact/SBOM attestation;
- branch protection, dangerous-workflow detection, code review, pinned dependencies and token-permission minimisation as first-class supply-chain controls.

## Current Federation implementation

GitHub Surface v2 extends `tools/github_control_plane.py` and `governance/github_control_plane_policy.json`.

Changed GitHub control surfaces now fail closed on:

- scheduled GitHub workflow execution unless explicitly registered;
- `pull_request_target` unless explicitly registered, with OIDC always prohibited there;
- `workflow_run` consumers with repository-write or OIDC authority;
- `id-token: write` unless the exact workflow is registered;
- OIDC-capable workflows without concurrency isolation;
- mutable third-party Action references instead of immutable commit SHAs;
- `permissions: write-all`;
- missing explicit top-level workflow permissions;
- checkout with persisted credentials;
- unregistered repository mutation commands;
- custom Copilot agents with omitted/wildcard tool grants;
- privileged agent edit/execute/subagent tools without explicit registration;
- automatic/background repository-agent invocation under the owner foreground-only policy;
- unregistered MCP-bearing agent profiles;
- unregistered Copilot hook files.

Every run also emits a derived GitHub estate scorecard. The score is deliberately narrow: it measures source/control-plane coverage only. It is not provider protection, runtime maturity, security certification or owner-value proof.

## Federation GitHub Guardian

`.github/agents/federation-github-guardian.agent.md` is a deliberately constrained GitHub Copilot profile:

- read/search/GitHub inspection only;
- no edit or arbitrary execution tool;
- no automatic invocation;
- no MCP expansion;
- no merge, approval, settings, provider, secret or schedule authority;
- currentness/proof-aware recommendations only.

This harvest uses agent technology as an assurance multiplier rather than creating another autonomous authority plane.

## Provider protection target

The existing canonical provider ruleset remains `governance/federation_omega_main_airlock.ruleset.json`. Provider activation is still a separate gate and must not be inferred from source presence.

Required target state remains:

- direct main updates prevented by GitHub before mutation;
- force push and deletion prevented;
- pull request required;
- exact admission/contract/scan checks required;
- source signature and review-thread controls retained;
- provider-native readback and a negative direct-update canary required for closure.

For this user-owned public repository, GitHub merge queue is not treated as an executable provider target because current GitHub availability requires an organization-owned public repository or eligible organization private repository. FDOF plus exact-head/current-main revalidation remain the source-concurrency control unless repository ownership/topology changes.

## Supply-chain target

Release-class Federation artifacts should converge to:

1. deterministic build input identity;
2. SBOM generation;
3. GitHub artifact attestation;
4. SLSA v1 Build Level 3 provenance through a vetted reusable build workflow where applicable;
5. `gh attestation verify` or equivalent provider-native verification before release promotion;
6. exact artifact digest bound into Federation proof/custody receipts.

This document registers the target only. No provider attestation is claimed until a real artifact is built, attested and independently verified.

## Performance model

The fastest GitHub surface is not the one with the most workflows. It is the one with the smallest trusted execution kernel.

Target architecture:

`change -> impact map -> smallest ProofOS court -> exact-head Airlock -> provider prevention -> attested release -> runtime/provider readback`

The estate should progressively remove duplicate cron workflows, privileged OIDC paths, historical PR lanes and duplicated workflow implementations. Reusable workflows and existing ProofOS/FDOF primitives should replace repeated bespoke control logic.

## Truth boundary

This source tranche proves only implementation and, after CI, deterministic admission behavior. It does not itself activate GitHub rulesets, remove legacy schedules from current main, attest a real release artifact, enable code-scanning merge protection, change WIF/IAM, merge the candidate, deploy a provider runtime, or prove 2x owner-value improvement.

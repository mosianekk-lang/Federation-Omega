# Omega Completion Engine

Status: PROD FOUNDATION / TESTED LOCAL

The Omega Completion Engine is a governed, provider-neutral work-processing system for decomposing a mission into dependency-aware work, allocating independent work to bounded parallel lanes, joining results deterministically, and closing only when the required proof exists.

This repository slice is locally implemented and tested, but it is not deployed, live-provider-authorized, CFBE-GOLD, soaked, or owner-value proven. Local deterministic proof does not transfer to external-provider or production behavior.

## Reconcile, do not rebuild

The engine composes existing Federation assets:

| Source | Reused responsibility | Proof ceiling in this build |
| --- | --- | --- |
| Formation Reconciliation Fabric v2 | Desired-versus-observed reconciliation, adaptive topology, proof-directed waves, policy holds, replay and challenger roles | Source implementation from current Federation lineage; no external authority inherited |
| SOL 6.1 | Durable event state, worker leases, fencing, queue recovery, provider route scoring, circuit breaking, receipts and checkpoints | Reconciled through the local work engine; deterministic integration tests and demo passed |
| Omega-One PR #843 | Contiguous maturity compiler, zero-dilution Universal Capability Contracts and MCP/A2A/OpenTelemetry projections | Open draft branch candidate; not current-main or production authority |
| Omega-One telemetry | Secret-safe events, W3C-style trace correlation, hash-chained audit records and metrics | Locally integrated and included in the 68-test court; external observability proof pending |

No component inherits provider credentials, deployment state, value proof, or authority merely because its source is present.

## Core operating model

The root orchestrator owns the mission and the fan-out/fan-in boundary:

1. Normalize the request into one versioned mission and terminal proof contract.
2. Compile a dependency graph with explicit read/write sets, effect class, authority, privacy and cost ceilings.
3. Apply hard vetoes before utility scoring.
4. Select the smallest useful deterministic, sequential, parallel or hybrid wave.
5. Run independent work in branch-isolated lanes.
6. Join all required predecessors at a barrier.
7. Send material claims through an independent falsifier or witness.
8. Serialize every shared write and every external effect through one effect gateway.
9. Require provider-native readback for provider claims.
10. Checkpoint, learn and stop when the mission proof contract is satisfied.

Parallelism is bounded work allocation, not uncontrolled agent multiplication. Logical roles do not prove simultaneous provider-backed inference.

## Transactional persistence

`OmegaCompletionEngine` now uses `omega_one.transaction_store.SQLiteStateStore` by default:

- SQLite WAL with `synchronous=FULL`, explicit `BEGIN IMMEDIATE`, schema versioning and optimistic revision fencing;
- one row per control record plus append-only hash-chained control events, so commits update only changed records rather than rewriting the complete control snapshot;
- transactionally unique idempotency reservations shared by engine instances on the same host;
- schema v2 admission and dispatch-transition outboxes: each admission or multi-lease wave shares one atomic control revision with its durable intent;
- idempotent SOL/worker materialization after commit, including restart and partial-wave recovery when interruption occurs between the control commit and inherited sidecar publication;
- topology-aware `concurrency_plan()` and `schedule_wave()` APIs that cap width by the READY frontier and spare eligible worker capacity, suppress empty control commits and keep effectful work outside multi-item waves;
- deterministic, hash-bound import of a legacy `control-state.json` without modifying or deleting the source;
- online SQLite backup with integrity and semantic restoration courts.

This is same-host transactional proof, not a multi-host consensus or leader-election claim. The inherited SOL worker and runtime sources remain byte-for-byte preserved.

## Provider harvest

### OpenAI / ChatGPT

- Harvest: root-owned delegation, bounded specialist fan-out, result return to the parent, tool isolation and task-specific context.
- Engine rule: the OpenAI adapter may recommend a default concurrency of 3, but the root scheduler may reduce it to 1 or hold it entirely.
- Non-transferable: ChatGPT UI intelligence levels, hidden provider routing, internal context management and platform-specific agent lifecycle.
- Current state: a default-deny provider descriptor/adapter layer is locally implemented and tested; live OpenAI execution remains unauthorized and unverified.

### Gemini / Google

- Harvest: deterministic workflow outer shells, isolated parallel branches, explicit join barriers, typed task/result envelopes, checkpoints and trajectory evaluation.
- Engine rule: parallel branches never share mutable state implicitly. Every branch produces an output or a typed terminal failure before the join.
- Default hold: managed agents and A2A remain disabled until capability flags, version compatibility, authority, privacy, cost and preview-risk gates pass.
- Current state: a documentation-verified, default-disabled Gemini descriptor is locally implemented and tested; no Gemini invocation occurred.

### Microsoft Copilot

- Harvest: thin front-door orchestration, domain specialists, explicit agent descriptions, deterministic flows, permission-aware tools, environment separation and parent/child telemetry.
- Engine rule: Copilot semantic routing is not treated as load balancing. Maker-credential autonomous triggers are prohibited.
- Default hold: preview connected-agent, autonomous-trigger and approval features remain unavailable unless independently admitted.
- Current state: a documentation-verified, default-disabled Copilot descriptor is locally implemented and tested; no Copilot runtime binding occurred.

## Non-negotiable boundaries

- Authority: default A1 internal planning. External effects require an exact current permit and provider authority.
- Privacy: minimum necessary context, branch-isolated payloads, redacted telemetry and no secret values in events or artifacts.
- Cost: zero-new-recurring-cost by default. Unknown incremental cost fails closed.
- Proof: designed, implemented, tested, admitted, deployed, provider-executed, semantically verified, repeated, soaked and value-verified remain separate.
- Effects: one serialized effect gateway. Independent read or analysis lanes may run in parallel.
- Delivery: remote work is at-least-once with idempotency and outcome reconciliation. The engine makes no provider-neutral exactly-once claim.
- Admission: duplicate or conflicting idempotency keys are rejected before mission, SOL, worker or control-plane mutation; integrity verification reconciles task and worker identities.
- Cancellation: a newer mission version or stop request cancels queued descendants, prevents new leases and fences stale completions.
- Recovery: checkpoints, lease expiry, dead-letter state and readback reconciliation govern resume.

## Local command surface

The distribution name is omega-completion-engine. It requires Python 3.11 or newer.

The implemented local interface is:

    python3 -m venv .venv
    .venv/bin/python -m pip install -e .
    .venv/bin/python -m unittest discover -s tests -v
    .venv/bin/omega-completion --help
    .venv/bin/omega-completion demo --state-dir .omega-demo

The entry point is:

    omega-completion = omega_one.cli:main

`omega_one/cli.py` and `omega_one/__main__.py` are present. The deterministic local demo completed a three-task, two-read-plus-join mission with all three tasks `PROVEN`, `integrity=true`, `source_verified=true`, `provider_execution=false`, and `deployed=false`.

## Local demo acceptance

The deterministic local demo exercises the following contract:

1. create a no-effect mission;
2. decompose it into independent and dependent work;
3. cap the selected parallel wave;
4. show at least one branch-isolated fan-out and one join;
5. checkpoint the mission;
6. exercise cancellation or lease recovery;
7. emit redacted correlated telemetry;
8. produce a proof report that remains below deployment/provider/value maturity.

The verified run did not call a paid model, resolve credentials, deploy, publish, send or mutate an external provider.

## Verification

Foundation validation:

    python3 /root/.codex/skills/remote-skills/validate-modisa-build-contracts/scripts/validate_build_contract.py BUILD_CONTRACT.json

Integrated tests:

    python3 -m unittest discover -s tests -v

Observed result: 72/72 PASS. `python3 -m compileall` also passed and all 13 inherited source Git-blob hashes matched. New failure-first courts cover schema-1 migration, atomic wave intent, post-commit crash, partial materialization replay, cross-instance duplicate-dispatch prevention and the H2-P five-boundary harness contract.

The H1 transactional actual-engine CFBE exercised the identical eight paired workloads through 240 tasks and the identical 16 adversarial invariants. All 16 invariants passed with zero safety-critical failures; measured three-stream speedup ranged from 1.134x to 2.648x, median 1.303x, with quality preserved in every pair. Deep-DAG moved from 0.958x to 1.134x and independent-240 from 0.964x to 1.174x. Fairness remained exactly 6:12:24 with Jain index 1.0. The persistence court still measures a 41.08x reduction in logical serialized changed payload (97.57%) across 122 single-item observations; that is not physical I/O or an elapsed-time speed claim. Release remains `SHADOW_ONLY` because live-provider, multi-host, hidden-suite, soak and real-media proof are absent. Canonical report self-hash: `45b1b997f562338013ea068e5dfd060675fed0626621f74077e5b9ee8f756a98`; file SHA-256: `86c5b52dba307ec05fc1a56bbafbf0b5a549a7b2fd19fabd0291760173e923aa`.

The H2-P process-kill canary then paired an identical 100-mission/160-task sequential baseline with a 100-mission/160-task five-way parallel candidate across all five required crash boundaries. Both routes recovered 100/100 missions with five verified `SIGKILL` terminations, zero provider calls and zero external effects. Candidate elapsed time was 2.6098887359985383 seconds versus 6.023659981001401 seconds, a measured 2.3080140919098455x speedup; the linear 10,000-mission projection was 260.98887359985383 seconds and is not soak proof. Full H2 remains held because the proof-completion boundary replayed two proof receipts, so `proof_receipts_exactly_once` and the aggregate quality gate failed. Canonical H2-P report hash: `c1763d501388cd8ff8d533fda6730875d1550995caf463c18f9c2a36a29f9726`.

The separate deterministic simulator remains simulation only: seven modeled faults, 2.275x simulated speedup, score 99.93984, no hard vetoes and `SHADOW_ONLY`.

Proof-required contract validation is intentionally a later gate:

    python3 /root/.codex/skills/remote-skills/validate-modisa-build-contracts/scripts/validate_build_contract.py BUILD_CONTRACT.json --require-proof

Do not run the proof-required command as a promotion ceremony. It should pass only after integrated tests, semantic verification and defect closure are recorded truthfully.

## Current provenance

- Federation-Omega main observed on 30 August 2026: commit 4f29813935a71f3d2fd344cf9075cfe4184a7e40; 3,137 non-truncated tree entries.
- Main was provider-reported as unprotected with required-check enforcement disabled at observation time.
- Omega-One PR #843: open draft and unmerged, head b1ccae6833410899ca07aada218a6b585d3c9f5e, 28 commits ahead and 8 behind current main; three exact-head hosted checks passed.
- PR #843 explicitly describes itself as branch-only, non-effect and non-promotable until its remaining gates pass.

Fresh provider state always supersedes this record.

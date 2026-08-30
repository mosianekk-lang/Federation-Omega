# AI Handoff — Omega Completion Engine

## Mission

Continue the Omega Completion Engine as a reconcile-not-rebuild integration over Formation Reconciliation Fabric v2, SOL 6.1 and the branch-only Omega-One PR #843 candidate.

Do not create a fourth orchestration framework.

## Required read order

1. BUILD_CONTRACT.json
2. PROJECT_MEMORY.md
3. ARCHITECTURE.md
4. README_ENGINE.md
5. SOURCE_BASE.json
6. current source under omega_one and sol_61_runtime
7. current tests
8. fresh Federation-Omega main and PR #843 state

Fresh provider state supersedes every recorded SHA and status below.

## Provenance at handoff

- Main commit: 4f29813935a71f3d2fd344cf9075cfe4184a7e40
- Main tree: 3,137 non-truncated entries
- Main required-check enforcement: observed disabled
- PR #843: open draft
- PR head: b1ccae6833410899ca07aada218a6b585d3c9f5e
- PR divergence: 28 commits ahead / 8 behind current main; three exact-head hosted checks passed
- PR candidate: Omega-One v0.8.5 proof maturity compiler and standards interoperability spine
- PR boundary: branch-only, non-effect, not current-main, not production

## Frozen architecture decisions

- One root-owned fan-out/fan-in orchestrator.
- Deterministic workflow outer shell.
- Branch-isolated parallel reads and computation.
- One serialized shared-write/effect path.
- Hard authority, privacy and cost vetoes before scoring.
- Remote delivery is at-least-once with idempotency, fencing and reconciliation.
- No provider-neutral exactly-once claim.
- OpenAI adapter advisory concurrency defaults to 3 and may be reduced.
- Gemini parallel branches require explicit joins/checkpoints; managed agents and A2A are disabled by default.
- Copilot semantic routing is not load balancing.
- Copilot maker-credential autonomous triggers are prohibited.
- Every provider capability is versioned, maturity-gated and disabled until current proof exists.
- Completion follows a contiguous proof chain; detached later evidence is preserved but cannot promote.

## Current workspace implementation

Exact inherited source retained and Git-blob verified:

- omega_one/maturity.py
- omega_one/interop.py
- omega_one/portfolio.py
- omega_one/promotion.py
- omega_one/proof_harvest.py
- omega_one/schema_adapter.py
- omega_one/telemetry.py
- sol_61_runtime/runtime.py
- sol_61_runtime/worker.py
- sol_61_runtime/coordinator.py
- sol_61_runtime/adaptive.py
- sol_61_runtime/provider_bridge.py

Local fan-in source:

- omega_one/work_engine.py
- omega_one/transaction_store.py
- omega_one/provider_adapters.py
- omega_one/source_proof.py
- omega_one/cfbe.py
- omega_one/cli.py
- omega_one/__main__.py
- tests/test_work_engine.py
- tests/test_transaction_store.py
- tests/test_cli.py
- tests/test_provider_adapters.py
- tests/test_source_proof.py
- tests/test_cfbe.py

All 13 inherited source files remained Git-blob verified after fan-in. Re-run the bounded inventory and hashes after any source change.

## Implemented local command contract

Distribution:

    omega-completion-engine

Runtime:

    Python >= 3.11

Entry point:

    omega-completion = omega_one.cli:main

Tests:

    python3 -m unittest discover -s tests -v

Local deterministic demo:

    omega-completion demo --state-dir .omega-demo

Observed local evidence: 72/72 integrated unittests passed; compileall passed; all 13 inherited source hashes matched; 16/16 identical actual-engine invariants passed; schema-v2 migration, one-revision multi-lease waves, post-commit crash, partial sidecar replay and cross-instance duplicate-dispatch courts passed; fairness remained Jain 1.0. H1 CFBE measured eight quality-preserving P3/P1 ratios from 1.134x to 2.648x, median 1.303x. H2-P recovered 100/100 candidate missions across five verified process kills and measured 2.3080140919098455x versus the identical baseline, but the proof-completion boundary replayed two proof receipts. Provider execution and deployment remain false.

## Next proof and admission sequence

1. Preserve the passing H1 baseline, exact inherited-source hashes, canonical H1 report and canonical H2-P failure evidence.
2. Repair only proof finalization: atomically persist deterministic proof-publication intent and completion state, make SOL receipt materialization replay-idempotent, and add a crash court that proves zero duplicate receipts.
3. Rerun the identical H2-P paired canary; admit the 10,000-mission H2 retry only when every quality gate passes.
4. Run the admitted H2 forced-process-interruption soak across admission commit, dispatch-wave commit, transition claim, partial sidecar materialization and proof completion, with bounded-WAL/RSS and exact recovery courts.
5. Add multi-host datastore, leader-election and lease/fencing proof; do not project same-host SQLite evidence across that boundary.
6. Implement live-provider clients only behind current capability, identity, privacy, cost and authority gates.
7. Obtain provider-native semantic readback before crediting provider execution.
8. Enforce the repository required-check ruleset before promotion.
9. Run repeated and soak courts; retain `SHADOW_ONLY` until their evidence exists.
10. Admit a deployment target only through a separate Formation permit, canary and rollback contract.
11. Do not call the local score CFBE-GOLD or a real-world throughput gain.

## Required test court

At minimum prove:

- dependency-aware fan-out and join;
- parallel width cap;
- no parallel overlapping writer;
- weighted fairness and no starvation;
- provider saturation and quota hold;
- unknown cost hold;
- authority and privacy denial before provider dispatch;
- OpenAI advisory concurrency cannot override the root cap;
- Gemini preview/A2A disabled by default;
- Copilot maker-credential trigger rejected;
- cancellation cascades and late results are fenced;
- expired lease recovery;
- idempotent exact retry;
- duplicate and conflicting idempotency admission rejected before either state plane mutates;
- control and worker planes reconciled by integrity verification;
- uncertain provider outcome is reconciled before retry;
- redaction and telemetry correlation;
- tamper detection for durable audit events;
- completion denied with a missing proof predecessor;
- CLI deterministic demo completes with no provider call.

## Proof rules

Never collapse:

- file present into implemented behavior;
- unit test into integrated behavior;
- CI into deployment;
- deployment into provider execution;
- provider response into semantic success;
- one success into reliability;
- reliability into owner value;
- agent profile into a running agent;
- provider catalogue into current availability;
- permit into provider authority.

Current integrated product states in BUILD_CONTRACT.json are authoritative for this workspace handoff.

The current ceiling is `TESTED_LOCAL`: implemented=true and tested=true, while ready, registered, authorized, deployed and proven remain false.

## Provider adapter admission

Every provider adapter must expose:

- provider and observed model/version;
- capability and modality;
- identity class and authority state;
- privacy/retention classification;
- unit cost or UNKNOWN;
- quota, concurrency and reset state;
- latency and reliability measurements;
- preview/stability status;
- tool/effect support;
- idempotency/readback/rollback behavior;
- latest verification time and evidence reference.

Unknown or stale fields hold the route.

## Safe stop and recovery

On stop:

- stop issuing leases;
- persist cancellation;
- fence old versions;
- preserve existing proof;
- reconcile in-flight external outcomes;
- checkpoint;
- return no provider-effect success claim without readback.

On restart:

- verify hash chains;
- load checkpoint;
- recover leases;
- inspect dead-letter/outcome-unknown work;
- refresh provider state;
- recompile the ready frontier;
- resume current-version tasks only.

## Handoff completion packet

Return:

- exact source ref;
- files changed;
- tests run and complete output summary;
- build-contract validation result;
- implemented versus pending states;
- provider calls and cost, normally zero during foundation work;
- unresolved defects;
- rollback route;
- next safe executable action.

Do not assign configuration, deployment or monitoring tasks to the owner when an authorized automated route remains.

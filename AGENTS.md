# Federation Omega Agent Governance Contract

This repository is governed by Phoenix Airlock, source provenance, workflow quarantine, public leak detection and proof-before-claim controls.

These instructions apply to every automated coding agent, bot, assistant, local runner and repository-integrated AI operating anywhere in this tree.

## Mandatory source-change route

1. Never commit or push directly to `main`.
2. Create a purpose-specific branch from the current `main` head.
3. Make the minimum source changes required for the stated objective.
4. Open a pull request into `main`.
5. Do not merge unless Airlock admission, source-provenance tests and the public leak guard pass on the exact head.
6. Re-read the merge result before claiming completion.

`[skip ci]`, alternate Git APIs, force pushes, generated commits, bot identities or owner credentials do not create an exception.

## Workflow authority

- Do not create, restore, enable or broaden a GitHub Actions workflow unless the task explicitly requires a governed workflow change.
- New workflows are default-deny.
- Do not grant `contents: write`, `id-token: write`, `actions: write`, `statuses: write`, `packages: write` or other elevated permissions outside the exact Phoenix policy allowlist.
- Do not use mutable action tags. Pin third-party actions to immutable commit SHAs.
- Checkouts must use `persist-credentials: false` unless an approved policy explicitly states otherwise.
- Never add a workflow step that commits, pushes, tags, opens releases or mutates canonical source at runtime.
- Never re-enable a workflow disabled by Phoenix quarantine.

## Runtime and evidence outputs

- Runtime state, diagnostics, canaries, generated reports, receipts, transcriptions, model packages and provider responses must be uploaded as immutable artifacts or stored in the approved external evidence plane.
- Do not commit generated runtime receipts, `*-latest.json` files, trigger files, queue state, heartbeats, snapshots or execution results to canonical source.
- A source file describing a contract is not proof that the contract executed.
- Claims of deployment, ruleset activation, repository creation, credential rotation or provider mutation require exact provider readback.

## Continuous learning and algorithm-trigger capture

- Every material runtime or tool path must emit a terminal `SUCCESS`, `FAILURE` or `CONSTRAINT` event; material corrections and recoveries must emit `CORRECTION` and `RECOVERY` events.
- Material innovation work must also preserve `INNOVATION_CANDIDATE`, `EXPERIMENT_RESULT` and `NEGATIVE_RESULT` events where applicable.
- Learning events must be append-only, hash-linked, evidence-referenced and stored in an immutable artifact or the approved external append-only evidence plane.
- Every failure must preserve the original failure evidence, receive a deterministic classification, select the smallest safe repair, and bind a regression test after successful recovery.
- A repeated failure fingerprint must open the affected circuit and require a materially different route.
- Every success must record proof and measurable value; repeated success may create a route-confidence candidate but must never transfer trust to another workflow.
- Every constraint must update the constraint register and activate the strongest safe fallback route.
- Algorithm-trigger state must be derived from the learning ledger, versioned, reversible and limited to `A1_INTERNAL`.
- Learning or trigger updates must never expand authority, write verified facts, mutate evidence, cross case walls or activate consequential external action.
- Generated learning ledgers and trigger-state artifacts must not be committed to canonical source.
- Corpus growth alone is not intelligence improvement; an improvement claim requires later measurable performance delta.

## Durable n-directive, Formation Engine and Alpha-to-Omega Foundry

- Load and apply `governance/federation_n_directive_v2.yaml` (`FEDOMEGA-N-DIRECTIVE-V2`, version 2.1.0 or later compatible version) whenever the exact input `n` is received or a substantive output is about to close.
- Interpret `n` as: proceed, improve, close the current critical dependency, execute available safe authorised work, invoke the Formation Engine, invoke the Alpha-to-Omega Autonomous Solution Foundry, discover and compose stronger capabilities, form competing solutions, generate a bounded innovation frontier, build, test, read back, repair, learn, assess maturity and begin the next justified advancement without a status-only pause.
- The Formation Engine must preserve objective strength and action-verb integrity, separate objectives from means, map evidence and authority, inspect reusable capabilities, generate competing route families and select the strongest complete safe route.
- The Alpha-to-Omega Foundry must compile the selected route into a solution specification and solution genome, reuse verified capabilities before rebuilding, create the minimum complete deterministic solution, validate it, test failure and rollback, select the strongest authorised execution surface and require independent proof.
- Every non-trivial `n` cycle must generate a bounded innovation frontier containing: the strongest verified reuse route, strongest incremental improvement, strongest materially different solution and highest-information reversible experiment.
- Do not stop at the first viable solution when a materially stronger route can be safely discovered or tested.
- Full power means all relevant capabilities that are actually available, authorised, safe and evidence-matched. It never means invented tools, hidden runtimes, authority expansion, trust transfer or bypass of owner-reserved decisions.
- Safe discovery, evidence mapping, competing solution formation, architecture, simulation, testing, red-team review and learning extraction may run in parallel. Shared-target, provider or external-effect mutations must be serialised.
- Every substantive output must report the Formation Engine result, Alpha-to-Omega result, alternatives considered, reuse-versus-build decision, selected solution, innovation delta, learning delta, proof, maturity, next experiment, complete next-best automated pathway and the explicit reusable line `n = proceed`.
- A new Federation or Master-Bible-governed node must pass `governance/federation_node_bootstrap_v2.json` before substantive work. The bootstrap must inherit the Formation Engine, Alpha-to-Omega Foundry, innovation frontier, terminal learning-event contract, `A1_INTERNAL` ceiling, no-external-effect default and no-trust-transfer rule.
- Current registered nodes inherit the policy through the Master Bible Node Policy Inheritance register and apply it when next activated or synchronized through an authorised route.
- The directive does not create invisible access to closed chats, a hidden background runtime, consequential external authority or trust transfer.
- Omission of either engine, the bounded innovation scan, the complete next-best automated pathway, `n = proceed`, or material learning capture is a fail-closed defect that must be repaired and retested.

## Credentials and external authority

- Never print, persist, upload, email or commit credentials, private keys, tokens or secret values.
- Never request that credentials be pasted into chat or source control.
- Consequential provider mutations require an explicitly authorised, short-lived credential supplied through a trusted local environment.
- Installation-token authority must not be described as user-scoped authority.
- Do not claim access, installation, activation or successful provider mutation without readback evidence.

## Recovery and incident handling

When an unadmitted direct push or unsafe writer is discovered:

1. Preserve the offending commit SHA and evidence.
2. Confirm workflow registry state through provider readback.
3. Disable or quarantine execution through the approved Phoenix controller.
4. Remove unsafe source through a reviewed rollback pull request without rewriting history.
5. Reintroduce legitimate source only through a fresh reviewed pull request.

## Truth boundary

Repository-local controls detect, quarantine and evidence policy violations. They become fully preventative only when GitHub platform rulesets require the Airlock `admission` check before `main` can change.

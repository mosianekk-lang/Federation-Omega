# Bubbles Ω — Autonomic Federation Runtime v1

## Objective

Turn the existing Bubbles/Federation capability estate into one proof-bound mission lifecycle:

`INTENT -> MISSION IR -> AUTHORITY PREFLIGHT -> PROVIDER CELL -> EXECUTION -> SEMANTIC READBACK -> PROOF PASSPORT -> RECOVERY/EVALUATION -> OWNER VALUE`

This is a convergence layer, not a second sovereign architecture.

## Five layers

### 1. Provider Authority Fabric

`bubbles/provider_authority_fabric.py` resolves exact, fresh, mission-bound authority contracts. It does not mint authority. It accepts credential references, never secret values, and can be backed by the existing Secure Capability Box/provider IAM/OAuth surfaces.

An effectful mission stays gated unless provider, connector, action, authority class, mission identity, expiry, semantic readback route and cost ceiling match. Consequential or explicit-owner-approval missions remain approval gated.

### 2. Durable Execution Fabric

`bubbles/autonomic_federation_runtime.py` reuses `formation_omega.durable_mission_runtime_v1.DurableMissionRuntimeV1`. The existing ConvergenceLedger remains event truth, MissionIR remains mission truth, and DurableMissionResultIndex remains result truth.

No new scheduler or memory root is introduced. Durable state does not mean ChatGPT continues executing after a host turn ends.

The runtime compiles five durable work items:

1. `AUTHORITY_PREFLIGHT`
2. `PROVIDER_EXECUTION`
3. `SEMANTIC_READBACK`
4. `PROOF_FINALIZE`
5. `OWNER_VALUE_MEASURE`

### 3. Provider Cell Mesh

`bubbles/provider_cell_mesh.py` treats provider integrations as execution cells rather than sovereign agents. Selection requires current provider-native health, provider-live state, semantic-readback readiness, MissionIR provider policy, effect-class support, latency target and cost ceiling. Effectful routes also require credential binding.

A bounded external effect without an exact resolved authority decision never reaches the executor. A transport-successful effect without semantic readback enters `HOLD_READBACK`; it is not blindly retried.

`CONSEQUENTIAL_EFFECT` is never auto-dispatched by this runtime.

### 4. Proof / Observability / Sentinel Fabric

`bubbles/mission_proof_passport.py` writes additive `BUBBLES_OMEGA_PROOF_EVENT_V1` records into the existing durable mission ledger. It is not another ProofOS or another state store.

Passport stages cover source, authority, provider dispatch, semantic readback, recovery, evaluation, value and final proof. Cost, latency and external-effect counts can be projected from receipts. A proof passport is complete only when required authority is resolved, provider semantic readback is verified, final proof is verified and no `HOLD_READBACK` condition remains.

The existing Omega interoperability/OTEL projection and Operational Closure Spine remain the standards/telemetry bridge. Live collector export and provider trace readback remain empirical gates rather than source claims.

### 5. Owner-Value Optimizer

`bubbles/owner_value_optimizer.py` consumes the existing `OwnerValueMissionRecord` and `OwnerValuePairCompiler` contracts. It never invents missing owner metrics.

No champion decision is made below the configured measured matched-pair floor. The default production target remains a sustained measured cohort, not CI-generated synthetic value.

The current score weights are explicitly local to the owner-value decision contract:

- 45% owner time reduction
- 20% owner intervention reduction
- 25% verified-output-ratio improvement
- 10% elapsed-time improvement

A positive measured cohort may identify Bubbles as the local champion for that cohort. It does not establish global market superiority or grant provider authority.

## Reused owners

This runtime deliberately reuses rather than replaces:

- `federation.mission_ir.MissionIR`
- `formation_omega.durable_mission_runtime_v1.DurableMissionRuntimeV1`
- `formation_omega.mission_convergence.ConvergenceLedger`
- Bubbles multistream continuity / fenced leases / `HOLD_READBACK`
- EvidenceOps Secure Capability Box as the existing effect-boundary foundation
- existing provider workers/adapters/readback contracts
- ProofOS and Omega interop/OTEL projection
- Sentinel owner-value ingress and existing owner-value court
- CFBE for benchmark, champion/challenger and promotion decisions

## Fail-closed states

- `PROVIDER_GATED` — no currently qualified provider cell or exact grant.
- `APPROVAL_REQUIRED` — consequential/explicit-owner-approval boundary.
- `AUTHORITY_GATED` — effectful route lacks exact resolved authority.
- `PROVIDER_DISPATCH_FAILED` — transport/provider-native execution failed.
- `READBACK_REQUIRED` — no-effect/read result has not been semantically confirmed.
- `HOLD_READBACK` — an external effect may have occurred and must be read back before retry or promotion.
- `DATA_GATED` — owner-value cohort is insufficient.

## What source admission does not prove

Even after this runtime is merged and its deterministic courts pass, the following remain separate provider/empirical states until provider-native readback exists:

- Google WIF/IAM activation or modification;
- GitHub repository ruleset/branch-policy administration;
- Apps Script owner-auth execution authority;
- OpenAI/OpenRouter/Gemini funded live inference availability;
- a remotely deployed MCP/runtime endpoint;
- arbitrary external-site browser or desktop computer-use authority;
- live OTEL collector/export/readback;
- positive sustained owner value;
- billing, IAM, deployment, publication, email-send or other consequential effects.

## Provider activation sequence

For each provider capability:

1. compile MissionIR and capability authority contract;
2. discover current provider-cell health;
3. resolve an exact fresh provider-native grant where required;
4. select the best admissible cell under cost/latency/proof policy;
5. execute once with an idempotency key;
6. independently obtain provider-native semantic readback;
7. if effect is uncertain, hold and read back rather than retry;
8. append the proof passport;
9. feed observed failures to Sentinel/Failure-to-Operational-Win;
10. feed genuinely measured matched outcomes to the owner-value court/CFBE.

## Non-negotiable invariants

- provider authority is never inherited from source code;
- secret values are never placed in public source/proof/passport metadata;
- one provider failure does not freeze unrelated safe lanes;
- no stale provider success overrides fresher failure/readback;
- no consequential effect is automatically dispatched by this runtime;
- no effect is promoted without provider-native semantic readback;
- no owner-value claim is inferred from architecture, CI or source coverage;
- Bubbles executes/orchestrates; CFBE selects/evaluates; existing proof and authority owners retain their roles.

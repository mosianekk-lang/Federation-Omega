# CASEFORGE-Ω — EvidenceOps Scientific Benchmark & Evolution Layer

Status: **DETERMINISTIC_TESTED core / blind-runner admitted / OpenAI provider adapter candidate / A1_INTERNAL / no external effect**

CASEFORGE continuously challenges EvidenceOps with blind, diverse and adversarial legal/evidentiary benchmarks. It converts confirmed failures into candidate improvements and delegates promotion to the existing EvidenceOps evolution fabric. It does **not** replace JFRIE, LEX-OMEGA, TruthGrid, the Innovation Engine, Federation Omega governance or primary legal authority.

## Runtime relationship

```text
Kim Dataverse / source systems
        ↓
CASEFORGE blind case corpus
        ↓
SCIENTIA scientific-method controls
        ↓
EvidenceOps + JFRIE + LEX-OMEGA + TruthGrid
        ↓
benchmark scoring + adversarial falsification
        ↓
Federation Formation / Alpha-to-Omega / AO-CRA
        ↓
candidate implementation
        ↓
existing EvidenceOps EvolutionGovernor
        ↓
shadow → canary → limited workflow → promotion
```

## Scientific invariants

1. A hypothesis is not a fact.
2. Material hypotheses require credible competing explanations where genuine alternatives exist.
3. Every promoted hypothesis must be falsifiable.
4. Blind benchmark packs must not contain answer keys or expected outcomes.
5. Correct outcome for the wrong legal/evidentiary reason is a failed benchmark.
6. Fatal integrity failures override numerical performance.
7. Court outcomes are learning evidence, not automatic doctrine.
8. Current law must be revalidated for current external-use legal analysis.
9. Negative results are preserved.
10. Candidate upgrades require independent replication, red-team review, mutation testing, global regression and rollback.

## Federation Omega binding

The capability broker uses only capabilities whose current state is verified enough for the requested role. A subscription, historical connector or architecture record is not treated as live capability. Missing capability is returned as an `AO-CRA:<role>` build request rather than being invented.

The required innovation frontier contains four routes:

- strongest verified reuse;
- strongest incremental improvement;
- strongest materially different solution;
- highest-information reversible experiment.

CASEFORGE intentionally reuses the existing `evidenceops.innovation_engine.evolution.EvolutionGovernor` for final candidate metric evaluation. It does not create a parallel promotion authority.

## Initial benchmark

`CF-UTILITY-ZA-001` is a blind public-utility benchmark inspired by the shared-transformer problem class. It tests:

- infrastructure/distributor identity;
- compliant vs non-compliant party separation;
- shared infrastructure vs individual enforcement;
- payment, technical, safety and logistics counter-hypotheses;
- current authority hierarchy;
- regulator/court route competence;
- uncertainty and provenance discipline.

The blind pack and the scoring-control pack are separate files. Runtime code should provide only the blind pack to the system being evaluated.

## Benchmark score

The initial aggregate score uses:

| Dimension | Weight |
|---|---:|
| Legal route | 15% |
| Evidence integrity | 20% |
| Authority quality | 15% |
| Fact and chronology | 10% |
| Contradiction reasoning | 10% |
| Adversarial resilience | 10% |
| Remedy and procedure | 10% |
| Uncertainty calibration | 5% |
| Traceability | 5% |

A benchmark automatically fails on fatal events such as fabricated authority/fact/quotation, answer-key leakage, material wrong-forum errors, binding-authority omission, remedy-forum mismatch, case-wall contamination or presenting inference as proved fact.

## Federation-wide validation adapters

CASEFORGE exposes a common `FederationEvaluationContract` and three bounded adapters. They share the same A1 internal authority ceiling and may not create external effects.

### ContinuityForge

ContinuityForge tests ChatBridge, heartbeat, Secondary Brain and Kim Dataverse continuity against explicit expected state. It measures context recovery, canonical-state accuracy, provenance fidelity, correction retention, stale-state rejection, route separation and contradiction detection. A corrected or superseded fact reappearing as current state is a permanent failure fingerprint rather than a harmless memory difference.

### CapabilityForge

CapabilityForge evaluates current capability rather than architectural intent. A surface is eligible only when its heartbeat state, freshness, semantic behaviour, readback and authority are verified for the current probe. Stale or adapter-only capabilities are degraded and emit AO-CRA engineering build identifiers. The existing heartbeat `surface_registry.json` is the intended source for provider state and TTL inputs.

### AutoFIX Laboratory

AutoFIX Laboratory stress-tests RESOLVE/AutoFIX recovery traces. It checks preservation of the original failure, deterministic classification, circuit breaking, continuation of unaffected lanes, repair reversibility, state integrity, independent readback and rollback. Repeating an unchanged broken route, losing failure evidence, corrupting state or declaring recovery without readback produces explicit failure fingerprints.

### Common evolution contract

All three adapters report a common structure:

`mission → hypothesis → baseline → metrics → failure fingerprints → red-team state → regression state → proof receipt → maturity`

`federation_validation_evolution.to_evolution_governor_metrics()` maps validated adapter results into the existing EvidenceOps `EvolutionGovernor` metric contract. Reuse, cost efficiency and owner-burden reduction must be supplied as measured values; CASEFORGE does not infer them from technical quality scores.

This enables Federation-wide comparison without creating a second promotion authority.

## Isolated blind-runner contract

`blind_runner.py` provides the deterministic tested-agent/scorer separation required before CASEFORGE may call a legal/evidentiary model run genuinely blind.

The tested agent receives only a detached canonical JSON blind payload and control-free run/model metadata. It does **not** receive the hidden control pack, scoring rubric, expected outcome, answer key, fatal-test list or control path. Reserved control keys—including underscore, hyphenated or camel-style variants—and a hidden-control marker fail closed before execution. A tested agent that mutates its blind input also fails the run.

The hidden scorer separately holds the control pack, binds it by SHA-256, verifies case identity, applies existing CASEFORGE benchmark/fatal-event scoring, and verifies that scoring did not alter the tested output.

A model binding may claim `PROVIDER_VERIFIED` only when a non-empty provider-native readback reference exists. Otherwise the harness remains `DETERMINISTIC_TEST_ONLY`.

This source boundary does not by itself prove process/container isolation or a real OpenAI/Google AI Studio blind run. Those stronger claims require the provider-bound canary and independent receipts tracked under `CF-AOCRA-BLIND-RUNNER-001` / issue #329.

## OpenAI provider adapter candidate

`openai_provider_adapter.py` reuses the repository's existing OpenAI Responses API pattern rather than creating a second provider stack. The tested model receives only canonical blind-case JSON and fixed control-free instructions. Provider tools, prompt references, conversations, previous-response references and any caller override of the model/input/instructions/store fields are rejected before invocation.

A successful provider response creates `ProviderResponseEvidence` containing only non-secret execution metadata and hashes. It is deliberately classified `PROVIDER_EXECUTED_UNREADBACK` unless an independent `ProviderReadbackVerifier` returns matching response ID, provider-returned model and status evidence. Only then may the combined blind receipt be promoted to `PROVIDER_VERIFIED`.

`openai_blind_canary.py` is a callable tested-agent-side canary for an already-authorised runtime. It never loads the hidden scoring/control pack, requires the model ID to be supplied at runtime, defaults to `store=False`, emits no credential values, and leaves scoring to a separate hidden scorer. No workflow is created or enabled by this source candidate, and source existence does not prove an OpenAI model was invoked.

## Maturity

This implementation must move sequentially through:

`DESIGNED → DETERMINISTIC_TESTED → SHADOW_VALIDATED → ADVERSARIALLY_VALIDATED → CANARY_VALIDATED → LIMITED_WORKFLOW_VERIFIED → CROSS_DOMAIN_VERIFIED → OPERATIONAL_VERIFIED`

Source existence is only `DESIGNED` until test evidence proves more. A deterministic isolation harness may reach `DETERMINISTIC_TESTED` after repository regression/Airlock evidence, but provider-bound blind execution requires separate proof.

## No-background-execution boundary

Repository source and ChatGPT conversation state do not create a durable scheduler. Daily/weekly/monthly CASEFORGE runs require a verified external runtime or a supported scheduled-task surface. Provider deployment, Apps Script triggers, Google Cloud services and AI Studio experiments require provider-native readback before their states may be promoted.

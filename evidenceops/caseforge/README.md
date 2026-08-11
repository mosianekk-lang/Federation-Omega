# CASEFORGE-Ω — EvidenceOps Scientific Benchmark & Evolution Layer

Status: **candidate implementation / A1_INTERNAL / no external effect**

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

## Maturity

This implementation must move sequentially through:

`DESIGNED → DETERMINISTIC_TESTED → SHADOW_VALIDATED → ADVERSARIALLY_VALIDATED → CANARY_VALIDATED → LIMITED_WORKFLOW_VERIFIED → CROSS_DOMAIN_VERIFIED → OPERATIONAL_VERIFIED`

Source existence is only `DESIGNED` until test evidence proves more.

## No-background-execution boundary

Repository source and ChatGPT conversation state do not create a durable scheduler. Daily/weekly/monthly CASEFORGE runs require a verified external runtime or a supported scheduled-task surface. Provider deployment, Apps Script triggers, Google Cloud services and AI Studio experiments require provider-native readback before their states may be promoted.

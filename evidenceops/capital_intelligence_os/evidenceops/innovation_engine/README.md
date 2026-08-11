# EvidenceOps Innovation and Algorithm Foundry

A canonical, proof-gated EvidenceOps capability that mines the Master Bible,
Secondary Brain and execution lessons for recurring problems, compiles those
problems into deterministic A0/A1 algorithms, tests them, records learning and
permits only bounded non-regressing parameter evolution.

## Placement

```text
Federation Omega constitutional and learning controls
  -> Formation Engine intent and route formation
  -> Alpha-to-Omega solution genome and foundry
  -> EvidenceOps Innovation and Algorithm Foundry
  -> EvidenceOps / FEVX read-only case-wall adapter
```

The foundry extends the existing `evidenceops/innovation_engine` control surface.
It does not create a second active EvidenceOps foundry. Independent logic is
kept only as a small reference replica for reproducibility tests.

## Canonical algorithm portfolio

1. `ALG-EOPS-AOM-001` — Algorithm Opportunity Miner
2. `ALG-EOPS-DEC-001` — Directive Execution Compiler
3. `ALG-EOPS-CPDG-001` — Claim-Proof Distance Guard
4. `ALG-EOPS-UFP-001` — Unknown Frontier Prioritizer
5. `ALG-EOPS-IGRS-001` — Information-Gain Route Selector
6. `ALG-EOPS-TFR-001` — Terminal Finality Resolver
7. `ALG-EOPS-CSIE-001` — Corpus Selection Integrity Evaluator
8. `ALG-EOPS-CPIG-001` — Control-Plane Integrity Guard
9. `ALG-EOPS-ASPV-001` — Action-Specific Proof Validator
10. `ALG-EOPS-FEGC-001` — Failure-to-Engineering-Gene Compiler
11. `ALG-EOPS-PSTG-001` — Proof-State Transition Guard
12. `ALG-EOPS-EDP-001` — Epistemic Debt Prioritizer
13. `ALG-EOPS-OBRO-001` — Owner-Burden Route Optimizer
14. `ALG-EOPS-CIRE-001` — Cross-Implementation Replication Evaluator
15. `ALG-EOPS-EVG-001` — EvidenceOps Evolution Governor

## Continuous learning and evolution

Each material cycle records a terminal Federation learning event and may add the
semantic subtypes `INNOVATION_CANDIDATE`, `EXPERIMENT_RESULT` and
`NEGATIVE_RESULT`. Rich subtypes remain hash-bound in event details and the
algorithm evolution ledger even when an older Federation learning runtime maps
them to its compatible SUCCESS, FAILURE or CORRECTION classes.

Events are append-only, SHA-256 linked and processed by the Federation learning
policy. Trigger state is derived from the ledger. A repeated failure opens its
circuit and requires a materially different route. A successful recovery binds
a regression control. Negative results remain evidence and may not silently
become doctrine.

The Evolution Governor permits configuration or threshold promotion only when:

- the candidate improves the weighted evaluation score;
- factual accuracy, proof completeness, security and reversibility do not regress;
- no secret-bearing field or authority expansion is introduced;
- the prior version remains available for rollback;
- the evolution ledger and learning ledger both verify.

The governor does not rewrite source code, constitutional authority, case-wall
rules or owner-reserved powers.

## EvidenceOps and FEVX integration

`evidenceops_adapter.py` compiles an authorised case-walled packet into a
conservative read-only foundry cycle. Packet presence is not treated as body
extraction, source verification, independent readback or legal correctness.
Missing records remain controlled finality obligations. Derived output remains
`HELD_FOR_EVIDENCEOPS_REVIEW` and cannot write the Verified Facts Register.

`fevx_bridge.py` exposes the foundry through the existing optional
`algorithm_foundry_runner` boundary in the EvidenceOps-FEVX adapter.

## Reproducibility

`reference_replica.py` is a small independent implementation used only for
R3-style agreement tests. `replication.py` compares release decisions, finality
counts, learning integrity and read-only boundaries. Replication never transfers
trust; divergence is preserved and blocks stronger promotion.

## Operational boundaries

- Authority ceiling: `A1_INTERNAL`.
- External effect: `false`.
- No source evidence mutation.
- No Verified Facts Register write.
- No cross-case trust transfer.
- No external send, filing, payment, publication or destructive action.
- No runtime claim from stored source or local test evidence.
- Runtime ledgers and receipts belong in immutable artifacts or an approved
  external append-only evidence plane, never canonical source.

## Commands

```bash
PYTHONPATH=".:systems/fevx-frontier-v2" \
python -m pytest -q \
  evidenceops/innovation_engine/tests \
  tests/test_evidenceops_algorithm_foundry.py

python -m evidenceops.innovation_engine \
  --policy governance/federation_learning_policy.json \
  canary \
  --signals evidenceops/innovation_engine/fixtures/master_bible_lesson_signals.json \
  --workspace local-artifacts/evidenceops-algorithm-foundry \
  --output local-artifacts/evidenceops-algorithm-foundry/canary.json
```

## Maturity truth

Source implementation and deterministic local tests can prove source and local
algorithm behaviour. Provider-hosted recurrence, real-matter accuracy, legal
correctness and workflow-specific trusted autonomy require separate evidence,
readback and owner-governed promotion.

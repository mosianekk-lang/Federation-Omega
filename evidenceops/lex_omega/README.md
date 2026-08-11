# LEX-OMEGA v1.1 — Legal Authority & Evidentiary Convergence

LEX-OMEGA is an EvidenceOps specialist meta-legal and forensic council. It complements, but never replaces, JFRIE.

## Position in EvidenceOps

```text
EvidenceOps / Master Bible
  -> LEX-OMEGA specialist legal and forensic intelligence
      -> JFRIE jurisdiction/evidence integrity gate
          -> release firewall
```

JFRIE remains fail closed. A LEX-OMEGA opinion cannot override a JFRIE hard-gate failure.

## v1.1 convergence controls

### 1. Legal Proposition Ledger

Every material legal proposition receives a stable fingerprint and is linked to the exact authority records on which it depends. Authority dependants can be enumerated when a statute, rule or judgment is superseded, conflicted or requires revalidation.

### 2. Authority Revalidation Gate

Authority records carry one of:

- `CURRENT_VERIFIED`
- `RECHECK_REQUIRED`
- `SUPERSEDED`
- `CONFLICTED`
- `UNVERIFIED`

A prior verification does not create permanent currentness. Effective dates, verification age and later-treatment checks are explicit inputs.

### 3. Independent Counsel Isolation

The primary analyst, employer-side red team and neutral decision-maker submit independent sealed conclusions. Integration is unavailable until all required roles have submitted. Disagreement is preserved rather than averaged away.

### 4. Claim-Law-Evidence Triangle

A litigation-relevant element is closed only when all three sides exist:

```text
LEGAL PROPOSITION <-> FACTUAL CLAIM <-> PRIMARY / VERIFIED EVIDENCE
```

A missing side blocks an unqualified release recommendation.

### 5. Outcome Learning Without Outcome Bias

A result is classified by what actually happened rather than by win/loss alone:

- `LEGAL_ERROR`
- `EVIDENCE_FAILURE`
- `PROCEDURAL_FAILURE`
- `FACTUAL_FINDING`
- `DISCRETIONARY_OUTCOME`
- `STRATEGIC_FAILURE`
- `STRATEGIC_SUCCESS`

No outcome automatically promotes doctrine.

## Current EvidenceOps mainline alignment — 11 August 2026

LEX-OMEGA now uses `alignment.py` to bind the August 7 convergence controls to the current EvidenceOps mainline without duplicating newer engines.

Current responsibility split:

```text
TruthGrid vNext
  -> evidentiary finality / TruthState / decision readiness

LEX-OMEGA
  -> specialist legal, labour-law and forensic reasoning

JFRIE / EACIA
  -> fail-closed jurisdiction, contamination and release integrity

CASEFORGE-Ω / SCIENTIA
  -> competing hypotheses, falsification, blind benchmarking and governed evolution

CapabilityResolutionGate
  -> proof burden before CAN / CANNOT / DONE terminal claims
```

The engines must remain separate. LEX-OMEGA may consume their results but may not silently reimplement, override or weaken them.

### TruthGrid alignment

Where a workflow requires evidentiary finality, the current `CompletionVector` and `DecisionReadiness` control the claim of readiness. `NOT_READY` blocks unqualified release; `CONDITIONAL` forces limitations; unresolved external production gaps do not become internal completion.

### SCIENTIA alignment

Material hypothesis-driven legal/evidentiary analysis may require competing hypotheses, testable predictions and falsifiers. A preferred theory is not promoted merely because it is plausible or owner-favourable. CASEFORGE remains the benchmark/evolution layer and the existing EvidenceOps EvolutionGovernor remains the promotion authority.

### Capability-resolution alignment

Any system-level statement that an objective **CAN**, **CANNOT** or is **DONE** must pass the current CASEFORGE `CapabilityResolutionGate`. Route failure, invalid arguments, missing authentication or a transient blocker are not objective incapability. `DONE` requires objective-complete state, zero executable internal dependencies and readback proof.

### Blind-evaluation alignment

A deterministic isolated blind-runner is not automatically a provider-verified blind model experiment. Provider-blind claims require `PROVIDER_VERIFIED` execution state and a provider-native readback reference. Otherwise the result remains deterministic-test evidence only.

### Mainline maturity vocabulary

The alignment adapter maps legacy LEX maturity into the richer current CASEFORGE-compatible ladder without silent promotion:

`DESIGNED -> DETERMINISTIC_TESTED -> SHADOW_VALIDATED -> ADVERSARIALLY_VALIDATED -> CANARY_VALIDATED -> LIMITED_WORKFLOW_VERIFIED -> CROSS_DOMAIN_VERIFIED -> OPERATIONAL_VERIFIED`

The legacy enum is retained for compatibility. Extra current-mainline stages are represented in `MainlineMaturityStage` and require their own proof.

## Legacy LEX maturity ladder

LEX-OMEGA's original internal ladder remains preserved for compatibility:

1. `DESIGN_ONLY`
2. `DETERMINISTIC_TESTED`
3. `SHADOW_VALIDATED`
4. `CANARY_VALIDATED`
5. `WORKFLOW_VERIFIED`
6. `OPERATIONAL_VERIFIED`

Promotion must be sequential and evidence referenced. No maturity state may exceed the lowest independently proven level.

## Release behavior

The deterministic council kernel can return:

- `PASS`
- `PASS_WITH_LIMITATIONS`
- `HOLD_FOR_AUTHORITY`
- `HOLD_FOR_SOURCE`
- `REFRAME`
- `SEPARATE_CAUSES`
- `LEGAL_RESEARCH_REQUIRED`
- `DO_NOT_FILE`
- `RESYNC_REQUIRED`

If JFRIE is not in a passing state, LEX-OMEGA fails closed to `DO_NOT_FILE` for filing-ready use.

## Current scope

This package is an internal deterministic control kernel. It does not itself retrieve legal authorities, file documents, send communications, make legal findings, or create external legal authority. Current law must still be verified against primary sources at execution time.

## Continuous evolution

Material corrections, objections, rulings, evidence failures and strategy outcomes may generate candidate improvements. Candidate rules must follow EvidenceOps/Federation learning governance:

```text
OBSERVE -> ROOT_CAUSE -> PROPOSE_RULE -> GENERATE_TEST -> SHADOW -> CANARY -> PROMOTE_OR_REJECT -> PUBLISH -> READBACK
```

LEX-OMEGA may propose JFRIE improvements; it may not silently rewrite JFRIE.

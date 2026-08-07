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

## Maturity ladder

LEX-OMEGA grows inside the EvidenceOps central evolution fabric through sequential proof-gated states:

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

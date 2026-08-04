# EvidenceOps v8.1 — ProofLoop Living Matter Twin

EvidenceOps v8.1 converts the existing bounded P13 control cycle into a case-walled, source-bound and continuously verifiable **living matter digital twin**.

## Verified engineering scope

- proof contract required before execution;
- byte-derived SHA-256 source registration;
- verified facts require registered sources;
- cross-matter writes fail closed;
- verified facts cannot be silently overwritten;
- event-sourced matter state with hash-chain readback;
- hash-chained longitudinal value ledger;
- source freshness, defects prevented, execution time, owner-attention demand and outcome-quality fields;
- consequential actions denied under A0/A1;
- scheduled GitHub Actions cycle and immutable proof artifact;
- no evidence content, credentials or private correspondence is committed to the public repository.

## State model

```text
SOURCE BYTES
→ SOURCE IDENTITY
→ FACT CLASSIFICATION
→ MATTER EVENT
→ CLAIM / ISSUE CONTROL
→ RELEASE GATE
→ VALUE CYCLE
```

## Authority boundary

```text
AUTHORITY: A0/A1 internal and reversible

DENIED:
send · file · serve · publish · settle · admission · hearing recording
financial action · destructive mutation · provider administration
```

The runtime produces preparation, verification and control receipts only. It does not perform external legal effects.

## Run locally

```bash
python -m unittest discover -s runtime/evidenceops_v81/tests -v
python runtime/evidenceops_v81/run_cycle.py run \
  --manifest runtime/evidenceops_v81/config/mpmb1435_26_control_manifest.json \
  --state-dir runtime/evidenceops_v81/state
python runtime/evidenceops_v81/run_cycle.py verify \
  --state-dir runtime/evidenceops_v81/state
```

## Maturity truth

```text
ENGINEERING: COMPLETE_VERIFIED after CI and readback
LONGITUDINAL ASSURANCE: ACTIVE_EVIDENCE_ACCUMULATING
VALUE GATE: NOT_YET_MATURE
CONSEQUENTIAL AUTHORITY: HELD
```

Elapsed longitudinal value cannot be proven by a single run. The scheduled ledger accumulates evidence without promoting itself or expanding authority.

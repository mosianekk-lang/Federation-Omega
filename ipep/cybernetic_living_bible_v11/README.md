# Ω-Cybernetic Living Bible v11 — Deterministic Control Kernel

This package is the first executable, privacy-safe source implementation of the
turn-driven cybernetic controller defined by the Federation Omega Local and
Primary Master Bible records.

## Closed loop

`SENSE → ESTIMATE → COMPARE → DECIDE → ACT → READBACK → LEARN → RESEAL`

The package implements:

- typed signals and state observations;
- homeostatic target comparison;
- seven deterministic reflex families;
- authority-aware action decisions;
- a non-mutating EvidenceOps Audio v4 control adapter;
- hash-bound cycle receipts;
- a privacy-safe synthetic canary;
- tests for truth, authority, evidence and unit-accounting gates.

## Reuse and integration

EvidenceOps Audio v4 remains the controlling audio-evidence plane. This package
does not replace or mutate Audio v4. It consumes a minimal summary snapshot,
checks unit accounting and preserves exact-quotation, bilingual-review and
certification gates.

Competitive Genome v10 remains the champion–challenger and benchmarking
subsystem. v11 adds state estimation, feedback, reflex, prediction, learning
and authority control around that subsystem.

## Run the canary

```bash
python -m omega_cybernetic_v11.cli canary
```

The canary uses synthetic A1-internal data. Generated receipts are runtime
artifacts and must not be committed to canonical source.

## Maturity and truth boundary

Source maturity after a successful local test is `LOCALLY_TESTED_SOURCE`.
A merged pull request proves reviewed canonical source only. It does not prove:

- unattended background execution;
- provider-native deployment;
- hidden or closed-chat access;
- production persistence;
- external benchmarking;
- human listening or bilingual review;
- transcript certification;
- external sending, filing or publishing.

Those states require separate runtime, provider and human receipts.

# Federation ProofOS Ω — Shadow Selector Calibration v1

## Purpose

ProofOS v1.1 adds bounded non-blocking selector falsification over registered proof groups that the deterministic impact selector omitted.

A deterministic 5% sample, capped at two sentinels, is executed only after the blocking manifest-selected court. Expensive full/export courts are excluded from routine sentinel sampling.

## Truth and authority boundary

- authority ceiling remains `A1_INTERNAL`;
- external effect remains `false`;
- a shadow success does not prove selector completeness;
- a shadow failure does not prove a causal dependency;
- a shadow failure becomes `SELECTOR_ESCAPE_CANDIDATE` learning evidence requiring confirmation;
- a sentinel failure does not automatically block the current admission;
- configuration/integrity failure of the calibration machinery itself fails closed;
- P0 security, provenance, authority and source-integrity invariants cannot be demoted to shadow tests.

## Why this is additive

The blocking ProofOS court still decides admission from the deterministic graph/risk/historical floor. Shadow calibration cannot remove any selected proof. It samples only omitted, sentinel-eligible proof groups and therefore acts as an empirical falsifier of omission decisions.

## Next maturity gate

Aggregate independent shadow receipts across real PRs, confirm or reject escape candidates, then use CFBE to measure selector false-negative rate before any claim of calibrated or frontier-leading selection.

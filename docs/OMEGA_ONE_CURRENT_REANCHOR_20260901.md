# Omega-One current-source re-anchor — 2026-09-01

## Purpose

Re-anchor the bounded Omega-One v0.8.6 source lineage from PR #873 onto current Federation main without merging the stale branch wholesale.

## Preserved capability

The re-anchor carries the Omega-One package, local CFBE benchmark and current-compatible deterministic tests. It preserves the 100-capability blueprint, schema-first interoperability, maturity separation, deterministic promotion courts, exactly-once finalization, bounded retry/concurrency, SLO/error-budget controls and local paired-campaign measurement.

## Deliberate exclusions

Legacy PR #873 edits to `frontier_convergence/slos_convergence_runner.py`, `tests/test_frontier_slos_convergence_runner.py` and the old ProofOS implementation are not carried forward. Current SLOS, ProofOS, SOL 6.2 Google-surface and provider-hardening controls remain authoritative.

## Truth boundary

This is source/currentness reconciliation only. It does not prove provider runtime, deployment, external effects, production performance, stable promotion, or owner value. Historical microbenchmark and scenario figures remain historical evidence and cannot substitute for the current CFBE matched courts.

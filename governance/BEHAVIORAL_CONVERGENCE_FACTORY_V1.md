# Behavioral Convergence Factory v1

## Purpose

Behavioral Convergence Factory v1 is the pre-execution triage layer for Failure-to-Operational-Win v2 receiver convergence.

It exists because empirical behavioral maturity can be polluted when admission failures, test-harness defects, synthetic canaries, stale evidence, owner-credential gaps, success-only readbacks, or semantically mismatched provider probes are treated as receiver behavior.

The factory does not replace `BehavioralConvergenceEngine` or `FailureToOperationalWinKernelV2`.

Operating order:

```text
raw event frontier
  -> Behavioral Convergence Factory
  -> only executable same-surface real-event lanes
  -> BehavioralConvergenceEngine
  -> FailureToOperationalWinKernelV2 proof graph
  -> repeated success + soak
  -> receiver-local maturity decision
```

## Fail-closed classes

The factory rejects:

- stale event/proof state;
- non-material events;
- unpreserved failures;
- success-only evidence with no failure antecedent;
- admission/setup-only failures;
- test-harness-only failures;
- synthetic-only events;
- semantic-surface mismatch between failed behavior and recovery target.

It holds rather than executes when:

- current owner/provider authority is not proven;
- a required external effect is not authorized;
- rollback is unavailable;
- independent readback is unavailable;
- semantic-surface binding is incomplete.

## Ranking

Only executable candidates reach Formation AMCF's existing `ProofDirectedScheduler`.

Ranking incorporates closure leverage, information gain, success probability, reversibility, cost, risk, latency, owner burden, and unlock leverage. The receiver id is the scheduler shared-state key, so two candidate recoveries for the same receiver are never selected into one parallel wave.

## Learned regressions captured from 27 August 2026

The regression suite preserves four concrete lessons:

1. Formation's Phoenix standalone-core pytest portability defect qualifies as a real executable recovery lane because the exported core itself failed and the repair targets the same semantic surface.
2. Google Apps Script missing `CLASPRC_JSON` is held at the owner/provider authority boundary; code mutation cannot substitute for a legitimate credential route.
3. JARVIS monkeypatch/test-process contamination is rejected as test-harness-only evidence.
4. Bubbles' disabled legacy provider-authority workflow is rejected as admission/setup evidence and cannot inherit behavioral credit from a later healthy Cloud Run probe.

## Truth boundary

Selection is not proof. A selected candidate does not imply repair success, provider execution, receiver behavior, repeated success, soak, or estate-wide maturity.

Receiver promotion remains governed by empirical failure preservation, causal falsification, materially different route, vector gate, authority/cost, failure-first and healthy-path tests, rollback, forward canary, independent semantic/provider readback, positive value, no regression, no increased owner burden, repeated success and soak.

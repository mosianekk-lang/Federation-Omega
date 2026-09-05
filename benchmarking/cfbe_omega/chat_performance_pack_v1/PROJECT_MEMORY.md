# Project Memory

## Current state

The recoverable current chat is `PARTIAL_CHECKPOINTED`. The measured live-surface baseline was 72.1/100 on 2026-09-03. The 2026-09-04 re-audit scored the current conversation at 67.6/100 after a real stream-safety regression: a broad automation listing produced roughly 69k tokens, and a registry hydration exceeded the bounded output envelope.

The regulator quarantined the incident with rogue score 1.0. A contracted 1,800-token single-route packet then passed with rogue score 0.0006 and `STREAM_RISK_CONTROLLED`.

## Decisions

- Keep the live score separate from this package's local tested-readiness score.
- Do not deploy from this build cycle.
- Make snapshots producer-signed and freshness-bound.
- Make receipt identity `(task_id,generation,slot)` and protect the head with a fence plus compare-and-swap.
- Require directly observed matched canary metrics; projections cannot promote.
- Automatically de-instrument after either terminal promote or hold.

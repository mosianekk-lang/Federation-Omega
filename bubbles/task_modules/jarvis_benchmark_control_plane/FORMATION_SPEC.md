# Formation specification

Mission: `JARVIS-BENCHMARK-KNOWLEDGE-PLANE-20260822`, version 1.

The runtime is `FORMATION_COMPATIBLE`. Local build writes were admitted through single-use A1 permits recorded in `governance/formation_permits.json`. The service itself has one effectful route: `POST /v1/cycle/commit`. That route requires operator configuration plus a bearer token and can only append an idempotent knowledge transaction. Dry-run evaluation, registry status and opportunity ranking remain A0/read-only.

The 50-horizon packet is `governance/foresight_plan.json`. It preserves exactly 50 advisory horizons, one fan-in, one maximum effectful path, no authority expansion and explicit cancellation conditions.

Mandatory stop conditions are stale mission, missing authority, critical stale evidence for current-comparison claims, invalid source identity, ledger corruption, idempotency conflict, stop-switch activation, recurring-cost expansion or user supersession.

The scoring engine routes attention. It never grants execution authority. A recommended opportunity must return through a fresh Formation decision before implementation or provider mutation.

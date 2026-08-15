# Formation specification

Mission: `MISSION-REALITYGUARD-REUSE-BEFORE-BUILD`, version 1. Authority: local A0–A2 only. Cost: zero. External deployment: not authorized.

The default scan and solution routes are deterministic and read-only. One invocation may select one explicit local mutation route: secret-redacted append-only `scan --audit-log`, or atomic idempotent `learn --ledger`. The learning route fingerprints incidents, increments recurrence and refuses self-promotion to `REGISTERED` or `BEHAVIOR_PROVEN`. Owner acceptance remains a distinct evidence grade and cannot be authored by the engine.

Solution order is `ADOPT → ADAPT → COMPOSE/PATCH_EXISTING → BUILD_NEW_ONLY_IF_GAP`. The pre-build gate additionally requires a current, finite, canonical-hash-bound inventory; applies explicit supersession and semantic deduplication; separates lifecycle proof gaps from source capability gaps; and bounds any permitted new component exactly to evidenced residual scope. A truth block may suppress a false status but may not silently suppress the valid owner objective. Federation and Alpha-Omega references provide patterns and provenance only; no live cross-system binding is inferred.

Stop switch: use `scan`, `resolve` or `prebuild` without a log/ledger option for zero writes; terminate the process for immediate stop. No worker, scheduler, daemon, autonomous learning loop or retry loop exists in this foundation build.

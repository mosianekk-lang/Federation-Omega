# Formation Specification — CIOS v0.2

Objective: make Genesis durable, replayable and tenant-scoped while preserving the A1 ceiling and M&A/public-market information barrier.

Selected route: provider-neutral transactional semantics with a SQLite reference adapter. Rejected routes: staying in-memory; premature cloud microservices without provider readback; cross-tenant outcome sharing by default.

New capabilities: tenant context/guard, durable Autopilot, request-bound idempotency, restart/replay, restricted lists, Deal Passport, consented cohort OutcomeNet, ten decision/learning algorithms, and Failure-to-Route genes derived from real implementation failures.

Highest-information reversible experiment: persist evidence/dependencies, restart the runtime, reproduce impact propagation, replay the same event without duplicate effects, and fail closed if an idempotency key is reused for different input.

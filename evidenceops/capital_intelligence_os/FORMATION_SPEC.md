# Formation Specification — CIOS v0.4

Objective: prove the durable core can operate through a real bounded HTTP runtime, survive backup/restore and remain deny-by-default without creating a provider or financial-effect claim.

Routes considered: public internet deployment — rejected for this gate; new GitHub execution workflow — rejected because Airlock reserves product execution for the private operations plane; loopback-only local canary — selected as the highest-information reversible proof.

Defects discovered and converted to regression rules: HTTP headers are case-insensitive and must be normalized; request-bound idempotency requires stable producer event time, so `occurred_at` is mandatory rather than regenerated on retry.

Qualification experiment: start the local HTTP server, authenticate, check health/readiness/release invariants, prove forbidden-route denial, back up state, stop, reopen, and compare state digest.

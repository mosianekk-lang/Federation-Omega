# EvidenceOps Capital Intelligence OS — v0.4 Local Runtime Qualification

v0.4 adds a bounded executable runtime surface on top of the durable market-aware core. It is deliberately a **localhost-only qualification runtime**, not a public or provider production deployment.

Implemented: loopback-only HTTP server; ephemeral bearer-token hashing plus tenant/user context; deny-by-default route policy; `/health`, `/ready`, `/v1/verify`, and idempotent `POST /v1/events`; no trading/payment/transfer/withdrawal/signing/regulatory-file route families; hash-chained audit reference ledger; SQLite backup `quick_check` and restore state-digest proof; stable producer-supplied `occurred_at` for idempotent event ingestion.

Local v0.4 acceptance: **111 tests PASS**, local HTTP canary PASS, release verifier PASS, compile PASS.

Maturity truth: `LOCAL_RUNTIME_VERIFIED` is evidence of a bounded local deployment canary. It is **not** `DEPLOYED` or `PRODUCTION_VERIFIED`. Provider deployment still requires an authorised private execution plane plus provider-native identity, secrets, network, health, persistence, rollback, observability, backup/restore and security evidence.

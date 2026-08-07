# Production Readiness Register — v0.2

| Component | Current truth | Next production proof |
|---|---|---|
| ProofGraph / M&A lifecycle | TESTED | scale/load/schema evolution |
| Authority + restricted list | TESTED | policy integration + external red team |
| Durable Autopilot | TESTED_LOCAL_RUNTIME | provider event/DB + multi-worker idempotency |
| SQLite reference store | TESTED_LOCAL_PERSISTENCE | encrypted HA provider DB + backup/restore |
| Tenant boundaries | TESTED_REFERENCE | authenticated tenant identity + penetration/isolation tests |
| Deal Passport | TESTED_REFERENCE | provenance/attestation adapters where justified |
| OutcomeNet | TESTED_PRIVACY_GATED_REFERENCE | legal/privacy review + leakage attack tests + optional formal DP |
| Decision algorithms | TESTED | calibrated historical/synthetic domain evaluation |
| Network API/UI | DESIGNED | authenticated API/UI, rate/session/audit controls |
| Provider runtime | NOT CLAIMED | runtime/health/persistence/rollback/observability receipt |
| Production security | NOT CLAIMED | threat model, secrets/DLP/SAST/dependency/container/external review |
| Live financial effects | DISABLED | separate regulated authority programme; never inherited |

v0.2 is an executable durable reference core, not a deployed commercial SaaS and not production-verified.

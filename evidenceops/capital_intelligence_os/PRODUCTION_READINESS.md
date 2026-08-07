# Production Readiness Register — v0.4

| Component | Current truth | Next production proof |
|---|---|---|
| Durable/M&A/market core | TESTED_LOCAL_REFERENCE | scale/load/provider adapters |
| Local HTTP runtime | LOCAL_RUNTIME_VERIFIED | private provider runtime + hardened gateway |
| Local auth/context | TESTED_LOCAL_CANARY | enterprise IdP/SSO/MFA/SCIM/service identity |
| Route authority policy | TESTED_DEFAULT_DENY | distributed policy enforcement/red-team |
| Audit chain | TESTED_REFERENCE | immutable provider audit sink/WORM/retention |
| Backup/restore | TESTED_LOCAL_CANARY | scheduled encrypted provider backup + DR exercise |
| Tenant isolation | TESTED_REFERENCE | authenticated identity + penetration/isolation tests |
| Market data adapter | TESTED_REFERENCE | licensed provider entitlements/readback |
| OutcomeNet / Deal Passport | TESTED_REFERENCE | privacy/legal/security qualification |
| Live financial effects | DISABLED | separate regulated authority programme; never inherited |
| Provider deployment | NOT CLAIMED | provider runtime/identity/network/health/persistence/rollback evidence |
| Production security | NOT CLAIMED | threat model, SAST/SCA/container/secrets/DLP/pentest and remediation |

# EvidenceOps eCertify ZA — Production Readiness v0.4

## Implemented source controls
- Legal-lane separation for digital originals, source-matched copies, certified-copy gate, affidavit gate and institution-accepted digital assurance.
- Identity-provider receipts pass server-side provider allowlisting, key-ID validation, signature verification, timestamp freshness and replay protection before identity policy is evaluated.
- Replay/idempotency is now an injected contract: local SQLite is explicitly non-production; PostgreSQL-compatible atomic replay is available through an externally supplied DB-API connection factory.
- Production private API fails startup when provider trust configuration or a distributed replay guard is absent.
- Provider-specific integrations must implement a common capability/evidence contract and cannot require EvidenceOps to retain raw biometric media.
- Public verification is separated from private identity processing and exposes only verification code, status, legal label, document fingerprint and timestamps.
- Isolated private/public container targets and a zero-traffic Cloud Run canary bundle use dedicated `evidenceops-ecertify-za-*` service names and refuse reserved Architron targets.
- Commissioner authority and recipient-acceptance control planes exist in the private Drive workspace.
- POPIA DPIA, legal launch gate, identity-provider RFP and 20-gate go-live register exist in the private control plane.

## Hard production gates — LIVE must not be claimed until all have provider-native proof
1. Select/contract an approved identity-verification provider and bind its provider-native receipt/JWS/mTLS semantics with production test vectors, key rotation/revocation and actual trusted-reference authority proof.
2. Supply the distributed PostgreSQL/managed-store connection factory through the authorised private runtime and prove atomic replay across instances and restarts.
3. Bind managed secrets/KMS and prove identity-provider and database credential rotation without raw credentials entering public source or chat.
4. Complete provider-specific POPIA DPIA and written section 57 prior-authorisation determination; complete authorisation before affected processing if required.
5. Bind encrypted object storage, malware scanning, content validation, DLP/redaction and retention/deletion evidence.
6. Implement Android/iOS platform attestation and hardware-backed device keys for high-risk device activation/recovery.
7. Onboard verified commissioners/certifiers with current authority/capacity/conflict proof; no invented or title-only authority.
8. Sign pilot recipient acceptance rules/agreements; Lane 5 remains unbound until express recipient acceptance is proved.
9. Deploy isolated zero-traffic private/public canaries through an authorised GCP route, prove health, service identity, secrets, distributed persistence and no production traffic.
10. Run independent penetration testing covering signed-receipt forgery/replay, API abuse, document upload attacks, virtual-camera/injection, synthetic-media provider boundary, compromised devices and recovery/social engineering.
11. Prove monitoring/SLOs, incident response, audit export, rollback and backup/restore.
12. Run a closed production-like pilot, then an end-to-end provider-native canary covering citizen identity, document assurance, applicable commissioner event, recipient verification, audit and rollback.
13. Obtain final legal/privacy/Information Officer approval of public wording, consent, terms and data flows.
14. Only after all above gates may a public service be made unauthenticated or promoted to production traffic.

## Current truth
SOURCE_V0_4_PRODUCTION_BOUNDARY_BUILD_IN_GOVERNED_BRANCH. V0_3_IS_MERGED_ON_MAIN. CLOUD_PRODUCTION_DEPLOYMENT_NOT_YET_PROVEN. IDENTITY_PROVIDER_NOT_YET_BOUND. COMMISSIONER_AND_RECIPIENT_NETWORKS_NOT_YET_POPULATED. PUBLIC_LAUNCH_NOT_YET_AUTHORISED.

# EvidenceOps eCertify ZA — Production Readiness v0.5

## Implemented source controls
- Legal-lane separation for digital originals, source-matched copies, certified-copy gate, affidavit gate and institution-accepted digital assurance.
- Identity-provider receipts pass server-side provider allowlisting, key-ID validation, signature verification, timestamp freshness and replay protection before identity policy is evaluated.
- Replay/idempotency is an injected contract: local SQLite is explicitly non-production; PostgreSQL-compatible atomic replay is available through an externally supplied DB-API connection factory.
- Production private API fails startup when provider trust configuration or a distributed replay guard is absent.
- Provider-specific integrations implement a common capability/evidence contract and cannot require EvidenceOps to retain raw biometric media.
- Smile ID now has a reference provider adapter based on its published callback signature and Biometric KYC result contract. The adapter verifies callback HMAC/timestamp, replay state, liveness, ID verification and authority-photo compare; callbacks exposing image links/KYC receipts are treated as a sensitive-media boundary event.
- Identity-provider trust and device trust are now explicitly separate domains. Final bank-grade human verification requires both verified identity proof and an independently trusted device; neither domain inherits trust from the other.
- Public verification remains separated from private identity processing and exposes only verification code, status, legal label, document fingerprint and timestamps.
- Document intake validates file signatures/type/size and cannot progress to accepted storage without separate malware/DLP controls.
- Isolated private/public container targets and a zero-traffic Cloud Run canary bundle use dedicated `evidenceops-ecertify-za-*` service names and refuse reserved Architron targets.
- A dedicated read-only eCertify CI workflow uses immutable pinned actions and runs only eCertify compile, shell-syntax and qualification tests.
- Commissioner authority, recipient acceptance, POPIA/DPIA, provider RFP, section 57 preliminary determination and go-live control planes exist in the private Drive workspace.

## Hard production gates — LIVE must not be claimed until all have provider-native proof
1. Select/contract an approved identity-verification provider and bind its provider-native production semantics with live test vectors, key rotation/revocation and actual trusted-reference authority proof. The Smile ID adapter is reference-ready but remains `UNBOUND_PROVIDER_CONTRACT_AND_PRODUCTION_READBACK`.
2. Supply the distributed PostgreSQL/managed-store connection factory through the authorised private runtime and prove atomic replay across instances and restarts.
3. Bind managed secrets/KMS and prove identity-provider and database credential rotation without raw credentials entering public source or chat.
4. Complete provider-specific POPIA DPIA and written section 57 prior-authorisation determination; complete authorisation before affected processing if required.
5. Bind encrypted object storage, malware scanning, content validation, DLP/redaction and retention/deletion evidence.
6. Bind platform-specific Android/iOS attestation adapters and hardware-backed device keys for high-risk device activation/recovery.
7. Onboard verified commissioners/certifiers with current authority/capacity/conflict proof; no invented or title-only authority.
8. Sign pilot recipient acceptance rules/agreements; Lane 5 remains unbound until express recipient acceptance is proved.
9. Deploy isolated zero-traffic private/public canaries through an authorised GCP route, prove health, service identity, secrets, distributed persistence and no production traffic.
10. Run independent penetration testing covering signed-receipt forgery/replay, API abuse, document upload attacks, virtual-camera/injection, synthetic-media provider boundary, compromised devices and recovery/social engineering.
11. Prove monitoring/SLOs, incident response, audit export, rollback and backup/restore.
12. Run a closed production-like pilot, then an end-to-end provider-native canary covering citizen identity, device trust, document assurance, applicable commissioner event, recipient verification, audit and rollback.
13. Obtain final legal/privacy/Information Officer approval of public wording, consent, terms and data flows.
14. Only after all above gates may a public service be made unauthenticated or promoted to production traffic.

## Current truth
SOURCE_V0_5_SMILE_ID_REFERENCE_ADAPTER_AND_LAYERED_HUMAN_VERIFICATION_IN_GOVERNED_BRANCH. V0_4_IS_MERGED_ON_MAIN. CLOUD_PRODUCTION_DEPLOYMENT_NOT_YET_PROVEN. IDENTITY_PROVIDER_NOT_YET_CONTRACTED_OR_BOUND. COMMISSIONER_AND_RECIPIENT_NETWORKS_NOT_YET_POPULATED. PUBLIC_LAUNCH_NOT_YET_AUTHORISED.

# EvidenceOps eCertify ZA — Production Readiness v0.6

## Implemented source controls
- Legal lanes remain strictly separated: technical assurance cannot silently become certified/commissioned legal status.
- Lane 5 no longer accepts a boolean or caller assertion. It requires a current `RecipientAcceptanceAssessment` bound to the exact recipient, use case, document type, accepted lane, authority evidence, effective period and freshness window.
- The public/private route API rejects client-controlled `recipient_accepts_digital_assurance` and `recipient_acceptance` fields. Verified recipient acceptance is an internal trusted-service evidence path only.
- Commissioner authority now has a source gate for personal/ex-officio designation, identity evidence, current ex-officio capacity, validity period and freshness.
- Certified-copy/affidavit completion is transaction-bound: commissioner identity, authority assessment, transaction ID, document SHA-256, conflict clearance and legal-event evidence must all align.
- `CERTIFIED_COPY` additionally requires original-document inspection evidence. `COMMISSIONED_AFFIDAVIT` requires physical presence and deponent signature in the commissioner's presence; no routine remote exception is implemented.
- A blocked legal event leaves the original `CERTIFICATION_REQUIRED`/`COMMISSIONING_REQUIRED` label unchanged.
- Shared semantic evidence-reference controls reject placeholder states such as `UNBOUND`, `PENDING`, `REFERENCE`, `TEST`, `MOCK`, `UNVERIFIED`, `DRAFT`, `TEMPLATE` and `HOLD` across provider, recipient and commissioner gates.
- Identity-provider receipts pass server-side provider allowlisting, key-ID validation, signature verification, timestamp freshness and replay protection before identity policy is evaluated.
- Identity-provider trust and device trust remain separate domains. Final bank-grade human verification requires both verified identity proof and an independently trusted device.
- Smile ID has a reference adapter based on its published callback-signature and Biometric KYC result contract, but remains unbound to a production contract/readback.
- Replay/idempotency is injected: SQLite is local/reference only; a PostgreSQL-compatible atomic replay guard exists for private-runtime binding.
- Public verification remains privacy-minimal; document intake remains fail-closed pending malware/DLP; isolated zero-traffic Cloud Run canary targets remain dedicated to eCertify.
- eCertify tests remain source-controlled while automated execution stays in the separate private execution plane under Phoenix execution-quarantine policy.
- Commissioner authority, recipient acceptance, POPIA/DPIA, provider RFP, section 57 preliminary determination and go-live control planes exist in the private Drive workspace.

## Hard production gates — LIVE must not be claimed until all have provider-native proof
1. Select/contract an approved identity-verification provider and bind provider-native production semantics, live test vectors, key rotation/revocation and trusted-reference authority proof.
2. Supply the distributed managed-store connection factory through the authorised private runtime and prove atomic replay across instances/restarts.
3. Bind managed secrets/KMS and prove credential/key rotation without raw credentials entering public source/chat.
4. Complete provider-specific POPIA DPIA and written section 57 prior-authorisation determination; complete authorisation before affected processing if required.
5. Bind encrypted object storage, malware scanning, content validation, DLP/redaction and retention/deletion evidence.
6. Bind platform-specific Android/iOS attestation adapters and hardware-backed device keys.
7. Populate the commissioner registry with real verified commissioners/certifiers and current authority/capacity evidence.
8. Populate the recipient registry with real authorised acceptance rules/agreements. Lane 5 remains unavailable without exact current evidence.
9. Bind commissioner-event authentication/capture in the private runtime and prove original-inspection/presence/conflict evidence on real pilot transactions.
10. Deploy isolated zero-traffic private/public canaries through an authorised GCP route and prove health, service identity, secrets, distributed persistence and zero production traffic.
11. Run independent penetration testing across identity receipts, recipient-rule abuse, commissioner-event forgery, document upload, device/recovery and public verifier surfaces.
12. Prove monitoring/SLOs, incident response, audit export, rollback and backup/restore.
13. Run a closed production-like pilot and end-to-end provider-native canary covering identity, device, document, recipient rule, applicable commissioner event, public verification, audit and rollback.
14. Obtain final legal/privacy/Information Officer approval of public wording, consent, terms and data flows.
15. Only after all above gates may public unauthenticated access or production traffic be enabled.

## Current truth
SOURCE_V0_6_RECIPIENT_AND_COMMISSIONER_EVIDENCE_GATES_IN_GOVERNED_BRANCH. V0_5_IS_MERGED_ON_MAIN_AS_B7E28DB9141BD149998E01926832248ED4AE62BC. CLOUD_PRODUCTION_DEPLOYMENT_NOT_YET_PROVEN. IDENTITY_PROVIDER_NOT_YET_CONTRACTED_OR_BOUND. COMMISSIONER_AND_RECIPIENT_REGISTRIES_NOT_YET_POPULATED_WITH_LIVE_PARTNERS. PUBLIC_LAUNCH_NOT_YET_AUTHORISED.

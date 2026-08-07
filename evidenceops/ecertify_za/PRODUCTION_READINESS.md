# EvidenceOps eCertify ZA — Production Readiness v0.7

## Implemented source controls
- All v0.6 recipient/commissioner legal evidence gates remain enforced.
- Document intake is now only the first step: accepted bytes remain `HOLD_FOR_SCAN` until independent security evidence is supplied.
- `DocumentSecurityGate` cross-binds the intake SHA-256 to a scanner receipt and requires CLEAN malware status, cleared DLP, cleared content validation, concrete scan evidence and a fresh timestamp.
- Malicious content or document-hash mismatch is rejected; review/stale/placeholder scan evidence remains on hold.
- `StorageAssuranceGate` requires a verified security assessment plus exact document hash, object identity/version, encryption evidence, provider storage readback, retention-policy evidence and private-only access.
- Production-mode `ECertifyService` rejects direct raw-byte assurance creation with `PRODUCTION_DOCUMENT_SECURITY_EVIDENCE_REQUIRED`.
- Production records can be created only from a verified `SecureDocumentAssessment`, which binds the verified document hash, storage object identity and security/storage evidence digest into the assurance record.
- The raw-byte path remains available only for explicit reference/development use and is labelled `REFERENCE_RAW_BYTES` in metadata.
- Identity, device, recipient, commissioner, legal-event, public-verifier, provider-proof and semantic evidence controls remain separated and fail closed.

## Hard production gates — LIVE must not be claimed until all have provider-native proof
1. Contract and bind an approved IDV provider with provider-native production proof.
2. Bind managed distributed replay/database, secrets and key rotation through the private execution plane.
3. Complete provider-specific POPIA DPIA/section 57 determination and any required prior authorisation.
4. Bind actual encrypted object storage, malware scanner, DLP/content-validation services, deletion/retention automation and provider-native readback to the v0.7 interfaces.
5. Bind platform-specific Android/iOS device-attestation adapters.
6. Populate and verify live commissioner/certifier authority records and transaction-event authentication.
7. Populate real recipient acceptance agreements/rules for Lane 5.
8. Execute isolated zero-traffic Cloud Run canaries and prove identity, secrets, persistence, storage, health and rollback.
9. Complete independent penetration testing, monitoring/SLOs, incident response and backup/restore.
10. Run a closed production-like pilot and end-to-end canary covering identity, device, secure document pipeline, recipient rule, applicable commissioner event, public verification, audit and rollback.
11. Obtain final legal/privacy/Information Officer launch approval.
12. Only then may public unauthenticated access or production traffic be enabled.

## Current truth
SOURCE_V0_7_DOCUMENT_SECURITY_AND_STORAGE_EVIDENCE_GATES_IN_GOVERNED_BRANCH. V0_6_IS_MERGED_ON_MAIN_AS_2BCBBD26AC29754A24F2CC643ACDC1F8B1EC1A40. ACTUAL SCANNER_DLP_STORAGE_PROVIDERS_NOT_YET_BOUND. CLOUD_PRODUCTION_DEPLOYMENT_NOT_YET_PROVEN. IDENTITY_PROVIDER_NOT_YET_CONTRACTED_OR_BOUND. COMMISSIONER_AND_RECIPIENT_REGISTRIES_NOT_YET_POPULATED_WITH_LIVE_PARTNERS. PUBLIC_LAUNCH_NOT_YET_AUTHORISED.

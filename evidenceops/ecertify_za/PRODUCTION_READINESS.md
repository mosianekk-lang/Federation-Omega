# EvidenceOps eCertify ZA — Production Readiness v0.3

## Implemented source controls
- Legal-lane separation for digital originals, source-matched copies, certified-copy gate, affidavit gate and institution-accepted digital assurance.
- Identity-provider receipts must pass server-side provider allowlisting, key-ID validation, HMAC signature verification, timestamp freshness and replay protection before identity policy is evaluated.
- Consent/fallback and sensitive-media boundary controls remain enforced.
- Provider verification, live-presence, trusted-reference, document and device-attestation results remain independently gated after receipt authentication.
- Append-only hash-linked reference ledger.
- Dependency-free containerized HTTP service and OpenAPI contract.

## Hard production gates — LIVE must not be claimed until all have provider-native proof
1. Contract/onboard an approved identity-verification provider with independent security/performance evidence, lawful trusted-reference access and provider-native receipt-signing/webhook semantics.
2. Replace the reference single-instance replay store with a durable distributed replay/idempotency service before horizontal production scale.
3. Inject provider verification keys/secrets only from an approved secret-management service and prove key rotation/revocation.
4. Complete POPIA lawful-basis, special-information, operator, retention/deletion, data-subject-rights, incident and cross-border analysis; determine whether any section 57 prior-authorisation trigger applies.
5. Production identity, encrypted object storage, malware scanning, DLP/redaction, KMS, audit export, rate limiting and abuse controls.
6. Android/iOS platform attestation and hardware-backed device keys; new-device and recovery events must step up.
7. Independent penetration testing including signed-receipt forgery/replay, virtual-camera/injection, synthetic-media, rooted-device, account-recovery and helpdesk social-engineering scenarios.
8. Accessibility and non-biometric fallback validation.
9. Commissioner/certifier authority, conflict and evidence-event verification before any CERTIFIED/COMMISSIONED status.
10. Recipient-specific acceptance rules with source and freshness dates.
11. Provider-native deployment, health, persistence, rollback, monitoring and incident-response receipts.
12. Legal and privacy sign-off on public launch wording and user consent flows.

## Current truth
SOURCE_V0_3_SECURITY_HARDENING_IN_GOVERNED_BRANCH. CLOUD_PRODUCTION_DEPLOYMENT_NOT_YET_PROVEN. IDENTITY_PROVIDER_NOT_YET_BOUND. PUBLIC_LAUNCH_NOT_YET_AUTHORISED.

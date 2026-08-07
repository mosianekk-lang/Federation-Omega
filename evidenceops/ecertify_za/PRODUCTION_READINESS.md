# EvidenceOps eCertify ZA — Production Readiness v0.8

## Implemented source controls
- All v0.7 identity, legal, document-security and storage gates remain enforced.
- Android Play Integrity now has a server-verdict adapter aligned to the provider model: it consumes a server-decrypted/verified verdict, rechecks exact package name, request hash, timestamp freshness, `PLAY_RECOGNIZED`, device-integrity labels and `MEETS_STRONG_INTEGRITY` for high-risk actions.
- Play Integrity request-hash mismatch, stale verdicts, weak high-risk integrity or placeholder provider verification evidence cannot produce a trusted-device outcome.
- Apple App Attest now has a verified-assertion adapter. The private runtime remains responsible for Apple certificate-chain/attestation/assertion cryptographic validation; EvidenceOps rechecks app ID, one-time challenge, environment, validation category and monotonic assertion counter.
- App Attest evidence is treated as a hardware-backed key signal only after those server-side verification semantics are satisfied.
- Hardware-backed application binding and strong platform integrity are distinct device signals. A known device can be trusted when either a hardware-backed binding or strong platform integrity is proven; new-device and account-recovery events always step up.
- Platform/provider evidence references still use the shared semantic placeholder gate and require provider-native/private-runtime proof before production claims.

## Hard production gates — LIVE must not be claimed until all have provider-native proof
1. Contract/bind an approved IDV provider and provider-native signed receipt route.
2. Bind Google Play Integrity server decoding/verification and Apple App Attest cryptographic verification in the authorised private runtime, with real package/App IDs, keys/challenges, counters and provider-native receipts.
3. Bind managed replay/database, secrets/KMS and key rotation.
4. Complete provider-specific POPIA DPIA/section 57 determination and any required prior authorisation.
5. Bind actual encrypted storage, malware/DLP/content validation, retention/deletion automation and readback.
6. Populate live commissioner/certifier authority and recipient acceptance rules.
7. Execute isolated zero-traffic Cloud Run canaries and prove identity, device, secrets, persistence, storage, health and rollback.
8. Complete independent penetration testing, monitoring/SLOs, incident response and backup/restore.
9. Run a closed production-like pilot and end-to-end canary covering IDV, platform device trust, secure document pipeline, recipient rule, commissioner event, public verification, audit and rollback.
10. Obtain final legal/privacy/Information Officer launch approval.
11. Only then may public unauthenticated access or production traffic be enabled.

## Current truth
SOURCE_V0_8_PLATFORM_ATTESTATION_ADAPTERS_IN_GOVERNED_BRANCH. V0_7_IS_MERGED_ON_MAIN_AS_8F29470B339CE0068248C7245145ABE15310B395. GOOGLE_PLAY_AND_APPLE_PRIVATE_RUNTIME_VERIFICATION_NOT_YET_PROVIDER_BOUND. IDENTITY_PROVIDER_NOT_YET_CONTRACTED_OR_BOUND. SCANNER_DLP_STORAGE_PROVIDERS_NOT_YET_BOUND. COMMISSIONER_AND_RECIPIENT_REGISTRIES_NOT_YET_POPULATED_WITH_LIVE_PARTNERS. CLOUD_PRODUCTION_DEPLOYMENT_NOT_YET_PROVEN. PUBLIC_LAUNCH_NOT_YET_AUTHORISED.

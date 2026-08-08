# EvidenceOps eCertify ZA — Launch & Full-Assurance Readiness v0.9

## Release doctrine
Commercial launchability is no longer blocked by every full-assurance dependency.

Two independently governed tracks exist:

### Track A — LAUNCH-NOW / ZERO-POSSESSION
This track can operate without an identity-verification contract, biometric processing, document storage, malware/DLP vendors or remote-commissioning claims.

Citizen value available in Track A:
- local/browser document hashing;
- server-signed EvidenceOps Document Integrity Receipt using only the SHA-256 fingerprint and client nonce;
- technical copy-integrity assurance clearly labelled as non-statutory;
- verified digital-original upgrade when a concrete issuer/source proof exists;
- recipient-approved digital assurance when an exact recipient rule has been independently verified;
- automatic formal-certification / affidavit routing in which the platform, not the citizen, finds and assigns an authority-verified commissioner;
- the final `CERTIFIED_COPY` or `COMMISSIONED_AFFIDAVIT` label remains impossible until the existing legal-completion gates pass.

Zero-Possession principle: the integrity-receipt endpoint rejects document bytes/content. EvidenceOps can therefore provide a useful tamper-evident receipt without becoming custodian of the document file.

Track A production minimum:
1. HTTPS-hosted launch service with `ECERTIFY_MODE=launch_now`.
2. A production integrity-signing key of at least 256 bits, private to the service, with a key ID and rotation procedure.
3. Public verification of server-signed integrity receipts.
4. POPIA-compliant minimal metadata/privacy notice and retention rules for receipt/contact/booking data; no claim that zero-possession eliminates POPIA.
5. Accurate public wording: integrity assurance is not statutory certification, not issuer verification unless separately proven, and not government affiliation.
6. For any formal certification/affidavit transaction, an authority-verified commissioner must be assigned and the transaction-specific legal event must pass before the legal label is released.

### Track B — FULL ASSURANCE
Track B activates stronger identity/source/device/document controls without changing Track A truth labels:
- contracted IDV provider and signed provider receipts;
- Google Play Integrity / Apple App Attest private-runtime verification;
- managed replay/database, secrets/KMS and rotation;
- provider-specific POPIA DPIA / section 57 determination and any required prior authorisation;
- encrypted document storage, malware/DLP/content validation and deletion/retention proof when EvidenceOps actually possesses document bytes;
- populated recipient and commissioner registries;
- provider-native cloud canaries, penetration testing and end-to-end pilot.

## Formal-service operating solution
A citizen requesting a certified copy or affidavit is never told to locate a commissioner. `CommissionerDispatchEngine` owns that dependency:
1. filter to available candidates supporting the requested service and service area;
2. require current verified authority/capacity and conflict clearance;
3. choose the closest eligible candidate with capacity;
4. bind the authority snapshot to the transaction;
5. schedule the original-inspection or physical-presence event;
6. capture legal-event evidence;
7. release the legal label only after `LegalCompletionGate` verifies commissioner, transaction, document hash, conflict and presence/original-inspection conditions.

If no eligible commissioner exists, the platform opens a supply-expansion task for the area. The citizen is not converted into the sourcing agent.

## Commercial model for Track A
Revenue may come from platform subscriptions, institutional verification/API access, integrity receipts, recipient-rule services, fraud/risk services and lawful logistics/convenience services. Any fee associated with an oath/affirmation/attested declaration must respect the Commissioner's fee prohibition; platform pricing must keep prohibited commissioner-act charges separate from lawful technology/logistics services and remain subject to legal review.

## Current truth
SOURCE_V0_9_LAUNCH_NOW_ZERO_POSSESSION_MODE_IN_GOVERNED_BRANCH. FULL_ASSURANCE_CONTROLS_FROM_V0_8_REMAIN_AVAILABLE_BUT_OPTIONAL_FOR_TRACK_A. TRACK_A_DOES_NOT_CREATE_STATUTORY_CERTIFICATION_WITHOUT_A_COMMISSIONER_EVENT. TRACK_A_DOES_NOT_CLAIM_IDENTITY_OR_ISSUER_VERIFICATION_WITHOUT_SEPARATE_PROOF. EXTERNAL_HOSTING_AND_LIVE_COMMISSIONER_SUPPLY_STILL_REQUIRE_PROVIDER_NATIVE_ACTIVATION, BUT THEY NO_LONGER BLOCK THE PRODUCT ARCHITECTURE OR THE SELF_SERVICE_INTEGRITY_LANE.

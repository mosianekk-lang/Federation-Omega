# eCertify ZA — Identity, Security and Privacy Contract

- Purpose limitation: identity proofing is used only for the active eCertify transaction/account-security purpose.
- EvidenceOps consumes signed provider verification receipts; raw sensitive identity media and reusable biometric templates are outside this repository and API boundary.
- A citizen who does not consent to the provider identity route must have a non-biometric fallback rather than permanent exclusion.
- Device activation and recovery are high-risk events and require device attestation, step-up controls and explicit audit receipts.
- Provider verification, live-presence checks, trusted-reference checks and document checks remain separate evidence signals; no single signal is authoritative.
- Identity proofing can never create a CERTIFIED COPY or COMMISSIONED AFFIDAVIT status by itself.
- Public verification must expose status/fingerprint data, not unnecessary ID numbers or sensitive identity evidence.
- Provider contracts must define purpose, data location, retention/deletion, sub-processors, incident notification, independent security testing and audit evidence.
- Every decision preserves policy version, provider transaction ID, signature-validation result, reasons and an evidence digest.

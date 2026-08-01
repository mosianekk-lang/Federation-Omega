# PR #50 Red-Team Review

Status: REPAIRED / PROVIDER_EXECUTION_PENDING / NO-MERGE
Reviewed: 2026-08-01

## Defects found and repaired

1. The Cloud Run workflow previously hard-coded project, provider, identities and service names. Replaced with repository variables and fail-closed validation.
2. Provider validation previously reintroduced the historical pool/provider path as a fixed truth. Replaced with project-number binding plus exact verification against the provider-native WIF receipt.
3. The migration removed the original deployment receipt. Separate canary and promotion receipts are now generated and retained as workflow artifacts.
4. The image reference was scoped only to one job while later logic needed consistent provenance. It is now defined at workflow scope and validated deterministically.
5. The canary image digest was not propagated to promotion proof. It is now an explicit job output and included in both receipts.
6. Health output was verified but not hash-bound to receipts. Canary and promoted health payloads are now SHA-256 bound.
7. Rollback was present but the proof model did not separate canary from promotion. Distinct receipts now state whether traffic was promoted.

## Residual gates

- Repository cloud variables remain empty.
- WIF provider is not provider-verified.
- Infrastructure inventory has not run.
- Cloud resources and identities remain unverified.
- Secret Manager, KMS, PostgreSQL, queues and storage remain unverified.
- OpenAI key containment remains open under issue #51.

## Merge decision

DO NOT MERGE until latest CI and leak checks pass, WIF verification succeeds, inventory variables are populated from verified values, and the infrastructure artifact is generated and reviewed.

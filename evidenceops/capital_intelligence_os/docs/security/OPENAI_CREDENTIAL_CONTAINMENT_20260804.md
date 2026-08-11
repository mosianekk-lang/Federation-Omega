# OpenAI Credential Containment — 4 August 2026

Status: `REPOSITORY_CONTAINED / REPLACEMENT_OWNER_ASSERTED / BINDING_UNVERIFIED / REVOCATION_UNVERIFIED`

Owner and final authority: Kim Kagiso Mosiane

## Determination

Historical records identify a plaintext OpenAI API credential exposure outside the repository. The exposed credential must be treated as compromised until a provider-native revocation and rejection test are both proven.

No raw credential value is reproduced in this record.

The current repository search found three active GitHub Actions workflows consuming the shared `OPENAI_API_KEY` secret alias:

| Workflow | Prior behaviour | Verified runtime state | Containment decision |
| --- | --- | --- | --- |
| `live-thread-autodeploy.yml` | automatic deployment and direct Cloud Run environment injection | latest canonical receipt says deployment not verified | removed from active workflow scope |
| `live-thread-key-recovery.yml` | recovered an existing value from GitHub, Secret Manager or Cloud Run and reused it | no successful replacement-and-revocation receipt | removed from active workflow scope |
| `modisa-legal-v2-autopilot.yml` | hourly and push-triggered live OpenAI canary using the shared alias | no production-promotion proof established here | removed from active workflow scope |

Complete source and history remain recoverable through Git. Removal from `.github/workflows` prevents automatic or manual dispatch through the active Actions surface while the credential state is unresolved.

## Repository controls applied

1. Quarantined every active workflow that consumed the compromised shared alias.
2. Preserved application source, tests, receipts and Git history.
3. Expanded the public repository leak guard to detect an OpenAI key pattern anywhere in supported text files, not only inside assignment statements.
4. Added deterministic regression tests for project-scoped and legacy key formats without embedding a usable credential.
5. Prohibited reactivation through an unchanged secret alias.

## Owner-completed secure setup event

At approximately `2026-08-04T20:13:00+02:00`, the owner reported completion of the authorised OpenAI Platform key-creation flow for the display name:

`Federation Omega Rotation 2026-08-04`

The connected OpenAI Platform tool does not expose key enumeration, raw key readback or revocation readback. The event is therefore classified as:

`OWNER_ASSERTED_CREATED_NOT_PROVIDER_READ_BACK`

The raw key was not returned to repository tooling or chat content.

## Rotation contract added

The following redacted, fail-closed controls now define the remaining work:

- `governance/openai_credential_rotation_manifest.json`
- `ops/openai_rotation_contract.py`
- `tests/test_openai_rotation_contract.py`
- `docs/security/OPENAI_ROTATION_EXECUTION_PLAN_20260804.md`

The contract assigns distinct vault references:

- `openai-mosiane-live-thread-20260804`
- `openai-modisa-legal-v2-20260804`

It rejects raw key patterns, shared destination aliases, literal runtime injection, missing secret-reference readback, missing least-privilege identity proof, incomplete canaries, absent rollback evidence, unproven revocation, unproven old-key rejection and premature completion claims.

## Provider and runtime closure sequence

Credential remediation is complete only after this exact sequence passes:

1. Create or verify the replacement project-scoped OpenAI API key through the authorised OpenAI Platform account.
2. Bind the replacement to new destination-specific secret names in an approved vault. Never reuse the compromised alias as proof of rotation.
3. Identify every confirmed dependent runtime and bind it by secret reference, not a literal environment value.
4. Deploy each runtime through a zero-traffic or otherwise isolated canary.
5. Verify provider call success, application health, semantic behaviour, runtime identity and secret-reference configuration.
6. Promote only the exact verified revision.
7. Revoke the exposed key through OpenAI Platform.
8. Prove the exposed key is rejected without recording its value.
9. Remove or restrict retained plaintext copies while preserving a redacted incident and audit record.
10. Issue a redacted remediation receipt linking replacement target, dependent runtimes, canary proof, revocation proof and rejection proof.

## Reactivation gate

A removed workflow may return to `.github/workflows` only when:

- it uses a new destination-specific secret alias or provider secret reference;
- no direct credential value is placed in Cloud Run configuration, repository text, logs, artifacts or receipts;
- automatic schedules remain disabled until one bounded manual canary succeeds;
- least-privilege runtime access is independently read back;
- rollback is recorded;
- provider-native revocation and old-key rejection are proven;
- repository leak guard and relevant runtime tests pass.

## Current truth state

- Repository workflow exposure: `CONTAINED_ON_MAIN`
- Raw credential printed or copied during containment: `FALSE`
- Replacement key created: `OWNER_ASSERTED / NOT PROVIDER READ BACK`
- Rotation manifest and validator: `BUILT_ON_REVIEW_BRANCH`
- Replacement key bound to runtime vault: `UNVERIFIED`
- Dependent runtimes migrated: `UNVERIFIED`
- Exposed key revoked: `UNVERIFIED`
- Exposed key rejection proven: `UNVERIFIED`
- Current external authority boundary: `GOOGLE_SECRET_MANAGER_BINDING / CLOUD_RUN_READBACK / OPENAI_REVOCATION`

No service is classified as production-operational merely because source, configuration, an owner assertion or a historical workflow exists.

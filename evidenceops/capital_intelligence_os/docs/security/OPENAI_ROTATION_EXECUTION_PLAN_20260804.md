# OpenAI Credential Rotation Execution Plan — 4 August 2026

Status: `KEY_CREATION_OWNER_ASSERTED / CONTRACT_BUILT / VAULT_BINDING_UNVERIFIED / CANARIES_UNVERIFIED / REVOCATION_UNVERIFIED`

Owner and final authority: Kim Kagiso Mosiane

## Purpose

Complete the OpenAI credential rotation without placing a raw key in repository source, GitHub Actions variables, logs, artifacts, receipts, chat content or literal Cloud Run environment configuration.

The secure key-creation flow was completed by the owner at approximately `2026-08-04T20:13:00+02:00`. The connected OpenAI Platform tool does not expose key enumeration or raw key readback, so creation is recorded as owner-asserted rather than provider-native verified.

## Canonical control manifest

The machine-readable contract is:

`governance/openai_credential_rotation_manifest.json`

The validation and receipt tool is:

`ops/openai_rotation_contract.py`

The contract fails closed if:

- a raw OpenAI key pattern appears anywhere in the manifest or receipt;
- the compromised shared GitHub secret alias is reused as a destination secret identifier;
- the two workloads use the same vault reference;
- secret-reference or runtime-identity readback is missing;
- canary health, semantic behaviour or rollback proof is missing;
- provider revocation or old-key rejection is unproven;
- a completion claim is made before every evidence gate passes.

## Destination contracts

### Mosiane Live Thread

- Provider project: `sov-hybrid-suite`
- Region: `africa-south1`
- Cloud Run service: `mosiane-live-thread`
- Runtime identity: `superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com`
- Destination vault reference: `openai-mosiane-live-thread-20260804`
- Runtime environment name: `OPENAI_API_KEY`
- Binding mode: Google Secret Manager reference only
- Canary: zero-traffic Cloud Run revision
- Semantic proof: isolated message request followed by a hash-chained assistant response
- Promotion: blocked until the exact revision, identity, secret reference, health, semantic probe and rollback target are read back

The redacted binding template is:

```text
gcloud run services update mosiane-live-thread \
  --project sov-hybrid-suite \
  --region africa-south1 \
  --update-secrets OPENAI_API_KEY=openai-mosiane-live-thread-20260804:latest \
  --no-traffic
```

This template contains no credential value. The secret version must be created through a provider-authorised secure input path that does not echo the value.

### MODISA Legal V2

- Provider project: `sov-hybrid-suite`
- Region: `africa-south1`
- Destination vault reference: `openai-modisa-legal-v2-20260804`
- Runtime environment name: `OPENAI_API_KEY`
- Binding mode: Google Secret Manager reference only
- Execution plane: separate private operations plane required
- Canary: isolated non-production seven-chamber qualification
- Semantic proof: trace ID, seven independent opinions, council completion and proof-bound release decision
- External actions: disabled throughout qualification
- Promotion: blocked pending private execution-plane identity and secret-reference readback

The previous public workflow is not restored because it ran hourly, accepted the shared GitHub secret alias, retained repository write authority and committed runtime receipts into source.

## Required closure sequence

1. Create two destination-specific secret versions through a non-echoing provider-authorised input channel.
2. Read back only secret metadata, never the payload.
3. Bind each runtime by secret reference under a least-privilege runtime identity.
4. Capture the previous production revision or equivalent rollback target.
5. Run the bounded isolated canaries.
6. Verify application health and required semantic behaviour.
7. Promote only the exact verified revision.
8. Revoke the exposed OpenAI key through the provider account.
9. Prove that the exposed key is rejected without recording its value.
10. Issue a redacted closure receipt and validate it with `ops/openai_rotation_contract.py`.

## Current execution boundary

The connected tools can prepare, validate, review and publish repository contracts, but they currently expose neither:

- Google Secret Manager secret-version creation or payload binding;
- Cloud Run provider-native deployment and configuration readback;
- OpenAI API-key enumeration or revocation.

No private GitHub operations repository currently exists, and the connected GitHub action set does not expose repository creation. Therefore no secret binding, runtime deployment, revocation or rejection proof is claimed here.

## Current truth state

- Replacement key creation: `OWNER_ASSERTED_CREATED_NOT_PROVIDER_READ_BACK`
- Raw key available to repository or chat: `FALSE`
- Rotation manifest: `BUILT`
- Deterministic validation: `BUILT`
- Destination vault references: `NAMED_NOT_BOUND`
- Live Thread canary: `NOT RUN`
- MODISA Legal V2 canary: `NOT RUN`
- Exposed key revocation: `UNVERIFIED`
- Exposed key rejection: `UNVERIFIED`
- Completion: `BLOCKED`

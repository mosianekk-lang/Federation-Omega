# OpenAI Runtime Secret-Binding Contract

## Purpose

Replace exposed email-stored OpenAI project keys with one project-scoped runtime credential that never appears in chat, email, Drive documents, GitHub content or logs.

## Required target

- dedicated EvidenceOps OpenAI project
- key name: `EvidenceOps-Runtime-Replacement`
- Google Secret Manager secret: `evidenceops-openai-runtime-key`
- access limited to the authorised EvidenceOps runtime service account

## Binding requirements

1. Create the replacement key through the secure OpenAI Platform flow.
2. Store the raw value directly in Secret Manager.
3. Do not write the value to local plaintext files, Gmail, Drive, GitHub Actions variables or repository secrets unless the deployment design explicitly requires a repository secret.
4. Bind only the runtime service account as `roles/secretmanager.secretAccessor` on the named secret.
5. Record project, secret name, runtime identity, version creation time and audit receipt without recording the key or public fingerprint.
6. Execute a minimal non-sensitive replacement-key canary.
7. Revoke each exposed key.
8. Execute an old-key rejection canary and record only the authentication failure class.
9. Close security issue #51 only after both canaries and runtime readback pass.

## Proof states

- `SETUP_FLOW_OPENED`
- `REPLACEMENT_KEY_CREATED`
- `SECRET_VERSION_BOUND`
- `RUNTIME_ACCESS_VERIFIED`
- `REPLACEMENT_CANARY_PASS`
- `OLD_KEYS_REVOKED`
- `OLD_KEY_REJECTION_VERIFIED`
- `INCIDENT_CONTAINED`

## Prohibited proof

A created key, configured secret name or successful local request alone does not prove production runtime binding.

# FUSE Windows Execution Plane v1

This additive Federation component provides a real, bounded Windows execution surface without creating a second scheduler, authority root, proof plane or memory system.

## Shippable profiles

1. **Hosted ephemeral Windows** — `windows-latest` GitHub Actions worker with read-only repository permissions, a 15-minute timeout, typed task selection, failure-first tests, and an immutable JSON receipt artifact.
2. **Owner-workstation adapter** — the same Python task engine and PowerShell entrypoint, ready for binding through the existing BEF/ChatBridge Windows lineage once a provider-authorized bootstrap reaches the workstation.

The hosted profile is the first deployable product because it needs no permanent machine, no new subscription and no secret. The owner-workstation profile is not called installed until a receipt from that machine is read back.

## Security model

- only `health`, `inventory`, and `hash_workspace_file` exist;
- no arbitrary shell, subprocess or dynamic module execution;
- task issuer is fixed to `FUSE/FDOF`; for the hosted profile, GitHub dispatch/PR permissions are the authentication boundary;
- task TTL is at most 15 minutes;
- effect ceiling is `READ_ONLY`;
- file hashing is confined to the checked-out workspace and 32 MiB;
- host names are represented only by SHA-256;
- workflow token is read-only and checkout credentials are not persisted;
- every receipt binds the canonical task envelope and result with SHA-256.

The `issued_by` field is a policy label, not a cryptographic credential. The owner-workstation profile therefore remains unbound until a separately authorized authenticated transport is proven. Read-only tasks are TTL-bounded and idempotent in effect, but v1 does not claim a durable cross-run replay cache.
The v1 CLI deliberately does not accept a caller-supplied envelope; it constructs the allowlisted envelope inside the authenticated invocation boundary.

## Run locally

```powershell
$env:PYTHONPATH = "$PWD\windows_federation_plane\src"
python -m unittest discover -s windows_federation_plane\tests -v
.\windows_federation_plane\scripts\Invoke-FederationWindowsTask.ps1 -Task health
```

On non-Windows systems, only deterministic development tests may use the hidden `--allow-non-windows-test` flag. The production entrypoint fails unless `OS=Windows_NT`.

## Deployment

The source-admitted workflow executes on pull requests that change this component and supports a restricted manual dispatch after merge. Promotion requires:

1. Windows job success;
2. receipt artifact existence;
3. `runner.os == Windows`;
4. `runner.github_actions == true`;
5. exact receipt hash readback;
6. current source ancestry and regression status.

## Rollback

Disable the workflow by reverting its admission commit. It holds no persistent credentials or provider state. Owner-workstation rollback remains governed by the existing BEF scoped rollback scripts.

## Debugging

| Symptom | Likely cause | Resolution |
|---|---|---|
| `WINDOWS_RUNTIME_REQUIRED` | Production entrypoint ran outside Windows | Route to the hosted Windows job or verified Windows host |
| `TASK_TYPE_NOT_ALLOWLISTED` | Unsupported or injected task | Reject; add capabilities only through a reviewed source change |
| `PATH_ESCAPE_DENIED` | File target escaped workspace | Supply a repository-relative path inside the checkout |
| `TASK_EXPIRED` | Stale envelope | Issue a fresh FDOF-bound envelope |
| Missing receipt artifact | Task or verification failed | Inspect the exact Windows job; never infer success |

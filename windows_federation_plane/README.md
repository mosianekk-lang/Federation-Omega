# FUSE Windows Execution Plane v1.1

This additive Federation component provides a real, bounded Windows execution surface without creating a second scheduler, authority root, proof plane or memory system.

## Shippable profiles

1. **Hosted ephemeral Windows** — `windows-latest` GitHub Actions worker with read-only repository permissions, a 15-minute timeout, typed task selection, failure-first tests, and an immutable JSON receipt artifact.
2. **Owner-workstation relay** — the same task engine behind an outbound-only agent, a FUSE-owned Streamable HTTP MCP endpoint, OAuth 2.1/OIDC verification, Firestore transactions, request signing, replay rejection, leases, idempotent completion and DPAPI-protected device credentials.

The hosted profile needs no permanent machine or subscription. The owner-workstation profile is not called installed until the Cloud Run service, ChatGPT connection, enrollment, machine heartbeat and task receipt are independently read back.

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
- ChatGPT-facing MCP calls require an exact-issuer, exact-audience, signed OAuth token carrying `fuse.windows`;
- workstation requests use per-device HMAC credentials derived from a Cloud Run root secret and are replay-protected in Firestore;
- the Windows credential is encrypted for the current Windows user with DPAPI;
- the workstation opens only outbound HTTPS connections; no RDP or inbound workstation listener is required.

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

The FUSE-owned relay deploys through `.github/workflows/fuse-windows-relay-cloud-run-v1.yml`. It uses the existing GitHub OIDC/WIF deployer, builds an immutable image, creates a zero-traffic canary, proves `/healthz`, proves unauthenticated `/mcp` is rejected, promotes only the exact canary revision, and restores the previous revision on failure. The workflow requires repository variables `FUSE_OIDC_ISSUER` and `FUSE_OIDC_JWKS_URL`; secrets remain in Google Secret Manager.

The MCP endpoint is intentionally internet reachable at the transport layer so ChatGPT can reach it. Privileged access remains closed by OAuth at `/mcp`; workstation endpoints use signed requests. Public reachability is not equivalent to authorization.

## Owner workstation agent

After the MCP tool issues a five-minute one-time enrollment grant, run the agent through a controlled installer or service wrapper:

```powershell
$env:FUSE_RELAY_URL = "https://fuse-windows-relay-...run.app"
$env:FUSE_ENROLLMENT_ID = "<single-use-id>"
$env:FUSE_ENROLLMENT_TOKEN = "<single-use-token>"
federation-windows-agent --workspace C:\FUSE\workspaces
```

The enrollment values are consumed once. The resulting device credential is DPAPI-encrypted and subsequent polling is autonomous.

## Rollback

For source rollback, revert the admission commit. For a failed provider canary, the deployment workflow returns traffic to the previously active revision. Disable a workstation by revoking its Firestore device record and stopping its agent service; rotate the root Secret Manager version to invalidate all derived device credentials.

## Debugging

| Symptom | Likely cause | Resolution |
|---|---|---|
| `WINDOWS_RUNTIME_REQUIRED` | Production entrypoint ran outside Windows | Route to the hosted Windows job or verified Windows host |
| `TASK_TYPE_NOT_ALLOWLISTED` | Unsupported or injected task | Reject; add capabilities only through a reviewed source change |
| `PATH_ESCAPE_DENIED` | File target escaped workspace | Supply a repository-relative path inside the checkout |
| `TASK_EXPIRED` | Stale envelope | Issue a fresh FDOF-bound envelope |
| Missing receipt artifact | Task or verification failed | Inspect the exact Windows job; never infer success |

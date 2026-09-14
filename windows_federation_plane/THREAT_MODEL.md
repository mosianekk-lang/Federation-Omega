# Threat Model

## Scope

Protected assets are the repository checkout, task intent, task and result integrity, hosted workflow identity, receipt artifact, and the boundary separating hosted Windows from an owner workstation. Version 1 has no cloud credential, private evidence, mutable database, inbound listener, or arbitrary-command interface.

## Trust boundaries

1. GitHub authorizes pull-request creation and manual workflow dispatch.
2. The workflow constructs an allowlisted task inside that boundary.
3. The Python policy validates the task and confines file access to the checkout.
4. GitHub stores the receipt as a short-retention artifact.
5. An independent reader verifies the run, job, artifact, runner, task hash, result hash, and source SHA.

The issued-by value is a policy label, not cryptographic identity. Version 1.1 adds cryptographic transport identity: exact-issuer/audience OAuth for MCP and derived HMAC credentials for the outbound Windows agent. The owner workstation remains outside the proven production boundary until its live enrollment and receipt are read back.

## Threats and controls

| Threat | Control | Residual boundary |
|---|---|---|
| Command or argument injection | Fixed task enum; no subprocess, shell evaluation, dynamic import, or caller envelope | New tasks require reviewed source |
| Path traversal or symlink escape | Relative path, resolved containment, file-only target, 32 MiB ceiling | Hosted checkout is assumed stable during one task |
| Stale or future request | UTC validation and maximum 900-second window | No durable cross-run replay store is claimed |
| Confused deputy or forged label | Caller envelopes disabled; GitHub invocation is the hosted authentication boundary | Owner-host transport is unbound |
| Secret or private-data leakage | No secrets requested; read-only token; leak guard; bounded public receipt | File-hash task exposes requested path, size, and digest |
| Artifact tampering | Task and result SHA-256 plus GitHub artifact digest and independent readback | GitHub remains a trusted provider boundary |
| Source drift or concurrent writer | Monotonic FDOF lease, exact source head, non-force update, exact-head PR checks | Provider ruleset enforcement is outside this component |
| Runner compromise | Ephemeral hosted runner, no secrets, read-only effect, 15-minute timeout | A compromised provider runner could forge local output; provider metadata/readback reduces but cannot eliminate this risk |
| Denial of service or queue starvation | Concurrency key, bounded timeout, no cancellation of an active run | GitHub runner availability is external |
| Accidental authority expansion | Default read-only effect, explicit governance record, separate owner-host/provider tranches | Future write-capable tasks require a new threat model and authorization |
| Forged ChatGPT caller | JWT signature, issuer, audience, expiry, client identity and `fuse.windows` scope validation | Security depends on the selected authorization server and its client registration |
| Forged workstation | Single-use enrollment, derived per-device secret, canonical request signature and constant-time comparison | Root-key compromise requires rotation of all device credentials |
| Replay or concurrent lease | Firestore create-once nonce record and transactional lease update | Nonce documents require a provider TTL policy for automatic cleanup |
| Cloud Run instance loss | No in-memory authority state; Firestore is canonical | Regional provider failure remains external; backup/restore must be exercised before production certification |
| Device credential theft | Windows DPAPI current-user protection and revocable device record | Malware running as the same Windows user remains in the workstation trust boundary |
| Tunnel runtime-key disclosure | Key accepted as `SecureString` or inherited environment only; DPAPI current-user encryption; user-only ACL; never written to logs or profile arguments | Same-user malware and process-memory inspection remain inside the endpoint trust boundary |
| Public MCP exposure | Direct profile uses stdio and the official outbound-only Secure MCP Tunnel client; no workstation listener | OpenAI control-plane availability and tunnel/workspace permissions remain provider boundaries |
| Supervisor persistence abuse | Limited current-user scheduled task, fixed runner path, fixed profile, RemoteSigned policy, no elevation, explicit stop switch | A compromised current user can replace user-owned files; source-signing enforcement is a later promotion gate |
| Installer supply-chain substitution | Python dependencies are installed from the hash lock; tunnel-client path must already resolve locally; no mutable binary download is embedded | The externally obtained tunnel-client binary must be verified through its official distribution channel |

## Promotion rule

Hosted verification requires exact-head source courts, a successful Windows job, an artifact receipt, semantic field checks, and independent hash verification. Tunnel production proof additionally requires `doctor` success, a running supervised task, ChatGPT tool discovery, an exact health receipt from the physical endpoint, persistence after logon/restart, and an exercised stop/rollback path. Source presence alone proves none of these.

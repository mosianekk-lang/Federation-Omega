# Federation Ω Shared Automation Authority Fabric

This subsystem turns the owner-controlled Google Sheet **Federation Ω — Shared Automation Authority Fabric** into shared command ingress for Superior Logic, SOVARA and other admitted Federation engines.

## Why this exists

The old pattern forced each chat/runtime to rediscover or carry its own provider authority. This fabric separates **chat intent**, **execution authority**, **provider effect**, and **proof**:

1. An authorized chat writes a governed row to `COMMAND_QUEUE` through the user's connected Google Drive surface.
2. A private Cloud Run worker polls the queue through Cloud Scheduler.
3. Policy selects autonomous read/lab authority, mission-lease authority, or fail-closed denial.
4. Provider-admin commands use short-lived impersonation of the temporary bootstrap admin; the runtime service account does not store an admin key.
5. Every terminal command writes `COMMAND_RECEIPTS` with provider identity, semantic readback, proof and digest.
6. Other chats can read the same control plane and receipts. This is shared state through Drive/KDV, **not hidden native chat-to-chat communication**.

## Autonomy classes

- `READ` — autonomous.
- `LAB_WRITE` — autonomous in non-serving labs; rollback + readback required.
- `CONTROL_PLANE_WRITE` — active mission lease required.
- `PROVIDER_ADMIN_WRITE` — active mission lease plus short-lived elevated impersonation.
- `DESTRUCTIVE_WRITE` — never covered by a reusable mission lease; exact one-use authority required.
- `COMMUNICATION_WRITE` — never covered by reusable automation authority; explicit user send/forward/reply instruction remains mandatory.

## Cross-chat contract

A chat with Superior Logic/SOVARA loaded can use the fabric when it has the connected Google Drive surface:

- register or refresh itself in `CHAT_SESSIONS`;
- read `CONTROL`, `CAPABILITY_REGISTRY`, `ROUTE_REGISTRY`, and the relevant active lease;
- append one canonical command to `COMMAND_QUEUE` with a unique `command_id` and `idempotency_key`;
- do **not** place tokens, API keys, private keys or credentials in payloads;
- wait for/read the matching `COMMAND_RECEIPTS` row;
- promote a claim only to the level supported by the receipt's semantic readback.

Recommended command fields:

```text
command_id, created_at_sast, requested_by_chat, engine, mission_id, lease_id,
adapter_id, action, effect_class, target_alias, payload_json,
required_proofs_json, idempotency_key, priority, state=QUEUED
```

## Security invariants

- No service-account private key is created.
- The permanent runtime identity is narrow.
- Temporary admin IAM expires automatically.
- Elevated operations use 15-minute service-account impersonation credentials.
- The queue spreadsheet is the owner-controlled ingress authority; share it only with the runtime service account.
- Cloud Run is private; Cloud Scheduler invokes it with OIDC.
- Service is deployed single-instance/single-concurrency during bootstrap to prevent double claims while Sheets is the queue store.
- Replayed idempotency keys are rejected before provider execution.
- Mission leases have expiry, scope and command budgets.
- Success requires provider semantic readback, not HTTP 2xx/LRO acceptance alone.
- Outbound communications and destructive commands remain separately gated.

## Initial bounded Google actions

The v1 executor intentionally starts bounded rather than accepting arbitrary REST calls:

- `GCP_GET_PROJECT`
- `GCP_LIST_ENABLED_SERVICES`
- `GCP_ENABLE_SERVICE`
- `CLOUD_RUN_GET_SERVICE`
- `APPS_SCRIPT_GET_CONTENT`
- `APPS_SCRIPT_GET_DEPLOYMENTS`
- `APPS_SCRIPT_RUN`

Additional provider actions should be added as explicit handlers with their own target validation and semantic readback contract.

## Bootstrap

Run `scripts/bootstrap_federation_automation.sh` once from an authenticated Google Cloud Shell after the source is admitted to main. The script creates:

- `federation-bootstrap-admin` — temporary, high-authority, expiring identity;
- `federation-automation-runtime` — narrow permanent runtime identity;
- GitHub WIF restricted to `mosianekk-lang/Federation-Omega`;
- private `federation-automation-gateway` Cloud Run service;
- one-minute Johannesburg Cloud Scheduler tick;
- short-lived runtime→bootstrap impersonation capability that expires with bootstrap authority.

The bootstrap does **not** grant email-send authority, does not create a service-account key, and does not itself claim Apps Script function execution until provider readback proves it.

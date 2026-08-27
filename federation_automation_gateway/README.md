# Federation Ω Shared Automation Authority Fabric

This subsystem turns the owner-controlled Google Sheet **Federation Ω — Shared Automation Authority Fabric** into shared command ingress for Superior Logic, SOVARA and other admitted Federation engines.

## Why this exists

The old pattern forced each chat/runtime to rediscover or carry its own provider authority. This fabric separates **chat intent**, **execution authority**, **provider effect**, and **proof**:

1. An authorized chat writes a governed row to `COMMAND_QUEUE` through the user's connected Google Drive surface.
2. Route ownership sends the command to one of two executors:
   - private Cloud Run service-account executor for Google Cloud operations;
   - owner-OAuth Apps Script broker for Apps Script source/version/deployment management.
3. Policy selects autonomous read/lab authority, mission-lease authority, or fail-closed denial.
4. Google Cloud provider-admin commands use short-lived impersonation of the temporary bootstrap admin; the permanent runtime service account does not store an admin key.
5. The Apps Script broker uses `ScriptApp.getOAuthToken()` from the already-authorized owner Apps Script surface. It does not copy owner credentials into chats or Cloud Run.
6. Every terminal command writes `COMMAND_RECEIPTS` with provider identity, semantic readback, proof and digest.
7. Other chats can read the same control plane and receipts. This is shared state through Drive/KDV, **not hidden native chat-to-chat communication**.

## Why there are two executors

Google's current Apps Script documentation states that the Apps Script API does not work with service accounts. Remote `scripts.run` has an additional requirement: the calling application and target script must share the same standard Cloud project and the target must be deployed as an API executable. The Federation therefore does not pretend that the Cloud Run service account can execute arbitrary Apps Script projects.

The Cloud Run worker skips `apps_script` queue rows. The owner-OAuth broker consumes those rows instead and provides bounded Apps Script management with backups and exact readback. Direct target-function execution remains a separate admission gate until its documented provider prerequisites are proven for that target.

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
- choose the registered `adapter_id` rather than inventing a direct provider route;
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
- The permanent Cloud runtime identity is narrow.
- Temporary admin IAM expires automatically.
- Elevated Cloud operations use 15-minute service-account impersonation credentials.
- Owner OAuth stays inside the existing Apps Script broker runtime; it is never exported into the shared Sheet or chats.
- The queue spreadsheet is the owner-controlled ingress authority.
- Cloud Run is private; Cloud Scheduler invokes it with OIDC.
- Cloud worker is deployed single-instance/single-concurrency during bootstrap to prevent double claims while Sheets is the queue store.
- Each executor consumes only its registered adapter rows, preventing cross-executor command theft.
- Replayed idempotency keys are rejected before provider execution.
- Mission leases have expiry, target/effect scope and command budgets.
- Apps Script write operations create a verified source backup before mutation and require post-write project-hash equality.
- Apps Script targets must be present in the canonical Federation Lab Kernel `LAB_REGISTRY`.
- Success requires provider semantic readback, not HTTP 2xx/LRO acceptance alone.
- Outbound communications and destructive commands remain separately gated.

## Initial bounded Google Cloud actions

- `GCP_GET_PROJECT`
- `GCP_LIST_ENABLED_SERVICES`
- `GCP_ENABLE_SERVICE`
- `CLOUD_RUN_GET_SERVICE`

## Initial bounded Apps Script broker actions

- `APPS_SCRIPT_GET_CONTENT`
- `APPS_SCRIPT_GET_DEPLOYMENTS`
- `APPS_SCRIPT_UPSERT_FILE`
- `APPS_SCRIPT_REPLACE_CONTENT`
- `APPS_SCRIPT_ROLLBACK_CONTENT`
- `APPS_SCRIPT_CREATE_VERSION`
- `APPS_SCRIPT_CREATE_DEPLOYMENT`
- `APPS_SCRIPT_UPDATE_DEPLOYMENT`

The broker intentionally does **not** expose arbitrary HTTP passthrough or generic dynamic function execution.

## Bootstrap

Run `scripts/bootstrap_federation_automation.sh` once from an authenticated Google Cloud Shell after the source is admitted to main. The script creates:

- `federation-bootstrap-admin` — temporary, high-authority, expiring identity;
- `federation-automation-runtime` — narrow permanent runtime identity;
- GitHub WIF restricted to `mosianekk-lang/Federation-Omega` main;
- private `federation-automation-gateway` Cloud Run service;
- one-minute Johannesburg Cloud Scheduler tick;
- short-lived runtime→bootstrap impersonation capability that expires with bootstrap authority;
- a bounded attempt to enable Service Usage + Apps Script API for the known owner-OAuth broker consumer project when that project is provider-visible to the authenticated owner.

After Cloud bootstrap, the connected Drive route shares the Fabric Sheet with the runtime service account. The existing owner-OAuth ChatOps queue then installs `apps_script_owner_broker/FED_Automation_Broker.gs` through its already-governed source-update path once Apps Script API readback is healthy.

The bootstrap does **not** grant email-send authority, does not create a service-account key, and does not claim target Apps Script function execution until provider evidence proves the documented execution prerequisites.

# Federation Ω Shared Automation Authority Fabric

This subsystem turns the owner-controlled Google Sheet **Federation Ω — Shared Automation Authority Fabric** into shared command ingress for Superior Logic, SOVARA and other admitted Federation engines.

## Why this exists

The fabric separates **chat intent**, **execution authority**, **provider effect**, and **proof**:

1. An authorized chat writes a governed row to `COMMAND_QUEUE` through the owner's connected Google Drive surface.
2. Route ownership sends the command to one of two executors:
   - private Cloud Run service-account executor for bounded Google Cloud operations;
   - owner-OAuth Apps Script broker for Apps Script source/version/deployment management.
3. Policy selects autonomous read/lab authority, mission-lease authority, or fail-closed denial.
4. The Cloud Run runtime uses the narrow `superior-logic-runtime` identity. Provider-admin execution is **not** implied by deployment and fails closed unless a separately admitted elevated identity is explicitly bound and read back.
5. The Apps Script broker uses `ScriptApp.getOAuthToken()` from the already-authorized owner Apps Script surface. Owner OAuth is never copied into chats or Cloud Run.
6. Every terminal command writes `COMMAND_RECEIPTS` with provider identity, semantic readback, proof and digest.
7. Other chats can read the same control plane and receipts. This is shared state through Drive/KDV, **not hidden native chat-to-chat communication**.

## Why there are two executors

Google's Apps Script API execution model does not make an arbitrary service-account Cloud Run worker a substitute for the owner-authorized Apps Script surface. Direct `scripts.run` also depends on the target's API-executable and Cloud-project configuration. The Cloud Run worker therefore does not steal `apps_script` queue rows; the owner-OAuth broker consumes those rows separately with bounded backup/readback controls.

## Autonomy classes

- `READ` — autonomous.
- `LAB_WRITE` — autonomous in non-serving labs; rollback + readback required.
- `CONTROL_PLANE_WRITE` — active mission lease required.
- `PROVIDER_ADMIN_WRITE` — active mission lease **and** an independently admitted elevated provider identity; otherwise execution fails closed.
- `DESTRUCTIVE_WRITE` — never covered by a reusable mission lease; exact one-use authority required.
- `COMMUNICATION_WRITE` — never covered by reusable automation authority; explicit user send/forward/reply instruction remains mandatory.

## Cross-chat contract

A chat with an admitted Federation engine can use the fabric when it has the connected Google Drive surface:

- register or refresh itself in `CHAT_SESSIONS`;
- read `CONTROL`, `CAPABILITY_REGISTRY`, `ROUTE_REGISTRY`, and the relevant active lease;
- append one canonical command to `COMMAND_QUEUE` with a unique `command_id` and `idempotency_key`;
- choose the registered `adapter_id` rather than inventing a direct provider route;
- never place tokens, API keys, private keys or credentials in payloads;
- read the matching `COMMAND_RECEIPTS` row;
- promote a claim only to the level supported by semantic readback.

Recommended command fields:

```text
command_id, created_at_sast, requested_by_chat, engine, mission_id, lease_id,
adapter_id, action, effect_class, target_alias, payload_json,
required_proofs_json, idempotency_key, priority, state=QUEUED
```

## Security invariants

- No service-account private key is created.
- Deployment and runtime identities are separate: `superior-logic-deployer` deploys; `superior-logic-runtime` serves.
- GitHub federation uses a dedicated workflow-scoped WIF provider for the automation gateway; the separate LiteLLM provider trust is not broadened or reused.
- The runtime identity remains narrow; deployment success does not grant provider-admin runtime authority.
- Owner OAuth stays inside the existing Apps Script broker runtime; it is never exported into the shared Sheet or chats.
- The queue spreadsheet is the owner-controlled ingress authority.
- Cloud Run is private; Cloud Scheduler invokes it with OIDC.
- The Cloud worker is single-instance/single-concurrency at genesis to prevent double claims while Sheets is the queue store.
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
- `GCP_ENABLE_SERVICE` — only executable when the separately admitted elevated identity is actually bound.
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

## Activation

Activation is source-admitted and provider-proof-bound:

1. A dedicated Google WIF provider is created under pool `github-federation-omega`, scoped only to `.github/workflows/federation-automation-gateway-activate.yml@refs/heads/main` and admitted `push`/`workflow_dispatch` events.
2. The workflow authenticates as the existing `superior-logic-deployer` service account. It does not create identities, create keys, broaden the LiteLLM WIF provider, or silently enable APIs.
3. The workflow verifies the project, required APIs and existing `superior-logic-runtime` service account.
4. It deploys private `federation-automation-gateway`, binds only the required Cloud Run invokers, reconciles the Johannesburg one-minute scheduler, and performs provider-native service/scheduler/health readback.
5. Activation remains incomplete until the Fabric Sheet ACL is proven and a real queue command reaches a semantic terminal receipt.

The former `federation-bootstrap-admin` time-expiry path is historical continuity only and is not part of this re-anchored activation design.

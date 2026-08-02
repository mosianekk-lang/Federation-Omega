# Federation Omega read-discovery upgrade

Status: **implemented and locally testable; not deployed, not live, and not wired into the current Cloud Run operator**.

The repository does not contain the source of the currently deployed `federation-omega-operator` image. This package is therefore an isolated, reviewable upgrade contract—not evidence that the live allowlist has changed.

## Read-only actions

- `READ_WIF_PROVIDER_METADATA` performs one fixed-host Google IAM `GET` for one exact allowlisted provider resource. Caller payloads cannot supply a URL, access token, credential or secret. Redirects are rejected both by the default transport and by requiring the final response URL to equal the requested Google IAM URL; the response is capped at 64 KiB. Output contains only identity-match status, provider state, disabled/expiry flags, provider kind, coarse issuer class, bounded attribute-mapping key names and whether an attribute condition exists. Raw resource paths, conditions, mapping values, audiences, issuer URIs, JWKs, tokens and upstream error bodies are never returned.
- `READ_GITHUB_ACTIONS_CONFIG_PRESENCE` directly reads only the immutable exact seven-name allowlist from the workflow process environment, covering the canonical, `GCP_WORKLOAD_IDENTITY_PROVIDER`, and generic `WIF_PROVIDER` recovery lanes. The request cannot supply names, values or Boolean claims, and constructor attempts to use a subset, superset or replacement set fail closed. Source values are discarded and the response contains only names, presence state and lane completeness. It is deliberately labelled `DIRECT_ALLOWLISTED_ENVIRONMENT_PRESENCE` with `independentReadback: false` and `runtimeOriginVerified: false`: the core module does not query GitHub, authenticate the runner, prove repository scope, or prove the values are correct.

Both actions require `mutation: "NONE"`, reject extra payload fields and report stable classifications without returning exception details.

Provider discovery reports metadata success separately from operational status. Deleted and disabled providers receive explicit blocked classifications. Even an active, enabled provider is labelled `METADATA_ACTIVE_TOKEN_EXCHANGE_UNVERIFIED`; no token exchange is attempted or claimed.

## Production adapter boundary

The future Cloud Run adapter must:

1. construct `GoogleIamProviderClient` with an exact provider-resource allowlist;
2. supply an access token from the operator's existing runtime identity—not from request data;
3. expose only the two constants in this package through its existing authenticated action dispatcher;
4. map only the exact seven non-secret GitHub `vars` entries into same-named process-environment entries before untrusted execution; the reader indexes only those entries, never enumerates the environment, never returns values, and the production adapter—not this core module—must bind the snapshot to the authenticated repository and workflow identity;
5. retain current authentication, logging, timeout and request-size controls; and
6. prove the deployed allowlist and both action semantics through independent live readback before any `DEPLOYED` or `LIVE` claim.

No workflow in this draft deploys the package, dispatches another workflow, changes IAM, reads Secret Manager, enables APIs, changes billing, routes traffic or updates a Git reference.

## KDV-L017 executor guard

`execute_kdv_l017_sequence` accepts injected create, gate, current-reference read and reference-update functions. It calls the dependent updater with `force=False` only when the gate returns `decision: "ALLOW"`, explicitly reports `KDV-L017`, and an immediate readback proves the reference still points at the expected old object. Every malformed, stale, exceptional or blocked result stops before the reference update.

Run the focused suite with:

```bash
python -m unittest tests.test_federation_operator_read_discovery -v
```

# Local Bible Recovery execution boundary

Status: `PRIVATE_OPS_PLANE_REQUIRED`

The Local Bible Event 13 recovery implementation remains available at `ops/evidenceops_local_bible_event13_rebuild.py`, together with its source-level privacy, hash-chain and artifact-output tests.

It remains deliberately **not executable from the legacy public source repository**.

## Reason

General source-repository OIDC remains denied. The admitted exceptions contain exactly five narrowly scoped provider-deployment gateways:

`.github/workflows/sovara-litellm-v2-3-provider-admission.yml`

`.github/workflows/cios-production-lane.yml`

`.github/workflows/luno-observer-provider-binding.yml`

`.github/workflows/deploy-gemini-gateway.yml`

`.github/workflows/federation-automation-gateway-activate.yml`

A sixth OIDC workflow, `.github/workflows/fo-wif-semantic-canary.yml`, remains a bounded owner-only read-only identity verifier and is **not** a provider-deployment gateway.

Each deployment gateway is repository-read-only, immutable-action-pinned, concurrency-bound, restricted to its exact admitted provider identity and trigger contract, and may persist proof only as a GitHub Actions artifact or external append-only record. None has source-write, actions-write or statuses-write authority. Provider execution remains separately proof-gated. The Luno gateway is additionally bounded to the read-only observer contract and does not grant financial write authority. The Gemini gateway is workflow-dispatch-only, obtains Google authority through the admitted keyless OIDC/WIF route, and must prove its Cloud Run service-account ADC identity plus a live Vertex AI semantic-nonce receipt before provider promotion. The Federation Automation gateway is restricted to a dedicated workflow-scoped WIF provider, deploys the private shared automation executor with separate deployer/runtime identities, and leaves provider-admin runtime authority unbound and fail-closed until independently admitted.

These exceptions do not authorize Phoenix Local Bible recovery, do not widen the Phoenix freeze controller beyond their exact paths, and do not transfer cloud authority to any other workflow. A commit-message marker remains an inadequate provider authorization boundary.

## Required Local Bible execution plane

Local Bible recovery may resume only from the private Federation Omega Ops repository or another external, independently governed runner after all of the following are proven:

- the Main Airlock ruleset is provider-active;
- direct updates are rejected before source mutation;
- the executing Local Bible workflow is outside the public source repository;
- OIDC trust is restricted to the exact private repository, branch or environment;
- the service account scope remains read-only and minimum necessary;
- the run produces an immutable artifact and independent readback;
- no credential, P2 content or generated runtime receipt is committed to source.

## Current source-repository contract

- `oidc_workflow_allowlist` contains exactly five provider-deployment gateways plus one owner-only read-only identity verifier;
- Phoenix Local Bible recovery remains excluded from that allowlist;
- the Phoenix freeze controller has no `id-token: write` permission;
- `[BIBLE-REBUILD]` is not an active source-repository trigger;
- the rebuild implementation is packaged capability only;
- no provider rebuild or Library writeback is claimed.

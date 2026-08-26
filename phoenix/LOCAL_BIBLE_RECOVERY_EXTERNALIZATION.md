# Local Bible Recovery execution boundary

Status: `PRIVATE_OPS_PLANE_REQUIRED`

The Local Bible Event 13 recovery implementation remains available at `ops/evidenceops_local_bible_event13_rebuild.py`, together with its source-level privacy, hash-chain and artifact-output tests.

It remains deliberately **not executable from the legacy public source repository**.

## Reason

General source-repository OIDC remains denied. The only admitted exception is the exact SOVARA LiteLLM provider-deployment gateway:

`.github/workflows/sovara-litellm-v2-3-provider-admission.yml`

That gateway is main-only, repository-read-only, immutable-action-pinned, concurrency-bound, restricted to the exact WIF service account, and may persist proof only as a GitHub Actions artifact or external append-only record. It has no source-write, actions-write or statuses-write authority.

This exception does not authorize Phoenix Local Bible recovery, does not widen the Phoenix freeze controller, and does not transfer cloud authority to any other workflow. A commit-message marker remains an inadequate provider authorization boundary.

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

- `oidc_workflow_allowlist` contains exactly one provider-deployment gateway;
- Phoenix Local Bible recovery remains excluded from that allowlist;
- the Phoenix freeze controller has no `id-token: write` permission;
- `[BIBLE-REBUILD]` is not an active source-repository trigger;
- the rebuild implementation is packaged capability only;
- no provider rebuild or Library writeback is claimed.

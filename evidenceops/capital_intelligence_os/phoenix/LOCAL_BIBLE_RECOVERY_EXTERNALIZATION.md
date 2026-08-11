# Local Bible Recovery execution boundary

Status: `PRIVATE_OPS_PLANE_REQUIRED`

The Local Bible Event 13 recovery implementation remains available at `ops/evidenceops_local_bible_event13_rebuild.py`, together with its source-level privacy, hash-chain and artifact-output tests.

It is deliberately **not executable from the legacy public source repository**.

## Reason

The legacy repository does not yet have provider-enforced pull-request admission. Granting `id-token: write` to an active source-repository workflow would allow a direct source update to widen cloud identity use before GitHub rejects or quarantines that update.

A commit-message marker is not an adequate provider authorization boundary.

## Required execution plane

Execution may resume only from the private Federation Omega Ops repository or another external, independently governed runner after all of the following are proven:

- the Main Airlock ruleset is provider-active;
- direct updates are rejected before source mutation;
- the executing workflow is outside the public source repository;
- OIDC trust is restricted to the exact private repository, branch or environment;
- the service account scope remains read-only and minimum necessary;
- the run produces an immutable artifact and independent readback;
- no credential, P2 content or generated runtime receipt is committed to source.

## Current source-repository contract

- `oidc_workflow_allowlist` is empty;
- the Phoenix freeze controller has no `id-token: write` permission;
- `[BIBLE-REBUILD]` is not an active source-repository trigger;
- the rebuild implementation is packaged capability only;
- no provider rebuild or Library writeback is claimed.

# Federation Omega Ops

Private execution plane for approved Federation Omega releases.

This repository is created by the Phoenix cutover program. It contains deployment gateways, schedulers and provider workers only after each module is admitted through an explicit authority contract.

## Permanent rules

- No canonical source development.
- No long-lived provider credentials.
- No self-promotion or self-approval.
- No receipt commits to source branches.
- Runtime proof goes to immutable artifacts or an external append-only evidence store.
- Every external mutation requires provider readback and a rollback path.

The initial repository intentionally contains no active workflow. Execution modules are introduced individually after the Core repository and external Gatekeeper are verified.

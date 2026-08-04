# Federation Omega Ops

Private execution plane for approved Federation Omega releases.

This repository is created by the Phoenix cutover programme. It contains deployment gateways, schedulers and provider workers only after each module is admitted through an explicit authority contract.

## Permanent rules

- No canonical source development.
- No long-lived provider credentials.
- No self-promotion or self-approval.
- No receipt commits to source branches.
- Runtime proof goes to immutable artifacts or an external append-only evidence store.
- Every external mutation requires provider readback and a rollback path.
- An unknown provider outcome is never retried automatically.
- Outcome reconciliation is GET-only and must prove an exact match to the authorised Core and Ops archives before reconstructing a receipt.

The initial repository intentionally contains no active workflow. The packaged provider cutover remains owner-authorised. The packaged outcome reconciler performs readback only and cannot create, update, delete, archive or push provider resources. Execution modules are introduced individually after the Core repository and external Gatekeeper are verified.

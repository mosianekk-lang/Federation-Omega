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
- Provider authority discovery is GET-only and records no credential value.
- Candidate validity, provider authority and owner authorization must all match the same source, Core and Ops bindings before apply.

## Canonical cutover route

`provider_cutover_authority_bound.py` is the only supported apply entrypoint. It requires a hash-valid provider-authority receipt and delegates through the candidate validator, live-source guard, one-time authorization-use state machine and exact provider readback.

`provider_cutover_candidate.py` and `provider_cutover_guarded.py` are internal components and must not be invoked directly. `provider_cutover.py` is a deprecated base coordinator and is not a supported direct apply route.

The initial repository intentionally contains no active workflow. The packaged provider cutover remains owner-authorised. The packaged authority probe and outcome reconciler perform readback only and cannot create, update, delete, archive or push provider resources. Execution modules are introduced individually after the Core repository and external Gatekeeper are verified.

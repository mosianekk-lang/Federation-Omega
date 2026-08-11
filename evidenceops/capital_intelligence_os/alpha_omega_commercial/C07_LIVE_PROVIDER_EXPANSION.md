# C07 Live Provider Expansion

This slice promotes only provider operations supported by fresh, provider-native and reversible evidence.

## Operational scope

The commercial control plane imports the certified reversible adapter register for GitHub, Google Drive, Gmail drafts, Google Calendar, Outlook drafts and Canva transactions. It separately requires fresh Google Cloud Run evidence proving authenticated invocation, exact service readback, health, persistence and rollback.

The Cloud Run proof is bounded to the existing private `fo-transcription-bridge` service in `sov-hybrid-suite`. The workflow does not deploy a new revision or move production traffic. It attaches a temporary zero-allocation tag to the current ready revision, invokes the private tag URL with keyless OIDC authority, verifies persistence, removes the tag and confirms rollback.

## Held boundaries

The following remain unpromoted:

- Gmail and Outlook sending;
- Canva permanent commit;
- Apps Script source mutation;
- payment processing and revenue recognition;
- contracts and external communications;
- self-service SaaS, subscriptions and invoices;
- customer demand, enterprise attestation, partner adoption, external case studies and production-scale proof.

Financial commitments, contracts, external communications, consequential releases and revenue-recognition confirmation remain owner-reserved.

## Proof gate

`prove_live_provider_expansion.py` must produce `LIVE_PROVIDER_EXPANSION_VERIFIED_EXTERNAL_GATES_UNCHANGED` only when all seven bounded provider operations are fresh, the ledger and restart readback pass, and an exact rollback drill restores the pre-drill state.

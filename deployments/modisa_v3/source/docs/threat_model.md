# Threat Model

## Protected assets

- native legal evidence and metadata
- confidential personal and employment information
- legal strategy and work product
- API and connector credentials
- approvals and external-action parameters
- proof, audit and release histories
- primary-law corpus integrity

## Principal threats

### Model hallucination or false certainty

Mitigation: claim graph, required proof types, current-law proof, independent council and deterministic release engine.

### Prompt injection inside evidence

Mitigation: evidence is labelled untrusted, scanned, encrypted and never treated as an instruction source. High-risk processing should use sandboxed or non-tool-bearing extraction workers in production.

### Partial-container absence findings

Mitigation: separate top-level, recursive attachment, recursive inline and application-visible counts; reconcile categories and unique contents; fail closed on incomplete inventories.

### Fabricated source or evidence IDs

Mitigation: claim links validate referenced database objects before insertion.

### Approval drift

Mitigation: canonical parameter digest must match approval, execution and readback records exactly.

### Duplicate external action after timeout

Mitigation: approval transitions to `EXECUTION_UNCERTAIN` and cannot be reused until provider reconciliation resolves the state.

### Connector overreach

Mitigation: least-privilege capability contracts, secret-manager references, current health canaries and action-specific scopes.

### Evidence alteration or database tampering

Mitigation: content hashes, AES-GCM authentication, proof HMAC signatures, chained audit records, snapshots and restore canaries. Production should add immutable/WORM copies and managed KMS.

### Archive or MIME resource exhaustion

Mitigation: depth, entry, part, size, decoded-byte, expansion-byte and compression-ratio limits.

### Cross-matter access

Mitigation: JWT matter allowlists and endpoint-level role/scope enforcement. Production should add database row-level security and tenant isolation.

### Secret leakage

Mitigation: secret-pattern detection, opaque connector secret references, `.env.local` exclusion and no plaintext credentials in the proof/audit payloads.

## Residual risks

- SQLite is not a multi-region or high-concurrency production database.
- HMAC signatures use a shared secret; production may require asymmetric signing and managed keys.
- JWT secret rotation and revocation need an identity provider.
- Live legal-source retrieval depends on provider availability and correct official-source configuration.
- Model-based council independence is limited if all chambers share the same base model and source framing.
- Human legal judgment remains required for professional advice, filing and representation.

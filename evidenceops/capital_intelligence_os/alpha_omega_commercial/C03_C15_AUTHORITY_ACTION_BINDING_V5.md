# C03→C15 Authority Action Binding v5

## Operational defect closed

The anti-rollback v4 control proved that an older provider-native authority snapshot
cannot replace a newer accepted snapshot. One narrower use-time boundary remained:
a snapshot could be cryptographically valid, correctly scoped and fresh, yet had
not been recorded as the latest durable acceptance. The canonical control plane
could therefore treat a candidate as live authority during inherited read paths
before an acceptance receipt existed.

## Smallest complete operational slice

The canonical `AuthoritySnapshotCommercialControlPlane` now separates validation,
acceptance and consequential use:

1. **Validation** proves snapshot integrity, provider evidence, scope and freshness.
2. **Acceptance** writes the snapshot to the hash-linked monotonic ledger.
3. **Use** requires the candidate hash to equal the latest acceptance entry exactly.
4. **Binding** records the exact snapshot, acceptance entry, domains and provider
   evidence hashes on the governed commercial object.

A merely valid candidate does not grant live authority. A superseded candidate does
not grant live authority. Restart reconstructs the acceptance chain and every bound
commercial object retains the exact use-time authority receipt.

## Dependency projection

| Stage | Effective control |
|---|---|
| C03 | Live provider authority requires exact latest durable acceptance |
| C11 | Owner-reserved service requests bind to accepted owner authority |
| C12 | Externally admitted outcome studies bind to accepted customer and owner authority |
| C13 | Quote presentation and live revenue paths bind to accepted owner/payment authority |
| C15 | Succession readback carries durable action-level authority provenance |

## Bound receipt

Each consequential binding contains:

- snapshot ID and SHA-256;
- acceptance sequence and acceptance-entry SHA-256;
- exact authority domains;
- provider evidence SHA-256 per domain;
- binding time and binding SHA-256;
- state `EXACT_LATEST_ACCEPTED_SNAPSHOT`.

Bindings are written into the existing commercial state and hash-linked commercial
ledger. They do not send a quote, execute a contract, process a payment, publish a
case study, operate Cloud Run or advance an external maturity gate.

## Strategy and truth boundary

The service-enabled platform remains first. Self-service SaaS remains held.

Reference and synthetic conformance can prove this control path, but cannot prove
customer demand, a signed customer contract, payment, revenue, subscriptions,
invoices, Cloud Run operation, enterprise assurance, partner adoption, an external
customer case study or production scale. Verified live revenue remains zero.

Financial commitments, contracts, external communications, consequential releases
and revenue recognition remain owner-reserved.

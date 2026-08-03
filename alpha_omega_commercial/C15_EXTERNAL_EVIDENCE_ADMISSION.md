# C15 External Evidence Admission

This control closes the gap between the verified C01–C15 reference platform and the eight external commercial maturity gates without manufacturing market proof.

## Operational slice

The admission controller provides:

- a typed evidence envelope with provider, locator, observation time and SHA-256 provenance;
- gate-specific claim requirements for customer demand, contracts, payment revenue, live cloud operation, enterprise assurance, partner adoption, external case studies and production scale;
- fresh provider-authority checks before any evidence can be admitted;
- explicit owner confirmation for contracts, payment recognition, partner adoption and customer-case-study publication;
- rejection of internal, reference-provider, synthetic and mock-conformance evidence;
- evidence freshness limits and conflict detection;
- an append-only hash-linked decision ledger;
- restart-safe state readback and deterministic maturity projection;
- no maturity promotion unless every required gate has admitted external provider-native evidence.

## Current provider boundary

- GitHub Actions source, CI and artifact authority: verified.
- Google Drive document release readback: verified for the C15 release document.
- Google Drive binary artifact transfer: blocked at file egress.
- Cloud Run: blocked because no fresh provider-native authority or execution receipt exists.
- Payment provider: blocked because no fresh provider authority or settled receipt exists.
- Customer, partner and assurance gates: market or external attestation proof required.

The Google Drive release proves publication and readback of the commercial receipt. It does not establish customer demand, a contract, payment, revenue, Cloud Run operation, enterprise assurance, partner adoption, an external case study or production-scale operation.

## Owner authority

Financial commitments, contracts, external communications, consequential releases and revenue-recognition confirmation remain owner-reserved. The controller cannot bypass those boundaries.

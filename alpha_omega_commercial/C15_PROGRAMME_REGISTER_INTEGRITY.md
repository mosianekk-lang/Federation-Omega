# C15 Programme Register Integrity

## Defect

The canonical C15 artifact and Google Drive release prove `CANONICAL_RECEIPT_INTEGRITY_VERIFIED`, but the machine-readable `programme.json` still declared `C15_SELF_CONSISTENCY_READBACK_AND_ROLLBACK_PROOF_REQUIRED` and kept the C15 gate marked active. That stale register could cause later automation to repeat completed work or misreport commercial maturity.

## Operational control

The programme register now records the verified PR, merge, workflow run, artifact ID and digest, integrity-receipt hash, and Google Drive release readback. A provider-executed verifier compares the register to the freshly generated C10-C15 maturity, commercial receipt and integrity receipt.

The verifier rejects:

- missing or reordered C01-C15 stages;
- dependencies that point forward or to unknown stages;
- a stale C15 integrity state;
- divergence between programme and artifact canonical status;
- unproven external-gate promotion;
- loss of owner-reserved financial, contractual, communication, release or revenue authority;
- any revenue or Cloud Run claim not present in provider evidence;
- regression from service-enabled platform priority to unsupported self-service SaaS.

## Promotion gate

Promotion requires the complete C01-C15 regression suite, receipt reconciliation, programme-register proof, repository leak guard and Superior Logic CI to pass. The proof package must contain `programme-register-integrity.json`.

## Truth boundary

This control repairs canonical metadata only. It does not prove customer demand, price acceptance, a signed contract, payment-provider revenue, Cloud Run operation, enterprise attestation, partner adoption, an external customer case study, or production-scale evidence. Financial commitments, contracts, external communications, consequential releases and revenue recognition remain owner-reserved.

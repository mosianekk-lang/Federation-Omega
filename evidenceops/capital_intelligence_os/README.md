# EvidenceOps Capital Intelligence OS — v1.0.0-rc5

CIOS rc5 is an **internal product-completion candidate** layered on the existing `PROVIDER_BINDING_READY` rc4 baseline.

It does not create a new framework. It closes a concrete product gap: the existing vault, diligence and runtime components can now operate as one authenticated deal-document journey.

## rc5 product route

`tenant auth → document ingestion → integrity hash → parser → classified vault → dedupe/version chain → search → diligence progress → digest-bound workspace export`

The reference runtime supports bounded ingestion for:

- UTF-8 text and CSV;
- JSON;
- RFC822 email;
- DOCX;
- XLSX;
- PDF only when explicit external extracted text is supplied.

PDF without an extraction source fails closed with `PDF_TEXT_EXTRACTION_REQUIRED`. The bytes are still integrity-hashed when accepted, but externally supplied extraction is labelled as such rather than silently promoted to independently verified text.

## Runtime surface

Authenticated/default-deny routes now include:

- `GET /health`
- `GET /ready`
- `GET /v1/verify`
- `POST /v1/events`
- `POST /v1/documents`
- `POST /v1/search`
- `GET /v1/diligence`
- `GET /v1/workspace`

Trade, orders, transfers, withdrawals, payments, signing and regulatory-filing route families remain constitutionally unexposed.

Runtime roles are configured at process construction, not accepted from caller-controlled headers. The default reference role set can process confidential deal material but cannot self-promote into clean-team, restricted/MNPI, privileged or admin access. Production enterprise identity/ABAC remains a provider qualification gate.

## Evidence safeguards

- tenant isolation;
- content SHA-256;
- exact duplicate detection;
- logical document version chains;
- information-class access policy;
- metadata-only search results;
- workspace export excludes raw/extracted document text;
- diligence completeness derives from accessible ingested document types;
- export bundle is digest-bound;
- final transaction decision remains human-required;
- external financial effects remain disabled.

## Qualification

The focused rc5 acceptance suite is wired into the existing Federation Omega Airlock through a `test_phoenix_provider_cutover_v3*.py` wrapper. The release verifier first executes the frozen rc4 baseline, then proves rc5 ingestion/workspace invariants separately.

Until exact-head Airlock and Public Repository Leak Guard admission complete, rc5 remains an implementation candidate. After admission it advances internal product completeness, **not provider production maturity**.

## Still outside this release

- private provider deployment/readback;
- production malware/DLP/object-storage/VDR services;
- enterprise IdP/MFA/KMS binding;
- independently qualified PDF/OCR pipeline;
- model/financial-engine calibration against representative transaction outcomes;
- live pilot/user outcomes;
- autonomous legal, transaction, payment or trading authority.

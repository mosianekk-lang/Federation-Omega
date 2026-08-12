# Production Readiness Register — v1.0.0-rc5

## Current maturity

Provider maturity remains **`PROVIDER_BINDING_READY`**.

Internal product state is **`INTERNAL_COMPLETION_CANDIDATE`** pending exact-head repository admission of rc5.

These states are intentionally separate. More complete product behavior does not establish cloud deployment, enterprise identity, security-provider binding or production qualification.

## Completed / implemented source-side gates

- synthetic full-deal MVP journey;
- machine-enforced production qualification gate;
- harmless A1 provider canary contract;
- provider-neutral production data-plane preflight;
- persistent authenticated local/provider-candidate runtime contract;
- tenant-scoped evidence vault with hashing, duplicate detection and version chains;
- bounded document ingestion for text, CSV, JSON, RFC822 email, DOCX and XLSX;
- PDF ingestion that fails closed unless explicit external extracted text is supplied;
- runtime-backed document search, diligence completeness and digest-bound workspace inventory;
- static runtime-role binding rather than caller-controlled role headers;
- A1 authority ceiling and private→market/live-financial firewall preserved.

## rc5 internal product qualification

The new document-to-workspace route is intentionally a composition layer over existing CIOS components:

`AUTHENTICATED TENANT → DOCUMENT BYTES → HASH/PARSER → CLASSIFIED VAULT → DEDUPE/VERSION → SEARCH → DILIGENCE STATUS → WORKSPACE EXPORT`

The workspace export exposes metadata/provenance identifiers and diligence state, not raw document content or extracted text. It always marks the transaction decision as human-required and has no external financial effect.

Supported direct parsers at this maturity are stdlib/reference implementations. They are not a substitute for a production malware/DLP/OCR/document-conversion pipeline. PDF bytes are integrity-hashed, but PDF text must come from an explicit external extraction route until a separately qualified parser is bound.

## Provider data-plane preflight

A candidate provider environment must still supply fresh healthy evidence for runtime identity, enterprise IdP/MFA, tenant isolation, encryption/KMS, malware scanning, DLP/redaction, immutable audit, observability and rate/abuse controls. Private-data residency/retention and market-data entitlement/freshness remain conditional requirements when those domains are enabled.

The preflight compiles accepted probes into validated `ProviderEvidence` objects. It does not itself establish production qualification.

## Exact remaining provider path

1. bind an authorised private CIOS execution target;
2. materialise/read back the exact admitted CIOS source/revision;
3. execute the harmless provider canary using persistent storage;
4. keep non-secret provider/runtime receipts outside the public source plane;
5. run the production data-plane preflight over identity, storage, scanning, audit, observability and entitlement adapters;
6. obtain independent health, persistence, rollback, backup/restore, vulnerability and incident/DR evidence;
7. feed the complete fresh provider evidence set into `ProductionQualificationGate`;
8. promote only if the gate returns `PRODUCTION_VERIFIED`.

## Internal work that should continue while provider execution is blocked

Provider authority does **not** freeze the product. After rc5 admission, the next internal lanes are:

- scientific calibration/benchmarking of valuation, QoE, diligence, target ranking and market-intelligence outputs;
- failure, security and cross-tenant adversarial testing;
- one polished five-minute synthetic acquisition demonstration with exportable decision artefacts;
- pilot/value scorecard and proof-safe case study.

## Not claimed

- provider production deployment;
- production VDR/security certification;
- enterprise IdP/KMS binding;
- licensed market-data operation;
- independently qualified PDF/OCR extraction;
- autonomous transaction approval, signing, payments or live trading.

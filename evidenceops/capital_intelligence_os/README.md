# EvidenceOps Capital Intelligence OS — v1.0.0-rc7

CIOS rc7 continues Ω-FINISH by hardening the already-admitted rc6 product/qualification stack rather than adding new architecture.

## Current states

- Internal product route: **rc5 admitted**
- Scientific state: **`SYNTHETIC_DETERMINISTIC_QUALIFIED`**
- Portfolio state: **`PORTFOLIO_DEMONSTRABLE_CANDIDATE`**
- Ingestion security state: **`INGESTION_RESOURCE_HARDENED_CANDIDATE`**
- Provider maturity: **`PROVIDER_BINDING_READY`**
- Production claim: **false**

## rc7 security objective

The rc5 document route bounded uploaded bytes but DOCX/XLSX are ZIP containers, so a small upload could otherwise expand into a much larger decompressed/parser workload. rc7 adds fail-closed OOXML resource controls before XML parsing.

The bounded parser now checks:

- maximum archive entry count;
- duplicate and unsafe archive names;
- encrypted entries;
- maximum per-entry uncompressed size;
- maximum total declared uncompressed size;
- suspicious compression ratios;
- DTD/entity declarations before XML parse;
- DOCX paragraph count;
- XLSX worksheet count;
- XLSX shared-string count;
- XLSX non-empty cell count;
- malformed or missing required archive/XML structures.

Normal DOCX/XLSX extraction remains supported. The security revision is inspectable through the parser identities `DOCX_STDLIB_V2_BOUNDED` / `XLSX_STDLIB_V2_BOUNDED` and bounded metadata including archive-entry count, declared uncompressed bytes and maximum compression ratio.

## Proof route

A focused 12-test adversarial suite exercises normal compatibility plus entry-count, path, duplicate-name, compression-ratio, per-entry, total-uncompressed, encryption, DTD/entity, worksheet-count and malformed-archive cases. The suite is bound into the existing Federation Omega Airlock through `test_phoenix_provider_cutover_v3_cios_ingestion_hardening_rc7.py`.

The rc7 cumulative verifier first requires rc6 to remain green, then verifies normal bounded DOCX operation and fail-closed archive controls. Provider maturity and consequential authority remain unchanged.

## Retained product and authority chain

`THESIS → TARGET → DOCUMENT INGESTION → EVIDENCE/CONTRADICTIONS → DILIGENCE → QoE → VALUATION → PUBLIC-MARKET CONTEXT → COUNCIL → HUMAN DECISION → INTEGRATION → OUTCOME LEARNING`

Authenticated product routes remain default-deny. Trade, orders, transfers, withdrawals, payments, signing and regulatory-filing route families remain unexposed.

## Truth boundary

rc7 is internal parser/resource hardening. It is not a production VDR, malware/DLP service, enterprise IdP/MFA/KMS proof, historical-deal calibration, real pilot outcome or provider deployment.

## Next automated completion path after rc7

1. exact-current-main recut and Airlock/Leak Guard/Bubbles admission;
2. merge and canonical readback;
3. materialize the rc6/rc7 synthetic demonstration pack for user inspection;
4. build a provenance-controlled public/historical transaction calibration corpus;
5. measure model error/calibration and false-positive/false-negative behavior;
6. prepare a consenting-user pilot/value scorecard;
7. keep Sparks' private-provider canary lane isolated until external authority becomes available.

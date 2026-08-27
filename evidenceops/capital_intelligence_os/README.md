# EvidenceOps Capital Intelligence OS — v1.0.0-rc8 production-lane candidate

CIOS rc8 adds the complete source-side production lane while keeping live provider claims evidence-bound.

## Current states

- Internal product route: **rc5 admitted**
- Scientific state: **`SYNTHETIC_DETERMINISTIC_QUALIFICATION_CANDIDATE`**
- Portfolio state: **`PORTFOLIO_DEMONSTRABLE_CANDIDATE`**
- Provider maturity: **`PROVIDER_EXECUTION_READY`**
- Production claim: **false**

## rc8 production lane

- `PostgresStateStore` implements tenant-scoped events, claims, dependencies, learning, idempotency and transactional state over a bounded Psycopg pool.
- `PostgresAuditLedger` uses a distinct database URL, an advisory-locked hash chain and triggers that reject update/delete mutations.
- Production configuration requires distinct state/audit URLs, exact source SHA parity, a fixed service identity, tenant and runtime user, and a pool of at most sixteen connections.
- Cloud Run IAM identity remains in `Authorization`; the application secret is separately supplied through `X-CIOS-Token` and is never returned.
- The v4 Federation operator admits only exact CIOS project, region, service, service account, Cloud SQL, secret-name and digest-pinned image bindings.
- Managed persistence preflight requires PostgreSQL, the exact region, backup enabled, PITR enabled, transaction-log retention, auto-resize, deletion protection and a successful backup.
- Deployment preserves the baseline traffic map and binds the candidate only to a zero-percent tag.
- The semantic canary verifies health, readiness, managed persistence, append-only audit and an idempotent event replay.
- Rollback restores the exact baseline active traffic and retains the candidate at zero traffic for a recovery canary.
- Promotion remains separately gated and requires immutable deployment, canary and rollback receipts.

The executable provider lane is `.github/workflows/cios-production-lane.yml`. It admits source on pull requests and pushes, and permits provider mutations only from the exact `main` SHA through keyless WIF plus the exact dispatch confirmation.

## rc7.1 production-convergence controls

- OOXML ZIP entries are streamed under declared and actual decompression budgets.
- UTF-16/32, NUL-bearing XML, DTDs and entities fail closed across the full bounded payload.
- XML elements, depth, attributes, text, paragraphs, worksheets, shared strings and cells are bounded.
- The provider candidate now exposes exactly four routes with a 256,000-byte request ceiling; document/search/workspace routes are disabled.
- Its bearer credential maps to one configured tenant and runtime principal; caller identity overrides are denied.
- SQLite request handling is serialized as a containment control. This does not qualify SQLite for horizontal production.
- Production evidence must bind the exact provider/project/region/environment/service/tenant/source/image target and pass an injected independent attestation verifier.
- Future, naive, stale, conflicting, failed, forged, self-attested or unregistered evidence blocks promotion.
- Duplicate document content cannot be used to downgrade classification or disclose restricted metadata.
- The provider canary executes the current cumulative release verifier rather than the obsolete rc2 verifier.

The rc8 source cut does **not** claim live production. Fresh provider-native Cloud SQL recovery, digest/revision, semantic canary, rollback/recovery, promoted traffic, observability and supply-chain receipts remain hard gates. Malware/DLP and resource-isolated parsing remain mandatory before document routes can ever be enabled in the provider runtime.

The states are intentionally independent. A strong synthetic qualification or portfolio demonstration cannot be used as evidence of provider deployment or real-world investment performance.

## rc5 product route retained

`tenant auth → bounded document ingestion → integrity hash → classified vault → dedupe/version → search → diligence → digest-bound workspace export`

Reference ingestion supports text/CSV, JSON, RFC822 email, DOCX and XLSX. PDF remains fail-closed unless an explicit external extracted-text source is supplied and labelled.

## rc6 qualification court

`InternalQualificationCourt` applies transparent independent expected values and counterfactual checks across:

- DCF analytic value;
- WACC monotonicity;
- terminal-growth monotonicity;
- IRR and MOIC analytic values;
- enterprise-to-equity bridge;
- evidence-thresholded QoE adjustments;
- working-capital normalisation;
- debt-like item inclusion;
- diligence empty/partial/full boundaries;
- acquisition-thesis hard gates;
- final-decision/live-order/private-to-market authority controls;
- full synthetic journey invariants;
- missing-evidence counterfactual;
- off-thesis counterfactual;
- deterministic replay of economic/decision fields.

Every check is fatal for the synthetic qualification receipt. The receipt is deterministic and digest-bound.

### Scientific truth boundary

This qualification proves transparent deterministic/synthetic behavior only. It is **not** historical-deal calibration, investment-performance validation, accounting assurance, legal/tax advice or production provider proof.

## rc6 proof-safe demonstration pack

`CIOSDemoPackBuilder` will generate a complete synthetic portfolio bundle only when both the synthetic MVP journey and qualification court pass:

- `manifest.json`
- `decision_brief.json`
- `qualification_receipt.json`
- `case_study.md`
- `dashboard.html`
- `pack_receipt.json` when written to disk

The pack is explicitly labelled `PUBLIC_SAFE_SYNTHETIC_DEMONSTRATION`. It preserves visible evidence contradictions, requires human final decision authority, denies live orders and denies private-M&A-to-public-market export.

The case study may only describe implemented/proven software behavior. It explicitly disclaims real customer, company, transaction, investment-performance or production claims.

## Local runtime authority remains unchanged

Authenticated/default-deny product routes remain:

- `GET /health`
- `GET /ready`
- `GET /v1/verify`
- `POST /v1/events`
- `POST /v1/documents`
- `POST /v1/search`
- `GET /v1/diligence`
- `GET /v1/workspace`

Trade, orders, transfers, withdrawals, payments, signing and regulatory-filing route families remain unexposed.

The provider candidate is intentionally narrower and exposes only:

- `GET /health`
- `GET /ready`
- `GET /v1/verify`
- `POST /v1/events`

## Next finish gates after rc6

Without waiting for Google/provider authority, CIOS should next pursue:

1. generate/read back the exact-source demo pack as an actual user-visible artifact;
2. build representative historical/public transaction calibration datasets with explicit source/licensing provenance;
3. compare deterministic reference models against independently sourced deal/financial outcomes;
4. add false-positive/false-negative and calibration-error reporting;
5. conduct product pilot/value measurement with real consenting users when available.

The provider lane is now executable but still proof-gated:

`admitted main → v4 operator → managed persistence readback → zero traffic → semantic canary → rollback → recovery canary → promotion → provider-native production receipt`

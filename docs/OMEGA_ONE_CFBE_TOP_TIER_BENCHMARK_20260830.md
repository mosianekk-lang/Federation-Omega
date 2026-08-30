# Omega-One CFBE top-tier engineering benchmark

Date: 2026-08-30

Scope: current Federation main at 73963da2, Omega-One v0.8.5 candidate lineage at
b1ccae68, and this isolated v0.8.6 purpose branch. This is a practice and source
benchmark, not a claim that Omega-One is globally faster or better than any company.

## Truth boundary

- Existing Omega-One evidence is strong at architecture, deterministic source, hosted
  admission for a bounded subset, maturity compilation, standards projection, and
  zero-dilution preservation.
- The earlier H2-P scenario recovered 100/100 at a modeled/local 2.308x factor, but
  duplicate final proof receipts violated the exactly-once quality gate. That factor is
  not promoted.
- CFBE Generation 6 has 0/30 required cold-replayable paired observations at the start
  of this change. No provider, deployment, soak, owner-value, or global-superiority
  claim follows.
- The private awareness manifest names an older GitHub head than current main; current
  public source is the runtime authority for this branch until reconciliation.

## Primary-source practice benchmark

| Practice | Primary standard | Baseline assessment | v0.8.6 additive response | Promotion proof still required |
|---|---|---|---|---|
| Delivery performance | DORA five software-delivery metrics | Partial; repository signals exist but Omega-One has no single compiler | compile_dora_metrics covers lead time, frequency, recovery time, failed deployment rate, and rework rate | Populate from independently read deployment events |
| Reliability governance | Google SRE SLOs and error budgets | Partial; promotion courts exist without a compact runtime burn gate | SloErrorBudget fails closed below the sample floor and when availability or latency budget is exhausted | Hosted observations and approved SLOs |
| Cascading-failure control | Google SRE load shedding and capacity guidance | Gap in the v0.8.5 package | Bounded AIMD concurrency plus priority shedding | Load-to-failure campaign and recovery readback |
| Retry safety | AWS Builders Library retry/backoff/jitter guidance | Critical gap exposed by duplicate receipts | Finite retry tokens, capped exponential backoff, deterministic jitter, and no blind retry for UNKNOWN outcomes | Provider-specific timeout and idempotency validation |
| Exactly-once recovery | Federation receipt/idempotency lineage | H2-P blocker | Thread-safe content-addressed canonical finalizer; identical replay returns the original receipt, recovered identical attempts can collapse as one verified batch, and conflicts fail closed | Segmented H2 plus 10,000-mission soak |
| Champion/challenger measurement | CFBE paired empirical contract | 0/30 paired campaign | Minimum-30 cold observed pairs, semantic oracle parity, quality floor, p95 guard, exact receipt gate | Real host binding and 30 independent pairs |
| Observability interoperability | OpenTelemetry semantic conventions | Strong source-level OTel projection | Adds measurement, authority, and truth-boundary attributes | Collector/export readback |
| Adaptive capacity | Kubernetes HPA dampened metric control | Design-level only | Bounded adaptive limit with stabilization and declared min/max | Load-test calibration against real saturation signals |
| Secure development | NIST SSDF 1.1 | Partial through repository courts and leak guard | No new authority or credential path; conflicting state and tampered snapshots fail closed | Full SSDF practice mapping and hosted security checks |
| Supply-chain integrity | SLSA v1.2 build track | Partial; provenance references exist for v0.8.5 | Deterministic source/test evidence remains separable from hosted provenance | Signed hosted provenance for this exact head |
| Guarded integration | GitHub rules, code scanning, merge queue | Repository-governed; no new workflow requested | Existing ProofOS selector extended to cover v0.8.6 | Exact-head hosted checks and independent PR readback |

## CFBE-ranked harvest

The validated 50-horizon twin ranked:

1. PAIRED_CFBE_BENCHMARK_AND_SLO_GATE — utility 1.70.
2. EXACTLY_ONCE_RECOVERY_CORE — utility 1.68.
3. BOUNDED_ADAPTIVE_PERFORMANCE_CONTROL — utility 1.52.

NEW_HOSTED_WORKFLOW_AND_RULESET ranked lower because it duplicates existing governance,
creates more operational burden, and does not close the observed proof-finalization
blocker.

## Capability mapping

| Omega capability | Exact additive mechanism | Current claim ceiling |
|---|---|---|
| CAP-026 Microbenchmark Sandbox Generator | Deterministic paired campaign compiler | Component tested locally; full sandbox generator remains DESIGNED |
| CAP-036 Adaptive Rate-Limit and Backoff Controller | Retry tokens, capped backoff/jitter, bounded concurrency | DETERMINISTIC_TESTED locally; hosted CI pending |
| CAP-045 Champion-Challenger Tournament Evaluator | Identical-oracle baseline/candidate court | DETERMINISTIC_TESTED locally; hosted CI pending |
| CAP-047 Empirical Convergence and Hallucination Suppressor | Semantic, quality, p95, and receipt promotion gates | DETERMINISTIC_TESTED locally; hosted CI pending |
| CAP-061 Content-Addressed Store with SHA-256 Deduplication | Canonical receipt and snapshot hashes | Component tested locally; full CAS remains DESIGNED |
| CAP-064 Atomic Release Promotion Gate | SLO/error-budget release decision | Component tested locally; full release gate remains DESIGNED |
| CAP-076 Replayable Decision Lineage Audit Trail | Recoverable intent/receipt snapshots | Component tested locally; full lineage capability remains DESIGNED |
| CAP-088 Live System Telemetry and Health Dashboard | DORA/SLO/campaign snapshots plus OTel attributes | Component tested locally; dashboard remains DESIGNED |

No capability is deleted, narrowed, marked deployed, or promoted by umbrella inheritance.

## Observed local campaign

The same 30-pair workload used 200 operations per pair and four recovered attempts per
operation. Alternating execution order reduced simple warm-order bias.

| Candidate | Median factor | p95 latency ratio | Canonical receipts | Peak memory | Decision |
|---|---:|---:|---:|---:|---|
| V1 sequential full rehash | 0.757x | 1.234 | 200 vs 800 | 156,441 vs 622,766 bytes | HELD |
| V2 prehashed sequential replay | 0.974x | 1.022 | 200 vs 800 | 154,987 vs 622,766 bytes | HELD |
| V3 prehashed recovered-replay batch | 2.031x | 0.573 | 200 vs 800 | 145,776 vs 622,766 bytes | QUALIFIED_LOCAL |
| V3 in-source replication | 2.067x | 0.528 | 200 vs 800 | 145,776 vs 622,766 bytes | QUALIFIED_LOCAL |

The two V3 measurement digests are
sha256:51ff91ceb7617d3c8f7c586faa6634a0558368abfe6718393fe5a77d1813d457
and sha256:0bf64afc773b68096d26331f8d5ea77b846b79de6c2d93ba1446c57197bb7834.
It proves only this local observed microbenchmark. It does not prove provider execution,
general workload superiority, deployment maturity, soak, or owner value.

## Next proof sequence

1. Run the v0.8.5 and v0.8.6 deterministic courts and the selected ProofOS manifest.
2. Run full repository, security/leak, and anti-dilution verification.
3. Publish only a draft PR from the exact current-main purpose branch.
4. Bind the existing approved no-effect host and run at least 30 cold-replayable
   identical-oracle pairs with exactly one canonical receipt per candidate mission.
5. If pair quality is perfect, run segmented H2, then a 10,000-mission soak. Any
   semantic, p95, receipt, SLO, or provenance regression holds promotion.

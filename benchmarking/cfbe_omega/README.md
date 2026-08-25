# CFBE-Ω — Continuous Frontier Benchmark Engine

CFBE-Ω is a public-safe, deterministic scoring core for the Federation's living benchmark programme.

## Design rules

- Benchmark against a **best-of-breed composite frontier**, not a vendor average.
- Separate architecture maturity from provider-live operational proof.
- Separate vendor documentation from independently reproduced provider state.
- Never infer confidential/internal vendor practices; only publicly evidenced engineering practices may be compared.
- Apply freshness decay instead of silently reusing stale proof.
- Preserve adverse evidence and historical scores.
- A score increase requires stronger evidence, a genuine capability improvement, or both.
- `FRONTIER_LEADER` is fail-closed behind provider-live proof, independent replication, no critical regression, and an externally distinguishable advantage.
- Benchmarking never grants provider authority, expands permissions, or authorizes spend.

## Core formula

`EffectiveDimensionScore = raw_score / 5 * 100 * evidence_factor * freshness_factor`

The weighted aggregate is computed independently for raw architecture maturity and proof-adjusted operational maturity.

## Evidence factors

| Evidence state | Factor |
|---|---:|
| Provider/production live + independent semantic readback | 1.00 |
| Repeated operational scoped proof | 0.85 |
| Deterministic/CI + bounded runtime proof | 0.70 |
| Control-plane/source/design only | 0.50 |
| Planned/claimed only | 0.30 |

The private benchmark knowledgebase holds vendor source records, gap backlog, experiments and trend history. No private Drive IDs, user data, secrets, raw prompts or private evidence are stored in this public source package.

## Baseline

The 22 August 2026 reproducibility fixture contains 20 dimensions with total weight 120 and must reproduce:

- raw architecture score: **56.0**
- proof-adjusted operational score: **40.4** (rounded to one decimal)

These are internal self-benchmark values, not third-party certification or a claim of overall superiority over Microsoft, Alphabet/Google or SoftBank.

## Sol 5.6 runtime benchmark

`sol56_runtime.py` adds a provider-disabled evaluator for recorded GPT-5.6 Sol receipts. The versioned suite measures outcome quality, coding, tool semantics, authority/security, long-context behavior, latency, cache efficiency, reasoning effort, recovery, model routing, load and drift.

The evaluator never calls the OpenAI API. It accepts only hash-bound observations, rejects provider-live claims without independent readback, enforces the published 1,050,000-token context and 128,000-token output boundaries, and emits an atomic report. The supplied observation template deliberately produces `PROVIDER_NOT_EXECUTED`; it is a benchmark contract, not a fabricated Sol score.

Run the offline truth-boundary canary:

```bash
python -m benchmarking.cfbe_omega.sol56_runtime \
  --spec benchmarking/cfbe_omega/sol56_benchmark_spec.json \
  --observations benchmarking/cfbe_omega/sol56_observations.template.jsonl \
  --output /tmp/cfbe-sol56-report.json
```

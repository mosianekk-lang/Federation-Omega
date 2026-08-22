# Federation Omega Frontier Benchmark Fabric

This package benchmarks verified JARVIS work against a **frontier envelope** assembled control by control from current official Microsoft, Alphabet/Google, SoftBank and standards-owner sources. It does not pretend that one company is best at everything, and it does not infer private internal practices from marketing or careers pages.

## What the fabric does

1. Maintains a reviewed registry of official HTTPS sources and an explicit host allowlist.
2. Maps those sources to 52 controls across agent orchestration, knowledge, security, AI risk, observability, SRE, platform engineering, delivery, supply chain, data, production operations, FinOps and team capability.
3. Scores the verified JARVIS evidence corpus on a proof ladder:
   `ABSENT → DESIGNED → SOURCE_IMPLEMENTED → TESTED → PROVIDER_BOUND → PRODUCTION_PROVEN`.
4. Separates raw capability alignment from evidence-adjusted alignment and production-proof coverage.
5. Refreshes official sources on a daily schedule, records hashes and freshness, and creates review proposals when content changes.
6. Writes snapshots, reports and terminal receipts to an Actions artifact. The workflow has read-only repository permissions and cannot commit, push, tag, release or promote a control.
7. Applies the separate canonical R0–R6 operational readiness standard, including strict-minimum release profiles, proof-gated promotion, automatic demotion and a deterministic backlog.

## Trust and update model

The reviewed source registry and control catalog live in source control. Scheduled runs fetch only allowlisted public pages, validate redirects and public DNS, cap response sizes, strip executable page content, hash the normalized text and report deltas. Changed pages create `HUMAN_REVIEW_REQUIRED` proposals. They do **not** change benchmark targets or JARVIS evidence automatically.

This two-lane model prevents benchmark poisoning:

- **Automated evidence lane:** read, hash, diff, assess freshness and produce immutable run artifacts.
- **Reviewed knowledge lane:** a purpose-branch pull request updates sources, mappings or maturity only after evidence review.

Vendor press releases and careers pages have lower comparator confidence. Their claims can identify a practice worth examining, but they cannot establish a private internal capability or promote JARVIS maturity.

## Run locally

Evaluate the reviewed corpus without network access:

```bash
python -m benchmark_fabric.frontier_benchmark.cli \
  --output /tmp/jarvis-frontier-benchmark \
  --as-of 2026-08-22T13:00:00Z
```

Refresh all official sources and emit the knowledgebase artifact:

```bash
python -m benchmark_fabric.frontier_benchmark.cli \
  --output /tmp/jarvis-frontier-benchmark \
  --refresh-official-sources
```

Run the regression suite:

```bash
python -m unittest discover -s tests -p 'test_frontier_benchmark.py' -v
```

Evaluate operational readiness without network access:

```bash
python -m benchmark_fabric.readiness --output /tmp/jarvis-readiness
```

The readiness result is deliberately separate from the 0–5 frontier control score. Capability alignment, architecture alignment and ordinal operational readiness must never be averaged or substituted. See `docs/JARVIS_READINESS_STANDARD_V1.md`.

## Artifact contract

Each run emits:

- `benchmark-report.json` and `benchmark-report.md`;
- `run-summary.json` with one terminal state;
- `knowledgebase/manifest.json`;
- `knowledgebase/review-proposals.json`;
- `knowledgebase/snapshots/<source>.json` and normalized `.txt` snapshots when refresh is enabled.

Runtime artifacts are deliberately excluded from the source repository. The scheduled workflow retains them as immutable GitHub Actions artifacts for 90 days; a separate admitted append-only execution plane may retain them longer without granting this workflow source-write authority.

## Current proof boundary

The 22 August 2026 baseline includes verified main-branch work, connected records and explicitly labeled source/test-verified open pull requests. No current JARVIS control is scored as `PROVIDER_BOUND` or `PRODUCTION_PROVEN`: the latest Gemini canary failed because the provider credential binding was absent, and the stronger JARVIS/GCP stack remains open and disabled.

Under the stricter release-profile rule, benchmark operations are currently R3 and the provider-runtime and full-Federation profiles are R0. Those states are the minimum across critical dependencies, not averages; they cannot be raised until every blocking proof gate is satisfied.

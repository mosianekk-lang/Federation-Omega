# The RESOLVE Method

**RESOLVE** means **Resilient Evidence Systems Orchestration, Verification, Learning and Execution**.

## Objective

Complete evidence-processing work despite provider limits, stale automation, failed credentials, file-size ceilings, runtime limits, or unavailable execution surfaces—without weakening provenance, completeness, or verification.

## Seven operating stages

1. **R — Register truth and invariants**
   - Freeze the source identity, expected size, hashes, authority, and non-negotiable completion rule.
   - Separate verified facts from assumptions.

2. **E — Enumerate execution lanes**
   - Discover available providers, runtimes, connectors, local tools, queues, and manual-safe fallbacks.
   - Rank lanes by authority, capacity, reliability, cost, and proof quality.

3. **S — Substitute intelligently**
   - When a lane fails, classify the failure and switch to the next admissible lane.
   - Never repeat a known failure without a changed condition.

4. **O — Observe every external effect**
   - Require receipts, provider IDs, sizes, timestamps, hashes, status readback, and logs.
   - Treat queue insertion, code creation, and deployment claims as incomplete until execution is observed.

5. **L — Learn and build capability**
   - Convert each novel constraint into a reusable adapter, rule, test, transport strategy, or circuit breaker.
   - Persist failure fingerprints and successful recoveries.

6. **V — Verify independently**
   - Re-download or re-read published outputs through a path independent from the writer.
   - Reconstruct multipart objects, recalculate hashes, run format integrity tests, and reconcile counts.

7. **E — Exit only on exact closure**
   - Write a completion receipt only when all mandatory gates pass.
   - Otherwise report the precise remaining gate; never convert partial completion into success language.

## Core doctrines

- Evidence before assertion.
- Append-only operational ledger.
- No deletion or mutation of original evidence.
- Deterministic identities and idempotent retries.
- Segmentation must preserve exact reconstruction.
- Every failure must produce a reusable lesson.
- Provider success is not evidence integrity; independent readback is.
- A job is not complete until its declared completion contract is satisfied.

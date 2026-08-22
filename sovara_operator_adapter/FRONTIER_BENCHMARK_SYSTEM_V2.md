# SOVARA Continuous Frontier Benchmark System v2

State: `PRODUCTION_FOUNDATION_PROVEN / OWNER_COCKPIT_V4_LIVE / DAILY_OWNER_CONTROL_ENABLED`

## What it measures

The engine compares SOVARA with Microsoft, Alphabet, SoftBank Group and relevant specialist peers across 20 weighted dimensions. The competitor field is a *frontier envelope*: the strongest current documented result in each dimension, not a fictitious single company that owns every leading capability.

Every system retains three separate measures:

1. **Capability strength** — what the reviewed evidence establishes the system is designed to do.
2. **Operational maturity** — what has been executed or publicly evidenced at a comparable proof level.
3. **Evidence confidence** — source tier multiplied by freshness, weighted across dimensions.

For dimension scores (s_d\in[0,5]) and weights (w_d) summing to 100:

\[
\text{axis score}=\frac{\sum_d s_d w_d}{5}
\]

The confidence-adjusted capability is informative only:

\[
\text{adjusted capability}=\text{capability}\times\frac{\text{evidence confidence}}{100}
\]

It is never used to erase the separate maturity axis or to authorize a superiority claim.

## Current 22 August 2026 result

| Portfolio | Capability | Operational maturity | Evidence confidence |
|---|---:|---:|---:|
| SOVARA / Kim DataVerse | 90.2 | 71.0 | 99.42 |
| Alphabet / Google Cloud | 89.8 | 43.2 | 85.80 |
| Microsoft | 85.8 | 42.4 | 83.42 |
| AWS AgentCore | 72.0 | 35.2 | 75.36 |
| SoftBank Group | 60.2 | 33.2 | 76.86 |
| NVIDIA Omniverse | 44.6 | 25.0 | 51.60 |

The best-of-market frontier envelope is **93.6**. SOVARA has four critical documented capability gaps: durable execution, least-authority identity, deployment flow, and change stability/recovery. Its digital-twin design reaches the documented frontier, but its Gemini-side operational proof still trails the publicly documented leader maturity. This is a proof gap, not a missing design.

These are bounded architecture assessments from the recorded propositions. Vendor public pages are not independently operated tests, and private internal practices remain `UNKNOWN_PUBLIC_VISIBILITY_LIMITED`.

## Continuous algorithm

1. Observe the finite allowlisted primary-source corpus.
2. Normalize page text while discarding scripts, styles and copied bodies.
3. Fingerprint semantic text and response metadata.
4. Write no repository change when fingerprints are unchanged.
5. On a new, changed or failed source, append an immutable observation and open a semantic-review item.
6. Re-read the authoritative page and update only propositions it directly supports.
7. Recalculate capability, maturity, confidence and the per-dimension frontier envelope.
8. Rank gaps by dimension weight, criticality and capability/proof distance.
9. Run failure-first tests, matched-workload evaluation, independent proof and protected-dimension non-regression.
10. Promote through Formation only; never self-promote from a changed webpage.
11. Append an immutable benchmark snapshot and delta.
12. Update the cockpit and deployment only for a material, verified change.

## Source and evidence-plane contract

- `frontier_knowledgebase_v2.json` — curated evidence, propositions, dimensions, scores and policies.
- `frontier_benchmark_engine.py` — validator, scorer, gap engine, delta compiler and append-only benchmark repository.
- `frontier_source_refresh.py` — bounded source watcher and semantic-review queue.
- `frontier_knowledgebase/README.md` — portable runtime repository layout.
- `test_frontier_benchmark_engine.py` and `test_frontier_source_refresh.py` — deterministic, failure-first proof.

`frontier_benchmark_report_v2.json`, source observations, immutable snapshots, deltas and the material-change journal are generated runtime evidence. The public Federation-Omega repository is a source plane, not a scheduler or receipt database, so those outputs are retained in the owner-controlled private evidence/recovery plane. The enabled CFBE Frontier Review automation performs the daily control cycle and may propose a source change through a reviewed feature branch; it never self-merges or auto-promotes scores.

## Promotion and failure rules

- Zero, missing or stale evidence never becomes a positive score.
- Public vendor documentation cannot establish operational maturity above level 3.
- A system's maturity cannot exceed its capability.
- Expired evidence changes the whole snapshot to `UNKNOWN_STALE_EVIDENCE`.
- Source change opens review; it never changes a score automatically.
- A gap experiment must pass matched workload, failure-first, independent semantic proof, rollback/compensation, owner-authority and critical non-regression gates.
- `AHEAD_PROVEN` is unavailable unless every current matched proof gate passes; absolute or perpetual superiority is prohibited.

## Local commands

```bash
python -m unittest test_frontier_benchmark_engine.py test_frontier_source_refresh.py
python frontier_benchmark_engine.py --dataset frontier_knowledgebase_v2.json --check
python frontier_benchmark_engine.py --dataset frontier_knowledgebase_v2.json --repository /private/evidence/frontier/benchmark --report-out /private/evidence/frontier/frontier_benchmark_report_v2.json --check
python frontier_source_refresh.py --knowledgebase frontier_knowledgebase_v2.json --repository /private/evidence/frontier/source-observations --require-all
```

Replace `/private/evidence/frontier` with an owner-controlled runtime location. The source refresh command requires network access to the allowlisted official corpus. A fetch failure retains the last good evidence and opens recovery work; it does not silently downgrade or promote a score.

# SOVARA Ω × JARVIS ΑΩ5 — Full Zero-Dilution Integration v2

This package corrects and supersedes the earlier partial ΑΩ5 executable integration.

## Canonical source
- The exact user-supplied 2,561-line specification is retained as six bounded deterministic payload chunks under `canonical/JARVIS_AO5_CANONICAL_SPEC.txt.gz.b64.part01` through `part06`.
- Reconstruction is `gzip.decompress(base64.b64decode(concat(parts)))` where the gzip used `mtime=0` and compression level 9.
- Exact reconstructed base64 length: `20196`.
- Exact deterministic gzip SHA-256: `e1b911b405c2e2cd26f78b72b31e2702bdc904269ff48155398c2e3299ad9c59`.
- Exact decompressed source SHA-256: `e777a19ed3750c989fdb82033fba1247e1b8fedb5be8721783697c83b4a4bb7f`.
- `tests/test_canonical_payload.py` joins exactly six chunks, validates base64 strictly, verifies the gzip hash, decompresses, verifies the raw source hash, then verifies 2,561 lines and all **54 Roman-numbered parts (I–LIV) plus Part 0**.
- The earlier subset's recorded `773ee295...` source hash is superseded as incorrect and retained in the discrepancy ledger rather than silently erased.

## Executable projection
`ao5_full_engine.py` implements or enforces every numbered section, including:
zero-case-data isolation; 20 immutable kernel invariants; S00–S25 state machine;
C0–C5 capability reality; Alpha and Omega engines; bidirectional reasoning;
decision DAG and hidden-SPOF detection; multi-path lattice and 3+3 path budget;
30-stream fabric; fan-out/fan-in; contamination firewall; execution budgets;
preflight/decomposition; convergence; evidence and confidence vectors;
source recovery; evidence independence; information-gain search; counterfactuals;
temporal states; knowledge ladder; contradiction gravity; 26 challenge modules;
five-angle council; pre/post-mortem; decision lineage; replay audit; opposition
patterns; dual-speed output; throughput/context/handoff controls; full Ω-FLM
pipeline; owner-correction and near-miss learning; recurrence law; Ω-Scientist;
experiment/promotion/self-improvement controls; semantic firewall; behavioural
safety; RealityGuard receipts; AutoFIX; output standard; owner-load contract;
command layer; first-turn boot; master initialization; and performance success gate.

`AO5_FULL_COMPATIBILITY_MATRIX.json` maps every source section to its executable method and direct regression test.

## Harmonized authority
- **SOVARA** remains mission / route / effect-admission / orchestration authority.
- **ΑΩ5** is the full forensic decision-intelligence engine within the SOVARA mission envelope.
- **JARVIS assurance** remains independent challenge / hold / assurance.
- **RealityGuard** governs truth and execution receipts.
- **CFBE** remains benchmark/value-learning.
- **Sentinel** remains freshness/drift/health.
- No provider-effect executor, credential minting, IAM mutation or external-effect authority is included in this package.

The only deliberate architectural reconciliation is orchestration placement. The complete ΑΩ5 method contract remains represented, and the canonical source is independently hash-bound so later refactors cannot silently redefine it.

## Verification
- Provider-shaped local regression: **60/60 PASS** = 59 executable-engine tests + 1 exact-canonical-payload test.
- End-to-end synthetic canary: **56/56 PASS**.
- External effects during canary: **0**.
- Compatibility matrix: **55/55 sections mapped; 54/54 Roman parts + Part 0**.
- Development and provider-CI near-misses and repairs are retained in `AO5_FULL_LOCAL_VERIFICATION.json`.

## Zero-dilution gate
`ZERO_DILUTION_VERIFIED` may be asserted only after all six gates pass:
1. exact canonical-source hash matches;
2. compatibility matrix is complete;
3. all regression tests pass;
4. synthetic canary passes;
5. GitHub pull-request source/admission checks pass;
6. merged-`main` readback preserves the exact admitted package.

Local/source gates 1–4 pass. Gates 5–6 remain provider-governance gates until fresh GitHub readback proves them.

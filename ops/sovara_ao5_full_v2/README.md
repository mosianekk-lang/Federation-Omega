# SOVARA Ω × JARVIS ΑΩ5 — Full Zero-Dilution Integration v2

This package corrects and supersedes the earlier partial ΑΩ5 executable integration.

## Canonical source authority
- The canonical authority is the **byte-exact user upload**, including its CRLF line endings.
- Raw uploaded bytes: `52480`.
- CRLF pairs: `2560`.
- Source lines: `2561`.
- **Canonical raw-upload SHA-256:** `773ee295b2ae3f2182afc47bcc94c676c1e6464face0176504ff8763c9616443`.
- The LF-normalized textual-equivalence SHA-256 is `e777a19ed3750c989fdb82033fba1247e1b8fedb5be8721783697c83b4a4bb7f`. It is retained as a secondary identity because an intermediate rebuild normalized line endings before hashing; it is **not** the zero-dilution authority.
- `source_identity.py` records both identities and explicitly makes `RAW_UPLOAD_SHA256` authoritative.

The exact upload is retained as six bounded deterministic payload chunks under `canonical/JARVIS_AO5_CANONICAL_SPEC.txt.gz.b64.part01` through `part06`.
Reconstruction is `gzip.decompress(base64.b64decode(concat(parts)))`, where gzip uses `mtime=0` and compression level 9.

Canonical transport proof values:
- chunk lengths: `4000, 4000, 4000, 4000, 4000, 460`;
- reconstructed base64 length: `20460`;
- deterministic gzip SHA-256: `a3b130bb71d08fb5a3a2c63615920ade240e2937a875f984e8d1982cf262f920`;
- decompressed byte-exact SHA-256: `773ee295b2ae3f2182afc47bcc94c676c1e6464face0176504ff8763c9616443`.

`tests/test_canonical_payload.py` validates all of those values, verifies strict base64 decoding, verifies 2,561 source lines, and verifies all **54 Roman-numbered parts (I–LIV) plus Part 0**.

The earlier single-file carrier was deleted after provider CI proved it was truncated. The failed runs remain in the verification ledger.

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

### Hash naming compatibility note
The pre-correction `ao5_full_engine.py` constant named `SOURCE_SHA256` contains the LF-normalized textual hash `e777…`. It is retained only as a backward-compatible textual identity. It does **not** determine canonical-source admission. The zero-dilution source gate is bound to `source_identity.RAW_UPLOAD_SHA256` plus the byte-exact reconstructed payload test.

## Harmonized authority
- **SOVARA** remains mission / route / effect-admission / orchestration authority.
- **ΑΩ5** is the full forensic decision-intelligence engine within the SOVARA mission envelope.
- **JARVIS assurance** remains independent challenge / hold / assurance.
- **RealityGuard** governs truth and execution receipts.
- **CFBE** remains benchmark/value-learning.
- **Sentinel** remains freshness/drift/health.
- No provider-effect executor, credential minting, IAM mutation or external-effect authority is included in this package.

The only deliberate architectural reconciliation is orchestration placement. The complete ΑΩ5 method contract remains represented, and the canonical source is independently byte-hash-bound so later refactors cannot silently redefine it.

## Verification
- Provider-shaped local regression before canonical transport correction: **60/60 PASS**.
- End-to-end synthetic canary: **56/56 PASS**.
- External effects during canary: **0**.
- Compatibility matrix: **55/55 sections mapped; 54/54 Roman parts + Part 0**.
- Development and provider-CI near-misses and repairs are retained in `AO5_FULL_LOCAL_VERIFICATION.json`.
- Fresh provider CI must now pass against the corrected byte-exact CRLF carrier before promotion.

## Zero-dilution gate
`ZERO_DILUTION_VERIFIED` may be asserted only after all six gates pass:
1. byte-exact canonical upload hash matches;
2. compatibility matrix is complete;
3. all regression tests pass;
4. synthetic canary passes;
5. GitHub pull-request source/admission checks pass;
6. merged-`main` readback preserves the exact admitted package.

The local executable/method gates are complete. Provider gates 5–6 and the fresh canonical byte-exact CI rerun remain open until GitHub readback proves them.

# BCO-Prime Chat Forensics v2

BCO-Prime Chat Forensics v2 is a local Python library and CLI that composes:

- the canonical 100-function BCO-Prime capability fabric;
- the 24-function Chat Forensics v1 extension;
- a contradiction-aware v1.1 truth repair;
- two source-bound meta-executive operations; and
- eight optional CFF v2 engine operations.

The unified registry contains 134 operation identifiers. The build is tested and
ready for local use. It is not registered, deployed, or proven on a live
provider. No publishing, merge, deployment, registration, or external mutation
is authorized by this project.

## Status

| State | Value |
|---|---|
| Designed | true |
| Implemented | true |
| Tested | true |
| Registered | false |
| Authorized | true, A1 local only |
| Ready | true, local configured runtime |
| Deployed | false |
| Proven | false |

The harvested meta-executive source imports three runtime packages that are not
present in the recovered snapshot. V2 therefore exposes its exact
rank_strategies algorithm and manifest as a source-hash-bound safe subset. The
full meta runtime remains fail-closed.

## Requirements

- Python 3.12 or later.
- No third-party Python dependency is required by the v2 kernel.
- Native CFF operations require the verified extracted engine and its
  restored_v1 dependency root.

## Run

From this directory:

~~~bash
python -m benchmarking.cfbe_omega.bco_prime_chat_forensics_v2 list
~~~

List with the verified CFF engine enabled:

~~~bash
python -m benchmarking.cfbe_omega.bco_prime_chat_forensics_v2 \
  --engine-path ../cff_unpacked/app_mentions_forensic_audit_v2.py \
  --dependency-root ../cff_unpacked \
  --engine-sha256 e56e002e7e0c5e95cc0b5cc13279f12da6e45fd8eb137156f5f661f0cf67e016 \
  --dependency-sha256 6226812cbf69335cfb74e3be244d107202eb065019321767411cdb951f1bbe7b \
  list
~~~

Run a pure operation:

~~~bash
python -m benchmarking.cfbe_omega.bco_prime_chat_forensics_v2 \
  run BCO-PRIME-CAP-001 --payload-json '{"objective":"bounded local audit"}'
~~~

Run a native CFF audit:

~~~bash
python -m benchmarking.cfbe_omega.bco_prime_chat_forensics_v2 \
  --engine-path ../cff_unpacked/app_mentions_forensic_audit_v2.py \
  --dependency-root ../cff_unpacked \
  engine-audit \
  --source conversations.json \
  --title "Exact conversation title" \
  --output-dir audit-output \
  --output-prefix exact_conversation
~~~

## Test

~~~bash
python -m py_compile benchmarking/cfbe_omega/bco_prime_chat_forensics_v2.py
python -m unittest -v \
  tests.test_bco_prime_chat_forensics_v1 \
  tests.test_bco_prime_chat_forensics_v2
python /root/.codex/skills/remote-skills/validate-modisa-build-contracts/scripts/validate_build_contract.py \
  BUILD_CONTRACT.json --require-proof
~~~

The selected suite passes 27 tests. It includes strict schemas, permission
denial, deterministic replay, dependency absence, hash mismatch, all registry
namespaces, a native ChatGPT-export CFF run, seven-file readback, JSONL
hash-chain validation, and ChatBridge 1.1 self-hash validation. A separate
registry sweep executes all 100 canonical core operations.

## Failure behavior

| Symptom | Cause | Disposition |
|---|---|---|
| ENGINE_NOT_CONFIGURED | CFF path not supplied | Use core, legacy, and meta-safe routes; engine routes stay closed |
| ENGINE_HASH_MISMATCH | Configured engine differs from expected bytes | Quarantine the path and verify the intended artifact |
| DEPENDENCY_PATH_MISSING | restored_v1 was not supplied | Keep CFF routes closed |
| ContractError | Input violates the typed local contract | Correct the bounded input; no external effect occurred |
| META_SAFE_SUBSET_EXTERNAL_EFFECT_REJECTED | Tournament candidate requested an effect | Use decision support only; obtain separate authority for effects |
| full meta runtime unavailable | Three source imports are absent | Safe subset remains available; full runtime closure requires the real dependencies |

## Recovery and rollback

The system stores no durable runtime state. Native audits write to their explicit
local output directory. To retry, correct the input or engine binding and use a
new output prefix. To roll back this version, stop invoking the v2 module and
continue using the unchanged v1 modules. Do not delete audit evidence as a
rollback mechanism.

See docs/architecture/BCO_PRIME_CHAT_FORENSICS_V2.md and
docs/handoffs/bco_prime_chat_forensics_v2/AI_HANDOFF.md for the complete
contract and continuity state.

## Additive successor v3

The v3 successor preserves every v2 route and the canonical 100-capability
core. It adds fourteen operations for a local hash-chained flight recorder,
authorized capability harvesting, Capability DNA, opportunity graphs,
declarative shadow compilation, paired qualification, measured adaptive-policy
evaluation and pinned meta-dependency closure.

~~~bash
python -m benchmarking.cfbe_omega.bco_prime_successor_v3 \
  --workspace-root ./successor-workspace health

python -m benchmarking.cfbe_omega.bco_prime_successor_v3 \
  --workspace-root ./successor-workspace \
  run BCO-PRIME-V3-META-DEPENDENCY-CLOSURE --payload-json '{}'
~~~

The runtime is `ON_DEMAND_GOVERNED`: it is a local library/CLI, not an
autonomous service. Harvesting is limited to an explicitly configured local
root and authorized source identifier. It rejects symlinks, path traversal,
unsupported formats, oversized inputs, malformed structured files, secrets in
derived metadata, incompatible or unknown licensing, network/provider effects,
shadow escape and stable self-promotion.

~~~bash
python -m compileall -q benchmarking tests
python -m unittest discover -s tests -p 'test_*.py'
python /root/.codex/skills/remote-skills/validate-modisa-build-contracts/scripts/validate_build_contract.py \
  BUILD_CONTRACT.json --require-proof
~~~

Full meta-runtime readiness remains `BLOCKED_WITH_ROUTE` until genuine local
MISSION_IR, DURABLE_MISSION_RUNTIME and PROOF_OS artifacts are supplied with
exact SHA-256 pins. The safe successor subset remains usable while that closure
route is blocked.

## Governed regression and harvesting successor v3.1

V3.1 is a separate additive release derived from the exact sealed v3.0 archive.
It preserves 100 canonical core, 24 legacy, two v2 meta, eight fail-closed CFF
engine, and fourteen v3 operations, then adds nine strict operations:

- trust-pinned one-time-signed baseline verification;
- complete source, policy, result, test and Capability-DNA drift checks;
- privacy-first bounded incremental extraction with signed resumable cursors;
- semantic DNA and occurrence separation so moves are not false inventions;
- sticky regression/quarantine scoreboards;
- declarative non-executable shadow repair plans;
- cancellation-aware, interprocess-locked cycle transactions; and
- control-pointer-only rollback that never rewrites monitored source.

The baseline signature uses Lamport SHA-256 one-time signatures. Verification
requires a public-key fingerprint from an external trusted release receipt;
a public key inside the baseline is never trusted by itself. Missing trust,
partial coverage, signature failure, source instability, secret/licence hold,
test or result regression, cancellation and hard drift all veto baseline
advancement and release eligibility.

~~~bash
python -m benchmarking.cfbe_omega.bco_prime_successor_v3_1 \
  --workspace-root ./v31-workspace health

python scripts/verify_bco_prime_successor_v3_1.py \
  --workspace-root ./v31-verifier-workspace
~~~

Runtime truth remains `ON_DEMAND_GOVERNED`. There is no daemon, crawler,
network client, generated-code executor, automatic baseline update, quarantine
auto-clear, provider effect, deployment, registration or stable promotion.

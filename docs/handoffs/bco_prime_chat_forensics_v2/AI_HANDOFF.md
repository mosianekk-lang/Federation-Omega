# AI handoff — BCO-Prime Chat Forensics v2

## Restore

Read, in order:

1. README.md
2. BUILD_CONTRACT.json
3. docs/architecture/BCO_PRIME_CHAT_FORENSICS_V2.md
4. docs/handoffs/bco_prime_chat_forensics_v2/PROJECT_MEMORY.md
5. benchmarking/cfbe_omega/BCO_PRIME_CHAT_FORENSICS_V2.json

Then verify the engine and dependency hashes listed in project memory.

## Verify

~~~bash
python -m py_compile benchmarking/cfbe_omega/bco_prime_chat_forensics_v2.py
python -m unittest -v \
  tests.test_bco_prime_chat_forensics_v1 \
  tests.test_bco_prime_chat_forensics_v2
python /root/.codex/skills/remote-skills/validate-modisa-build-contracts/scripts/validate_build_contract.py \
  BUILD_CONTRACT.json --require-proof
~~~

Expected selected test result: 27 tests, all passing.

## Current truth

- Local build: tested and ready.
- CFF engine: ready only when the extracted path and hashes match.
- Meta strategy subset: ready and source-bound.
- Full meta runtime: unavailable because three dependencies are absent.
- Provider registration: not performed.
- Deployment: not performed.
- Original incident backend cause: unverified.

## Do not

- Do not claim the full meta runtime is available.
- Do not infer provider durability from filenames or a branch name.
- Do not mix methodology assets into incident evidence counts.
- Do not promote a suspected terminal failure to an exact backend cause.
- Do not publish, merge, deploy, register or communicate externally under this
  mission.

## Extension seam

Add new operations through a new namespace in UnifiedRegistry; do not alter the
canonical 100 IDs. Every optional provider or engine adapter must implement
probe, hash/config validation, fail-closed execution, structured receipts and a
no-effect path.

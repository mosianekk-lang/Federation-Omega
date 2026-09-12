# AI handoff — BCΩ-PRIME v4 compatibility

## Current state

The v4.0.1 adapter is `IMPLEMENTED` and its focused tests pass. It is local-only and
must not be described as deployed, registered, merged, or provider-proven.
Formation authority is `A1_LOCAL_INTERNAL`; runtime effect authority is zero.

## Files to preserve

- `benchmarking/cfbe_omega/bco_prime_v4_v31_compatibility_adapter.py`
- `tests/test_bco_prime_v4_v31_compatibility_adapter.py`
- `BUILD_CONTRACT.json`
- `README.md`
- `FORMATION_SPEC.md`
- `PROJECT_MEMORY.md`
- `AI_HANDOFF.md`
- `proof/DOCUMENTATION_GATE_PACKET.json`

Do not overwrite either source readback used to construct this workspace. Do not
silently omit the exact v3.1 closure when moving the adapter to a repository
branch. If the branch lacks that closure, state `BLOCKED_WITH_ROUTE` for default
construction. Preserve the fail-closed injection contract: exact source-hash
attestation plus inherited health/manifest self-hash and surface validation.

## Verification commands

Run from the build/repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile \
  benchmarking/cfbe_omega/bco_prime_v4_v31_compatibility_adapter.py

PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v \
  tests.test_bco_prime_v4_v31_compatibility_adapter

PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v \
  tests.test_bco_prime_anticipatory_institution_v4 \
  tests.test_bco_prime_v4_strategic_genome_bridge

python3 /root/.codex/skills/remote-skills/validate-modisa-build-contracts/scripts/validate_build_contract.py \
  BUILD_CONTRACT.json --require-proof

PYTHONDONTWRITEBYTECODE=1 python3 -m benchmarking.cfbe_omega.bco_prime_v4_v31_compatibility_adapter \
  --workspace-root /tmp/bco-prime-v4-compat-readback manifest
```

Run the 67-test v3.1 suite from its sealed baseline layout so its adjacent CFF
fixture path resolves. A combined checkout without that adjacent fixture will
truthfully show the optional engine routes as unavailable.

## Promotion gate

Any repository branch/PR is a separate Formation action. Before writing, fresh-
read main and each destination path, preserve predecessor files, commit only the
bounded additive file set, and read back branch/commit/PR contents. Do not merge,
deploy, register, or enable background execution without new explicit authority
and semantic provider readback.

## Closure test

The local package is proven only after all verification commands pass, the
manifest binds the expected main/source hashes, the MODISA validator reports
valid with `--require-proof`, and a temporary archive extraction reproduces the
same hashes for the additive files.

# BCΩ-PRIME v4 / v3.1 compatibility adapter

This package adds a deterministic v4 decision-support surface to the sealed
BCO-Prime v3.1 registry without changing inherited operation names, receipts,
authority, or state. It is an on-demand Python library/CLI. It does not create a
scheduler, daemon, network client, provider executor, credential path, memory
root, proof plane, deployment path, or stable self-promotion path.

## Compatibility contract

`BcoPrimeV4CompatibilityAdapter` exposes the familiar methods:

- `health()` — reports inherited v3.1 health plus three additive v4 operations.
- `manifest()` — binds the exact v3.1/v4 source hashes and authority boundary.
- `execute(operation, payload)` — delegates every non-v4 operation unchanged to
  the v3.1 registry and dispatches only the three v4 operations below.

The additive operations are:

1. `BCO-PRIME-V4-MANIFEST`
2. `BCO-PRIME-V4-COMPILE-DECISION`
3. `BCO-PRIME-V4-STRATEGIC-GENOME-RECOMMEND`

All v4 receipts set dispatch, provider-effect, and stable-promotion authority to
false. Inputs asking the adapter to grant those effects are rejected before
dispatch. External-effect fields are accepted only as observations used by the
v4 hold logic; they cannot create effect authority.

## Pinned source identity

- Current main: `ceb5cf36d1e608d0520a23114fe4bfc08eab644a`
- v3.1 registry SHA-256: `111e37d3f6d990819f5d7ce6463cf62babb13aa3cdbb20db1490ec9366211a26`
- v4 institution SHA-256: `3cada8deb311b9fcefe04990c0063086b0e623884591d23fe3359d258c04d0c8`
- v4 genome bridge SHA-256: `937024053bf593a03ffa59b21dea301f9ab2ce8c7fd86e684ba4669aa3e3f33c`

The adapter hashes the materialized v3.1 registry before construction. An
explicitly injected registry must carry the exact `base_registry_sha256`
attestation and pass self-hash, schema, version, route-count, canonical-core and
authority-boundary checks on both `health` and `manifest`. If the closure is
missing, mismatched or unattested, construction fails closed; it never
substitutes a fake baseline.

## Run

Python 3.12 and the materialized v3.1/v4 repository closure are required. No
third-party package is added by this adapter.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m benchmarking.cfbe_omega.bco_prime_v4_v31_compatibility_adapter \
  --workspace-root /tmp/bco-prime-v4 health

PYTHONDONTWRITEBYTECODE=1 python3 -m benchmarking.cfbe_omega.bco_prime_v4_v31_compatibility_adapter \
  --workspace-root /tmp/bco-prime-v4 manifest
```

For a v4 operation, pass a JSON object to `--payload-json`:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m benchmarking.cfbe_omega.bco_prime_v4_v31_compatibility_adapter \
  --workspace-root /tmp/bco-prime-v4 run BCO-PRIME-V4-MANIFEST --payload-json '{}'
```

## Verify

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
```

The full combined discovery surface contains optional inherited CFF engine tests
whose fixture path is outside the materialized repository root. Run the sealed
v3.1 suite in its original baseline layout for that provider-free fixture
closure; do not reinterpret an absent adjacent fixture as a v4 regression.

## Failure and recovery

- Invalid types, unknown fields, non-finite numbers, effect-authority requests,
  path traversal, and unknown operations fail closed.
- The adapter writes no durable application state. `workspace_root` is passed to
  v3.1, whose own transaction and rollback rules remain authoritative.
- Rollback is code-only: remove the additive adapter/test/docs/contract change or
  switch back to the pinned v3.1 registry. No data migration or provider
  compensation is required.
- Restore by re-materializing the pinned sources and checking their SHA-256
  values before rerunning syntax, focused tests, v4 tests, and the v3.1 suite.

See `docs/handoffs/bco_prime_v4_v31_compatibility/FORMATION_SPEC.md`,
`PROJECT_MEMORY.md`, and `AI_HANDOFF.md` for governance, continuity, and exact
handoff state.

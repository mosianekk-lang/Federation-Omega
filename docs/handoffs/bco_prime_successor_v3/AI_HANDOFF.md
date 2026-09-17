# AI handoff — BCO-Prime successor v3

## Verify

~~~bash
python -m compileall -q benchmarking tests
python -m unittest discover -s tests -p 'test_*.py'
python /root/.codex/skills/remote-skills/validate-modisa-build-contracts/scripts/validate_build_contract.py \
  BUILD_CONTRACT.json --require-proof
python -m benchmarking.cfbe_omega.bco_prime_successor_v3 \
  --workspace-root ./successor-workspace health
~~~

Expected repository suite: 53 tests passing. The standalone release verifier
must report 100 core, 24 legacy, 2 v2 meta, 8 expected-blocked engine and 14
successor routes. Health must report
`canonical_core_count=100`, `canonical_core_invariant_preserved=true`, fourteen
successor operations, `runtimeState=ON_DEMAND_GOVERNED`, no external mutation,
no owner action and no manual tasks.

Run verification from the extracted `upstream/` directory. The package must
also contain sibling `cff_unpacked/`; otherwise inherited CFF integration tests
must fail rather than silently skip.

## Do not

- Do not alter or overwrite the sealed v2 archive.
- Do not treat local readiness as deployment or continuous operation.
- Do not scan outside an explicit authorized local root.
- Do not emit raw harvested content or secrets.
- Do not compile unknown/incompatible licensed material.
- Do not execute generated candidates or allow them to escape shadow quarantine.
- Do not authorize stable promotion from a qualification receipt.
- Do not claim full meta readiness without three genuine SHA-256-pinned artifacts.

## Extension seam

Add operations only in a new namespace, retain the 100 canonical identifiers,
bind every local write to one workspace root, emit deterministic proof receipts,
and add adversarial tests before changing the release contract. Provider-backed
capabilities require a separate Formation authority cycle and semantic readback.

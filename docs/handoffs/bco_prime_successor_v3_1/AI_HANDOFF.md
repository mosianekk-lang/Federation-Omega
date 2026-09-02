# AI handoff — BCO-Prime successor v3.1

## Verify

~~~bash
python -m compileall -q benchmarking tests scripts
python -m unittest discover -s tests -p 'test_*.py'
python scripts/verify_bco_prime_successor_v3_1.py --workspace-root ./v31-proof
python /root/.codex/skills/remote-skills/validate-modisa-build-contracts/scripts/validate_build_contract.py BUILD_CONTRACT.json --require-proof
~~~

Expected counts: 67 tests; 100 core, 24 legacy, two v2 meta, eight
expected-blocked engine, fourteen v3 and nine v3.1 routes. Runtime must remain
`ON_DEMAND_GOVERNED`; provider/source mutation, baseline advance, quarantine
clear and stable promotion must remain false.

## Trust requirements

Never verify a baseline without the expected public-key fingerprint from the
external release receipt. Require complete coverage and minimum generation.
Never treat a baseline-contained key, hash-only seal or package receipt as
deployment authority.

## Do not

- do not modify sealed v2 or v3.0 archives;
- do not claim no drift from partial coverage;
- do not derive DNA from secret or unlicensed held files;
- do not execute, import, evaluate or apply a shadow repair candidate;
- do not auto-advance the baseline or clear quarantine;
- do not mutate monitored source, network providers or live registries;
- do not claim deployment, registration or stable promotion.

# AI Handoff

Read in this order:

1. `contract_v1.json`
2. `FORMATION_SPEC.md`
3. `core.py`
4. `multistream_contract_v1.json`
5. `multistream.py`
6. `tests/test_cfbe_vnext_mission_execution_kernel.py`
7. `tests/test_cfbe_vnext_multistream_execution.py`

Run:

```bash
python -m unittest -v tests.test_cfbe_vnext_mission_execution_kernel
python -m unittest -v tests.test_cfbe_vnext_multistream_execution
python -m compileall -q benchmarking/cfbe_omega/mission_execution_kernel_vnext
```

Do not weaken the finite denominator, mission-version fencing, permit binding,
dependency invalidation, waiting contract, independent terminality or no-effect
default. A provider adapter must be separate, least-privilege, idempotent, and
proved by native readback before any deployment or behaviour claim.

Do not replace safe parallelism with blanket serialization. Preserve the
immutable graph, capability attestation, atomic claim budgets, collision keys,
claim fences, producer/verifier separation, failure-isolated logical workers,
one effect candidate per group, graph-aware terminality and paired speed-claim
gate. `SIMULATED` is never evidence of an observed 2x improvement.

# CFBE vNext Mission Execution Kernel

This package is the locally deterministic Phase 0-2 reference kernel from the
CFBE vNext design. It freezes finite mission contracts, stores hash-linked
events in SQLite, survives process restart, fences every action to the current
mission version, issues single-use permits, records idempotent local effects,
invalidates dependency-linked proof, classifies durable waiting, and refuses
false completion.

Phase 2 adds a Formation-plan-bound execution DAG, capability-attested route
selection, collision-free bounded waves, Alpha-Omega multi-path candidates,
logical specialist-bot envelopes, failure-isolated asynchronous execution,
durable claims with fencing, sovereign proof fan-in, and one selected effect
candidate per mission effect group. It selects an effect candidate but never
performs an external effect.

It performs no provider deployment and grants no GitHub, Google Cloud, IAM,
secret, traffic, financial, or publication authority.

## Minimal use

```python
from benchmarking.cfbe_omega.mission_execution_kernel_vnext import (
    FruitCriterion, MissionContract, MissionExecutionKernel, Requirement,
)

contract = MissionContract.create(
    mission_id="MISSION-1",
    mission_version=1,
    owner_outcome="Deliver one independently verified local result",
    terminal_fruit=(FruitCriterion("F1", "Independent result receipt exists"),),
    requirements=(Requirement("R1", "Build and test the required local result"),),
    critical_path=("R1",),
)
kernel = MissionExecutionKernel("/tmp/cfbe-vnext.sqlite3")
kernel.open_mission(contract)
```

## Verification

```bash
python -m unittest -v tests.test_cfbe_vnext_mission_execution_kernel
python -m unittest -v tests.test_cfbe_vnext_multistream_execution
python -m compileall -q benchmarking/cfbe_omega/mission_execution_kernel_vnext
```

The deterministic courts include permit/effect concurrency stress, atomic
multi-path budget and collision enforcement, independent producer/verifier
binding, bot-path failure containment, graph-aware terminality, and an
evidence-grade paired throughput gate. Zero-test and count-mismatch results
fail closed.

Repository admission, provider canaries, effectful provider workers, and value
measurement are later phases with separate authority and proof gates.

"""Local operator CLI for the Omega-One completion-engine foundation."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any, Sequence

from .cfbe import (
    CFBEEvaluator,
    DeterministicFaultSimulator,
    FailureInjection,
    FaultKind,
    SimulationTask,
    SimulatorPolicy,
)
from .provider_adapters import default_provider_registry
from .work_engine import MissionEnvelope, OmegaCompletionEngine, ProofBundle, TaskEnvelope, WorkerDescriptor, output_digest


def _render(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def _demo(state_dir: Path) -> dict[str, Any]:
    engine = OmegaCompletionEngine(state_dir)
    mission_id = "OMEGA-LOCAL-DEMO"
    if mission_id not in engine.state["missions"]:
        engine.register_worker(WorkerDescriptor("local-worker-1", ("research", "synthesis"), capacity=2))
        engine.submit_mission(
            MissionEnvelope(mission_id, 1, "Complete a no-effect two-stream mission", ("both fruits independently proven",)),
            (
                TaskEnvelope("research-a", mission_id, (), "research", "sha256:demo-a"),
                TaskEnvelope("research-b", mission_id, (), "research", "sha256:demo-b"),
                TaskEnvelope("synthesis", mission_id, ("research-a", "research-b"), "synthesis", "sha256:demo-join"),
            ),
        )
    while engine.mission_status(mission_id)["state"] != "PROVEN":
        lease = engine.schedule_next()
        if lease is None:
            raise RuntimeError("DEMO_STALLED_WITHOUT_ROUTABLE_TASK")
        fruit = {"task_key": lease.task_key, "fruit": "verified-local-demo"}
        proof = ProofBundle(
            verifier_id="independent-local-verifier",
            output_digest=output_digest(fruit),
            schema_valid=True,
            semantic_valid=True,
            policy_valid=True,
            evidence_refs=("urn:omega:demo:deterministic-readback",),
        )
        engine.submit_candidate(lease, fruit, proof)
    return {
        "scope": "LOCAL_NO_EFFECT_DEMO",
        "status": engine.mission_status(mission_id),
        "integrity": engine.verify_integrity(),
        "source_verified": True,
        "provider_execution": False,
        "deployed": False,
    }


def _providers() -> dict[str, Any]:
    registry = default_provider_registry()
    providers = []
    for provider, adapter in sorted(registry.adapters.items(), key=lambda item: item[0].value):
        descriptor = adapter.descriptor
        providers.append({
            "provider": provider.value,
            "maturity": descriptor.descriptor_maturity.value,
            "available": adapter.availability.accepts_requests,
            "live_execution_authorized": descriptor.gate.live_execution_authorized,
            "external_effects_authorized": descriptor.gate.external_effects_authorized,
            "zero_dilution": descriptor.zero_dilution,
            "recommended_concurrency": descriptor.concurrency.recommended_concurrency,
            "capabilities": [
                {"name": item.flag.value, "supported": item.supported, "maturity": item.maturity.value, "preview": item.preview}
                for item in descriptor.capabilities
            ],
        })
    return {"scope": "DOCUMENTATION_VERIFIED_LOCAL_DESCRIPTORS", "providers": providers}


def _benchmark() -> dict[str, Any]:
    faults = tuple(FaultKind)
    tasks = tuple(
        SimulationTask(
            task_id=f"T{index:02d}", mission_id=f"M{index:02d}", tenant_id="alpha" if index % 2 else "beta",
            latency_seconds=1.0 + (index % 3) * 0.25, effect_key=f"effect-{index}", cost=0.0, budget=0.0,
        )
        for index in range(1, len(faults) + 1)
    )
    injections = tuple(FailureInjection(task.task_id, fault) for task, fault in zip(tasks, faults))
    baseline = DeterministicFaultSimulator.run("serial-safe", tasks, injections, policy=SimulatorPolicy(parallelism=1))
    candidate = DeterministicFaultSimulator.run("parallel-safe", tasks, injections, policy=SimulatorPolicy(parallelism=3))
    report = CFBEEvaluator.evaluate(candidate, baseline=baseline)
    return report.to_dict()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="omega-completion", description="Omega-One governed multi-stream completion engine")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="run the deterministic no-effect DAG demo")
    demo.add_argument("--state-dir", type=Path, default=Path(".omega-demo"))
    status = commands.add_parser("status", help="read a local mission status")
    status.add_argument("mission_id")
    status.add_argument("--state-dir", type=Path, default=Path(".omega-demo"))
    cancel = commands.add_parser("cancel", help="cancel and fence a local mission")
    cancel.add_argument("mission_id")
    cancel.add_argument("--state-dir", type=Path, default=Path(".omega-demo"))
    commands.add_parser("providers", help="show non-effect provider capability descriptors")
    commands.add_parser("benchmark", help="run deterministic local CFBE fault simulation")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "demo":
        _render(_demo(args.state_dir))
    elif args.command == "status":
        _render(OmegaCompletionEngine(args.state_dir).mission_status(args.mission_id))
    elif args.command == "cancel":
        _render(OmegaCompletionEngine(args.state_dir).cancel_mission(args.mission_id))
    elif args.command == "providers":
        _render(_providers())
    elif args.command == "benchmark":
        _render(_benchmark())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .acceptance_integrity import AcceptanceDomain, AcceptanceIntegrityCourt, AcceptanceWitness
from .engineering_runtime import ReadinessSignal, SLOSReadinessCourt
from .evolution_lab import EvolutionLab
from .finalization_kernel import FinalizationDirective, SLOSFinalizationKernel
from .harness_tournament import HarnessGenome
from .market_composite_benchmark import (
    BenchmarkIntegrityCourt,
    BenchmarkObservation,
    BenchmarkTask,
    MarketCompositeCourt,
)
from .mission_capability_intelligence import (
    ExecutionSurface,
    MachineGenome,
    MissionCapabilityIntelligence,
    MissionResourceRequest,
    SurfaceReadiness,
)
from .opportunity_adapter import EngineeringOpportunityAdapter, MissionProfile


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


@dataclass(frozen=True, slots=True)
class OperatorReceipt:
    operation: str
    status: str
    payload: Mapping[str, Any]

    def canonical_json(self) -> str:
        return _json(asdict(self))


class SLOSEngineeringOperator:
    """Owner-facing, no-effect SLOS engineering control surface.

    It compiles plans, selects engineering shape, forms bounded harness challengers,
    evaluates proof/value/acceptance receipts, and now performs deterministic resource
    preflight plus market-composite benchmark evaluation. It never executes provider,
    repository, deployment, IAM, secret, traffic or spend effects itself.
    """

    def compile_blueprint(self, request: Mapping[str, Any]) -> OperatorReceipt:
        directive = FinalizationDirective(
            mission_id=str(request["mission_id"]),
            base_revision=str(request["base_revision"]),
            objective=str(request["objective"]),
            required_capabilities=tuple(sorted(set(map(str, request.get("required_capabilities", ()))))) ,
            optional_capabilities=tuple(sorted(set(map(str, request.get("optional_capabilities", ()))))) ,
            risk=str(request.get("risk", "HIGH")),
            unknown_count=int(request.get("unknown_count", 0)),
            estimated_tasks=int(request.get("estimated_tasks", 0)),
            external_effects=bool(request.get("external_effects", False)),
            authority_ready=bool(request.get("authority_ready", True)),
            independent_verification_required=bool(request.get("independent_verification_required", True)),
        )
        blueprint = SLOSFinalizationKernel().compile(
            directive,
            repository_files={str(k): str(v) for k, v in dict(request.get("repository_files", {})).items()},
            toolchain={str(k): str(v) for k, v in dict(request.get("toolchain", {})).items()},
            dependencies={str(k): str(v) for k, v in dict(request.get("dependencies", {})).items()},
        )
        return OperatorReceipt("compile_blueprint", "COMPILED_NO_EFFECT", asdict(blueprint))

    def assess_readiness(self, rows: Sequence[Mapping[str, Any]]) -> OperatorReceipt:
        signals = tuple(
            ReadinessSignal(
                signal_id=str(row["signal_id"]),
                passed=bool(row["passed"]),
                proof_ref=str(row.get("proof_ref", "")),
                receiver=str(row.get("receiver", "")),
            )
            for row in rows
        )
        verdict = SLOSReadinessCourt().evaluate(signals)
        return OperatorReceipt("assess_readiness", verdict.status, asdict(verdict))

    def assess_tenx(self, baseline: Mapping[str, Any], candidate: Mapping[str, Any]) -> OperatorReceipt:
        try:
            from .codeforge import EngineeringMetrics, TenXEngineeringCourt
        except (ImportError, ModuleNotFoundError) as exc:
            raise RuntimeError("CODEFORGE_REQUIRED_FOR_TENX_COURT") from exc
        b = EngineeringMetrics(**dict(baseline))
        c = EngineeringMetrics(**dict(candidate))
        verdict = TenXEngineeringCourt().compare(b, c)
        return OperatorReceipt("assess_tenx", verdict.reason, asdict(verdict))

    def assess_shape(self, request: Mapping[str, Any]) -> OperatorReceipt:
        profile = MissionProfile(
            mission_id=str(request["mission_id"]),
            changed_paths=tuple(map(str, request.get("changed_paths", ()))),
            subsystems=tuple(map(str, request.get("subsystems", ()))),
            risk=str(request.get("risk", "MEDIUM")).upper(),
            unknown_count=int(request.get("unknown_count", 0)),
            estimated_tasks=int(request.get("estimated_tasks", 1)),
            external_effects=bool(request.get("external_effects", False)),
            authority_ready=bool(request.get("authority_ready", True)),
            independent_verification_required=bool(request.get("independent_verification_required", True)),
        )
        decision = EngineeringOpportunityAdapter().choose_shape(profile)
        return OperatorReceipt("assess_shape", decision.shape.value, asdict(decision))

    def assess_acceptance(self, request: Mapping[str, Any]) -> OperatorReceipt:
        witnesses = tuple(
            AcceptanceWitness(
                witness_id=str(row["witness_id"]),
                domain=AcceptanceDomain(str(row["domain"])),
                actor_id=str(row["actor_id"]),
                trust_domain=str(row["trust_domain"]),
                passed=bool(row["passed"]),
                evidence_refs=tuple(map(str, row.get("evidence_refs", ()))),
                relation_to_implementation=str(row.get("relation_to_implementation", "INDEPENDENT")),
            )
            for row in request.get("witnesses", ())
        )
        required = tuple(str(value) for value in request.get("required_domains", ("TEST", "PROOF", "READBACK")))
        verdict = AcceptanceIntegrityCourt().evaluate(
            implementation_actor_id=str(request["implementation_actor_id"]),
            implementation_trust_domain=str(request["implementation_trust_domain"]),
            witnesses=witnesses,
            required_domains=required,
        )
        return OperatorReceipt("assess_acceptance", verdict.status, asdict(verdict))

    def evolve_harness(self, request: Mapping[str, Any]) -> OperatorReceipt:
        baseline = HarnessGenome.create(**dict(request["baseline"]))
        variants = EvolutionLab().generate(
            baseline,
            substitutions=dict(request.get("substitutions", {})),
            max_variants=int(request.get("max_variants", 12)),
            max_changed_dimensions=int(request.get("max_changed_dimensions", 2)),
        )
        batch = EvolutionLab().plan(baseline, variants)
        payload = {"batch": asdict(batch), "variants": tuple(asdict(row) for row in variants)}
        return OperatorReceipt("evolve_harness", "CANDIDATES_FORMED_NO_EFFECT", payload)

    def resource_preflight(self, request: Mapping[str, Any]) -> OperatorReceipt:
        mission = MissionResourceRequest(
            mission_id=str(request["mission_id"]),
            required_capabilities=tuple(map(str, request.get("required_capabilities", ()))),
            preferred_capabilities=tuple(map(str, request.get("preferred_capabilities", ()))),
            heavy_compute=bool(request.get("heavy_compute", False)),
            prefer_owner_controlled=bool(request.get("prefer_owner_controlled", True)),
            privacy_sensitive=bool(request.get("privacy_sensitive", False)),
            external_effects=bool(request.get("external_effects", False)),
            required_authority_actions=tuple(map(str, request.get("required_authority_actions", ()))),
        )
        surfaces = []
        for row in request.get("surfaces", ()):
            genome = row.get("genome")
            surfaces.append(
                ExecutionSurface(
                    surface_id=str(row["surface_id"]),
                    surface_type=str(row["surface_type"]),
                    provider=str(row.get("provider", "")),
                    readiness=SurfaceReadiness[str(row["readiness"]).upper()],
                    capabilities=tuple(map(str, row.get("capabilities", ()))),
                    authority_actions=tuple(map(str, row.get("authority_actions", ()))),
                    owner_controlled=bool(row.get("owner_controlled", False)),
                    current=bool(row.get("current", True)),
                    trust_domain=str(row.get("trust_domain", "")),
                    proof_ref=str(row.get("proof_ref", "")),
                    cost_rank=int(row.get("cost_rank", 100)),
                    latency_rank=int(row.get("latency_rank", 100)),
                    throughput_rank=int(row.get("throughput_rank", 0)),
                    genome=MachineGenome(**dict(genome)) if genome else None,
                )
            )
        verdict = MissionCapabilityIntelligence().compile(mission, surfaces)
        return OperatorReceipt("resource_preflight", "DEGRADED_COMPUTE_MODE" if verdict.degraded_compute_mode else "RESOURCE_PLAN_READY", asdict(verdict))

    @staticmethod
    def _benchmark_tasks(rows: Sequence[Mapping[str, Any]]) -> tuple[BenchmarkTask, ...]:
        return tuple(
            BenchmarkTask(
                task_id=str(row["task_id"]),
                source_epoch=str(row["source_epoch"]),
                environment_profile=str(row["environment_profile"]),
                oracle_id=str(row["oracle_id"]),
                hard_floors=tuple(map(str, row.get("hard_floors", ()))),
                oracle_frozen=bool(row.get("oracle_frozen", True)),
                scoreable=bool(row.get("scoreable", True)),
            )
            for row in rows
        )

    @staticmethod
    def _benchmark_observations(rows: Sequence[Mapping[str, Any]]) -> tuple[BenchmarkObservation, ...]:
        return tuple(BenchmarkObservation(**dict(row)) for row in rows)

    def assess_benchmark_integrity(self, rows: Sequence[Mapping[str, Any]]) -> OperatorReceipt:
        verdict = BenchmarkIntegrityCourt().evaluate(self._benchmark_tasks(rows))
        return OperatorReceipt("assess_benchmark_integrity", verdict.status, asdict(verdict))

    def assess_market_composite(self, request: Mapping[str, Any]) -> OperatorReceipt:
        verdict = MarketCompositeCourt().compare(
            tasks=self._benchmark_tasks(request.get("tasks", ())),
            candidate_observations=self._benchmark_observations(request.get("candidate_observations", ())),
            baseline_observations=self._benchmark_observations(request.get("baseline_observations", ())),
            independent_judge_passed=bool(request.get("independent_judge_passed", False)),
        )
        return OperatorReceipt("assess_market_composite", verdict.status, asdict(verdict))


def _load(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="slos-engineering", description="No-effect SLOS engineering compiler/proof interface")
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("compile"); c.add_argument("request_json")
    r = sub.add_parser("readiness"); r.add_argument("signals_json")
    t = sub.add_parser("tenx"); t.add_argument("baseline_json"); t.add_argument("candidate_json")
    s = sub.add_parser("shape"); s.add_argument("request_json")
    a = sub.add_parser("acceptance"); a.add_argument("request_json")
    e = sub.add_parser("evolve"); e.add_argument("request_json")
    p = sub.add_parser("resource-preflight"); p.add_argument("request_json")
    bi = sub.add_parser("benchmark-integrity"); bi.add_argument("tasks_json")
    mc = sub.add_parser("market-composite"); mc.add_argument("request_json")
    args = parser.parse_args(argv)
    op = SLOSEngineeringOperator()
    if args.command == "compile": receipt = op.compile_blueprint(_load(args.request_json))
    elif args.command == "readiness": receipt = op.assess_readiness(_load(args.signals_json))
    elif args.command == "tenx": receipt = op.assess_tenx(_load(args.baseline_json), _load(args.candidate_json))
    elif args.command == "shape": receipt = op.assess_shape(_load(args.request_json))
    elif args.command == "acceptance": receipt = op.assess_acceptance(_load(args.request_json))
    elif args.command == "evolve": receipt = op.evolve_harness(_load(args.request_json))
    elif args.command == "resource-preflight": receipt = op.resource_preflight(_load(args.request_json))
    elif args.command == "benchmark-integrity": receipt = op.assess_benchmark_integrity(_load(args.tasks_json))
    else: receipt = op.assess_market_composite(_load(args.request_json))
    print(receipt.canonical_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

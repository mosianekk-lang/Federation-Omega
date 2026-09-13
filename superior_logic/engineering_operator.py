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
    and evaluates proof/value/acceptance receipts. It never executes provider,
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
        # CodeForge remains the single authority for the 10x engineering-value court.
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
        payload = {
            "batch": asdict(batch),
            "variants": tuple(asdict(row) for row in variants),
        }
        return OperatorReceipt("evolve_harness", "CANDIDATES_FORMED_NO_EFFECT", payload)


def _load(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="slos-engineering", description="No-effect SLOS engineering compiler/proof interface")
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("compile")
    c.add_argument("request_json")
    r = sub.add_parser("readiness")
    r.add_argument("signals_json")
    t = sub.add_parser("tenx")
    t.add_argument("baseline_json")
    t.add_argument("candidate_json")
    s = sub.add_parser("shape")
    s.add_argument("request_json")
    a = sub.add_parser("acceptance")
    a.add_argument("request_json")
    e = sub.add_parser("evolve")
    e.add_argument("request_json")
    args = parser.parse_args(argv)
    op = SLOSEngineeringOperator()
    if args.command == "compile":
        receipt = op.compile_blueprint(_load(args.request_json))
    elif args.command == "readiness":
        receipt = op.assess_readiness(_load(args.signals_json))
    elif args.command == "tenx":
        receipt = op.assess_tenx(_load(args.baseline_json), _load(args.candidate_json))
    elif args.command == "shape":
        receipt = op.assess_shape(_load(args.request_json))
    elif args.command == "acceptance":
        receipt = op.assess_acceptance(_load(args.request_json))
    else:
        receipt = op.evolve_harness(_load(args.request_json))
    print(receipt.canonical_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .engineering_runtime import ReadinessSignal, SLOSReadinessCourt
from .finalization_kernel import FinalizationDirective, SLOSFinalizationKernel


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

    It compiles plans and evaluates proof/value receipts. It never executes provider,
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
        # CodeForge is the single existing authority for the 10x engineering-value court.
        # Import lazily so this finalization delta does not duplicate that logic.
        try:
            from .codeforge import EngineeringMetrics, TenXEngineeringCourt
        except (ImportError, ModuleNotFoundError) as exc:
            raise RuntimeError("CODEFORGE_REQUIRED_FOR_TENX_COURT") from exc
        b = EngineeringMetrics(**dict(baseline))
        c = EngineeringMetrics(**dict(candidate))
        verdict = TenXEngineeringCourt().compare(b, c)
        return OperatorReceipt("assess_tenx", verdict.reason, asdict(verdict))


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
    args = parser.parse_args(argv)
    op = SLOSEngineeringOperator()
    if args.command == "compile":
        receipt = op.compile_blueprint(_load(args.request_json))
    elif args.command == "readiness":
        receipt = op.assess_readiness(_load(args.signals_json))
    else:
        receipt = op.assess_tenx(_load(args.baseline_json), _load(args.candidate_json))
    print(receipt.canonical_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

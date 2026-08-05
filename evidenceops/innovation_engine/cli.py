from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from .algorithms import AlgorithmOpportunityMiner
from .foundry import EvidenceOpsAlgorithmFoundry


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_result(result: Mapping[str, Any], output: str | Path | None) -> None:
    rendered = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if output:
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


def default_canary_payload(signals: list[Mapping[str, Any]]) -> dict[str, Any]:
    gates = {
        "G1_SCOPE_LOCKED": True,
        "G2_EXPECTED_SOURCES_ENUMERATED": True,
        "G3_BODIES_RETRIEVED": True,
        "G4_ATTACHMENTS_AND_NESTED_CONTAINERS_HANDLED": True,
        "G5_ATOMIC_DECOMPOSITION_COMPLETE": True,
        "G6_DEDUPLICATION_AND_VERSION_RECONCILIATION_COMPLETE": True,
        "G7_CONTRADICTIONS_AND_COUNTEREXAMPLES_TESTED": True,
        "G8_REQUIREMENT_COVERAGE_COMPLETE": True,
        "G9_SELECTION_AND_REJECTION_LOGIC_RECORDED": True,
        "G10_INDEPENDENT_READBACK_PASSED": True,
    }
    return {
        "cycle_id": "EVIDENCEOPS-ALGORITHM-FOUNDRY-CANARY-V1",
        "evidence_refs": [
            "master-bible:CH-046",
            "master-bible:CH-054",
            "master-bible:CH-061",
            "master-bible:CH-063",
            "master-bible:CH-072",
            "secondary-brain:CAP-026-039",
        ],
        "lesson_signals": signals,
        "directive": (
            "Build and update the internal EvidenceOps algorithm foundry, "
            "verify its controls and preserve the learning delta"
        ),
        "available_routes": [
            {
                "route_id": "LOCAL-DETERMINISTIC-SOURCE",
                "action": "build update verify",
                "available": True,
            }
        ],
        "claims": [
            {
                "statement": "The local deterministic algorithm canary passed",
                "scope_defined": True,
                "source_evidence": ["test-suite:dedicated"],
                "execution_receipt": "receipt:local-canary",
                "target_readback": ["workspace:result-readback"],
                "independent_verification": ["hash-chain:passed"],
                "inference_distance": 0.0,
            }
        ],
        "unknowns": [
            {
                "unknown_id": "UNK-PROVIDER-REPRODUCTION",
                "question": "Will a governed provider runner reproduce the local result?",
                "impact": 1.0,
                "uncertainty": 1.0,
                "repetition": 1,
                "strategic_relevance": 1.0,
                "learnability": 0.9,
                "cross_domain_reuse": 1.0,
                "investigation_cost": 0.4,
                "risk": 0.1,
                "owner_burden": 0.0,
                "next_reversible_test": "run a read-only provider CI canary",
            }
        ],
        "experiments": [
            {
                "experiment_id": "EXP-LOCAL-DETERMINISTIC-CANARY",
                "description": "run all algorithm and evolution tests",
                "expected_information_gain": 0.9,
                "decision_sensitivity": 1.0,
                "resolution_probability": 1.0,
                "reversibility": 1.0,
                "downstream_reuse": 1.0,
                "cost": 0.1,
                "time": 0.1,
                "risk": 0.05,
                "owner_attention": 0.0,
                "authority": "A1_INTERNAL",
            }
        ],
        "finality_items": [
            {"item_id": "SOURCE-BUILD", "state": "EXTRACTED_VERIFIED"},
            {"item_id": "LOCAL-TEST", "state": "EXTRACTED_VERIFIED"},
        ],
        "corpus_evaluations": [
            {"requested_claim": "complete bounded source selection", "gates": gates}
        ],
        "control_transactions": [
            {
                "record_id": "ALG-CATALOG-V1",
                "record_type": "ALGORITHM_CATALOG",
                "cycle_id": "EVIDENCEOPS-ALGORITHM-FOUNDRY-CANARY-V1",
                "packet_id": "PKT-ALG-FOUNDRY-V1",
                "idempotency_key": "IDEM-ALG-FOUNDRY-V1",
                "expected_revision": "R1",
                "current_revision": "R1",
                "lease_epoch": "E1",
                "cycle_start_lease_epoch": "E1",
                "collision_key": "EVIDENCEOPS:ALGORITHM-FOUNDRY",
                "collision_owner": "ALGORITHM-FOUNDRY",
                "actor_id": "ALGORITHM-FOUNDRY",
                "matter_id": "INTERNAL-SYSTEM",
                "case_wall_id": "INTERNAL-SYSTEM",
                "nested_matter_ids": ["INTERNAL-SYSTEM"],
                "nested_case_wall_ids": ["INTERNAL-SYSTEM"],
                "references": ["MASTER-BIBLE", "SECONDARY-BRAIN"],
                "state": "READY",
            }
        ],
        "valid_references": ["MASTER-BIBLE", "SECONDARY-BRAIN"],
        "allowed_states": ["READY", "COMPLETE"],
        "action_proofs": [
            {
                "action": {
                    "action_id": "ACT-READ-CATALOG",
                    "action": "READ_SOURCE",
                    "target_id": "ALG-CATALOG-V1",
                },
                "proof": {
                    "action": "READ_SOURCE",
                    "target_id": "ALG-CATALOG-V1",
                    "provider_response": "catalog returned with matching hash",
                    "target_readback": {"catalog": "ALG-CATALOG-V1"},
                    "checked_at": "CANARY-DETERMINISTIC",
                    "executed": True,
                    "semantic_match": True,
                },
            }
        ],
        "proof_state_transitions": [
            {
                "current_state": "STATICALLY_VALIDATED",
                "target_state": "PROTOTYPE_PASSED",
                "proof": {
                    "prototype_receipt": "receipt:local-canary",
                    "rollback_test": "rollback:passed",
                    "evidence_refs": ["test-suite:dedicated"],
                },
            }
        ],
        "epistemic_debts": [
            {
                "debt_id": "DEBT-PROVIDER-REPLICATION",
                "debt_class": "UNREPLICATED_FINDING",
                "description": "local deterministic result lacks provider replication",
                "impact": 0.9,
                "uncertainty": 0.8,
                "decision_sensitivity": 0.8,
                "repetition": 1,
                "strategic_relevance": 0.9,
                "reuse_potential": 1.0,
                "closure_cost": 0.4,
                "owner_burden": 0.0,
                "closure_test": "read-only provider CI reproduction",
                "evidence_refs": ["test-suite:dedicated"],
            }
        ],
        "route_candidates": [
            {
                "route_id": "LOCAL-DETERMINISTIC-SOURCE",
                "description": "reuse the existing Innovation Engine and run locally",
                "mission_fidelity": 1.0,
                "expected_value": 0.9,
                "probability": 1.0,
                "proof_quality": 0.9,
                "reversibility": 1.0,
                "information_gain": 0.8,
                "option_value": 0.9,
                "reuse_potential": 1.0,
                "cost": 0.1,
                "latency": 0.1,
                "maintenance": 0.1,
                "risk": 0.05,
                "owner_burden": 0.0,
                "authority": "A1_INTERNAL",
                "fallback": "preserve source and run the previous version",
            }
        ],
        "failure_lessons": [
            {
                "failure": {
                    "fingerprint": "ALG-FP-SAFE-VALIDATOR",
                    "category": "CONTRACT",
                    "summary": "safe explicit values were rejected while api_key was missed",
                    "evidence_refs": ["test-run:first-failure"],
                },
                "recovery": {
                    "resolved_failure_fingerprint": "ALG-FP-SAFE-VALIDATOR",
                    "repair": "allow explicit safe boundary fields and reject api_key",
                    "guard": "separate permitted safe values from prohibited secret fields",
                    "readback": "dedicated evolution tests passed",
                    "applicability": ["algorithm configuration validators"],
                    "evidence_refs": ["test-run:repaired"],
                },
                "regression": {
                    "passed": True,
                    "test_id": "test_configuration_cannot_expand_authority_or_store_secret",
                },
            }
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="evidenceops-algorithm-foundry")
    parser.add_argument("--policy", required=True, help="Federation learning policy JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)

    mine = subparsers.add_parser("mine", help="Mine algorithm opportunities from lessons")
    mine.add_argument("--input", required=True)
    mine.add_argument("--output")

    cycle = subparsers.add_parser("cycle", help="Run a complete foundry cycle")
    cycle.add_argument("--input", required=True)
    cycle.add_argument("--workspace", required=True)
    cycle.add_argument("--output")

    canary = subparsers.add_parser("canary", help="Run the built-in local canary")
    canary.add_argument("--signals", required=True)
    canary.add_argument("--workspace", required=True)
    canary.add_argument("--output")

    evolve = subparsers.add_parser("evolve", help="Evaluate one algorithm candidate")
    evolve.add_argument("--input", required=True)
    evolve.add_argument("--workspace", required=True)
    evolve.add_argument("--output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "mine":
        payload = load_json(args.input)
        signals = payload if isinstance(payload, list) else payload.get("lesson_signals", [])
        result = AlgorithmOpportunityMiner().run(signals).as_dict()
        write_result(result, args.output)
        return 0

    foundry = EvidenceOpsAlgorithmFoundry(
        args.workspace,
        learning_policy_path=args.policy,
    )
    if args.command == "cycle":
        result = foundry.execute_cycle(load_json(args.input)).as_dict()
    elif args.command == "canary":
        signals = load_json(args.signals)
        result = foundry.execute_cycle(default_canary_payload(signals)).as_dict()
    elif args.command == "evolve":
        payload = load_json(args.input)
        result = foundry.evolve_algorithm(**payload)
    else:  # pragma: no cover
        raise RuntimeError(f"unsupported command: {args.command}")
    write_result(result, args.output)
    return 0 if result.get("status", result.get("decision", {}).get("decision")) not in {"FAILED", "REJECT"} else 2


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from pathlib import Path

from alpha_omega_v30.neuro_symbolic import NeuroSymbolicPlanner, PlanConstraints, PlanStep, SymbolicPlanVerifier
from alpha_omega_v30.product_discovery import ExperimentContract, ExperimentEvaluator, PainSignal, ProductDiscoveryEngine
from alpha_omega_v30.progressive_delivery import FileRevisionProvider, ProgressiveDeliveryController
from alpha_omega_v30.prove_p09_p10_p14 import build_proof


def test_progressive_delivery_promotes_and_proves_rollback(tmp_path: Path) -> None:
    provider = FileRevisionProvider(tmp_path / "provider")
    controller = ProgressiveDeliveryController(provider)
    first = controller.release({"version": "1", "ready": True}, lambda revision, percentage: True)
    second = controller.release({"version": "2", "ready": True}, lambda revision, percentage: True)
    assert first["status"] == "PROMOTED"
    assert second["status"] == "PROMOTED"
    assert second["readback_verified"]
    assert second["health_verified"]
    assert second["rollback_verified"]
    assert second["restoration_verified"]
    assert second["persistence_verified"]
    assert provider.state()["traffic"] == {second["candidate"]: 100}


def test_progressive_delivery_rolls_back_unhealthy_candidate(tmp_path: Path) -> None:
    provider = FileRevisionProvider(tmp_path / "provider")
    controller = ProgressiveDeliveryController(provider)
    baseline = controller.release({"version": "1"}, lambda revision, percentage: True)
    before = provider.state()
    result = controller.release({"version": "2"}, lambda revision, percentage: percentage < 50)
    assert baseline["status"] == "PROMOTED"
    assert result["status"] == "ROLLED_BACK"
    assert result["rollback_verified"]
    assert result["persistence_verified"]
    assert provider.state() == before


def test_product_discovery_ranks_expected_value_and_marks_synthetic_proof(tmp_path: Path) -> None:
    hypotheses = ProductDiscoveryEngine().discover(
        [
            PainSignal("1", "ICT", "manual reporting", 10, 100, 1.0, 1.0, "E1"),
            PainSignal("2", "ICT", "manual reporting", 5, 100, 1.0, 1.0, "E2"),
            PainSignal("3", "Legal", "reconciliation", 1, 50, 1.0, 1.0, "E3"),
        ]
    )
    assert hypotheses[0].problem == "manual reporting"
    result = ExperimentEvaluator(tmp_path / "ledger.jsonl").evaluate(
        ExperimentContract("E", hypotheses[0].hypothesis_id, "interest", 0.5, 10, True, "AUTO"),
        0.8,
        0,
        {"source": "synthetic"},
    )
    assert result["validated"]
    assert result["market_proof"] == "EXTERNAL_EVIDENCE_REQUIRED"
    assert result["persistence_verified"]


def test_symbolic_verifier_rejects_forbidden_effect_and_selects_safe_plan() -> None:
    constraints = PlanConstraints(
        initial_facts=("authority",),
        required_outcomes=("done",),
        forbidden_effects=("delete",),
        max_cost=5,
        max_risk=0.5,
    )
    safe = [PlanStep("a", "act", preconditions=("authority",), effects=("done",), cost=1, risk=0.1)]
    unsafe = [PlanStep("b", "act", effects=("delete", "done"), cost=0, risk=0.1)]
    assert SymbolicPlanVerifier().verify(unsafe, constraints)["valid"] is False
    result = NeuroSymbolicPlanner().select({"safe": safe, "unsafe": unsafe}, constraints)
    assert result["valid"]
    assert result["selected"]["candidate_id"] == "safe"


def test_provider_proof_runner_records_exact_boundaries(tmp_path: Path) -> None:
    receipt = build_proof(tmp_path / "proof")
    assert receipt["phases"]["P09"]["status"] == "REFERENCE_PROVIDER_VERIFIED"
    assert receipt["phases"]["P09"]["cloud_run"].startswith("PROVIDER_BLOCKED")
    assert receipt["phases"]["P10"]["status"].endswith("MARKET_PROOF_REQUIRED")
    assert receipt["phases"]["P14"]["planning"]["valid"]
    assert (tmp_path / "proof" / "p09_p10_p14_receipt.json").is_file()

from benchmarking.cfbe_omega.fitness_a1_simulations_v1 import (
    run_authority_precision_simulation,
    run_information_gain_scheduling_simulation,
    simulation_summary,
)


def test_authority_precision_simulation_prefers_exact_capabilities():
    receipt = run_authority_precision_simulation()
    assert receipt.experiment_id == "EXP-CFBE-FIT-009"
    assert receipt.case_count == 6
    assert receipt.exact_model_false_positive == 0
    assert receipt.exact_model_precision == 1.0
    assert receipt.broad_role_false_positive > receipt.exact_model_false_positive
    assert receipt.broad_role_precision < receipt.exact_model_precision
    assert receipt.provider_effect is False
    assert len(receipt.receipt_sha256) == 64


def test_information_gain_order_reduces_cost_to_same_threshold():
    receipt = run_information_gain_scheduling_simulation()
    assert receipt.experiment_id == "EXP-CFBE-FIT-010"
    assert receipt.information_gain_route_better is True
    assert receipt.information_gain_cost_to_threshold < receipt.fifo_cost_to_threshold
    assert set(receipt.information_gain_order) == set(receipt.fifo_order)
    assert receipt.provider_effect is False
    assert len(receipt.receipt_sha256) == 64


def test_simulation_summary_preserves_truth_boundaries():
    summary = simulation_summary()
    assert summary["truth_boundary"]["simulation_is_not_owner_value_proof"] is True
    assert summary["truth_boundary"]["simulation_is_not_provider_runtime_proof"] is True
    assert summary["truth_boundary"]["provider_effect"] is False
    assert summary["truth_boundary"]["stable_promotion_authorized"] is False

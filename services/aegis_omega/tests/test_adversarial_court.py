from aegis_omega.adversarial.court import run_adversarial_court

def test_adversarial_production_court_passes_all_synthetic_cases():
    receipt=run_adversarial_court()
    assert receipt.scenario_count == 11
    assert receipt.scenario_pass_count == receipt.scenario_count
    assert receipt.threat_recall == 1.0
    assert receipt.benign_specificity == 1.0
    assert receipt.replay_resistance_passed is True
    assert receipt.source_concentration_resistance_passed is True
    assert receipt.privacy_minimization_passed is True
    assert receipt.neural_receipt.shadow_only is True
    assert receipt.neural_receipt.synthetic_training_only is True
    assert receipt.tournament_receipt.auto_promotion_performed is False
    assert receipt.provider_effect_performed is False
    assert receipt.stable_promotion_authorized is False

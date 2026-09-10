from aegis_omega.adversarial.twin import scenario_suite
from aegis_omega.adversarial.evolution_tournament import PolicyGenome, run_policy_tournament
def test_policy_genome_requires_normalized_primary_weights():
    try: PolicyGenome('bad',max_weight=.9).validate()
    except ValueError as exc: assert 'SUM_TO_1' in str(exc)
    else: raise AssertionError('invalid genome accepted')
def test_evolution_tournament_never_auto_promotes():
    receipt=run_policy_tournament(scenario_suite()); assert receipt.candidate_count==24; assert receipt.champion_is_shadow_candidate is True; assert receipt.auto_promotion_performed is False; assert receipt.quality_floor_passed is True

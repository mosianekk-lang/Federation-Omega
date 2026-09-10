from aegis_omega.schemas import CandidateMetrics
from aegis_omega.evolution.certifier import certify

def good():
    return dict(candidate_id="c", unseen_family_recall=.95, false_positive_rate=.01, privacy_leakage=0, poisoning_resilience=.95, drift_resilience=.95, adversarial_resilience=.95, calibration_error=.02, rollback_test_passed=True, provenance_test_passed=True, shadow_test_passed=True, canary_test_passed=True)

def test_good_candidate_is_only_eligible_for_signed_promotion():
    r=certify(CandidateMetrics(**good())); assert r.certified; assert r.promotion == "eligible_for_signed_human_promotion"

def test_failed_gate_rejects():
    d=good(); d["false_positive_rate"]=.10; r=certify(CandidateMetrics(**d)); assert not r.certified; assert r.promotion == "reject"

from __future__ import annotations
from . import registry
from ..schemas import CandidateMetrics, CertificationResult

_THRESHOLDS = {
    "unseen_family_recall": (">=", 0.90),
    "false_positive_rate": ("<=", 0.02),
    "privacy_leakage": ("<=", 0.001),
    "poisoning_resilience": (">=", 0.90),
    "drift_resilience": (">=", 0.90),
    "adversarial_resilience": (">=", 0.90),
    "calibration_error": ("<=", 0.05),
}


def certify(metrics: CandidateMetrics) -> CertificationResult:
    failed = []
    for name, (op, threshold) in _THRESHOLDS.items():
        value = getattr(metrics, name)
        ok = value >= threshold if op == ">=" else value <= threshold
        if not ok:
            failed.append(f"{name} {op} {threshold}")
    for name in ["rollback_test_passed", "provenance_test_passed", "shadow_test_passed", "canary_test_passed"]:
        if not getattr(metrics, name):
            failed.append(name)
    certified = not failed
    result = CertificationResult(candidate_id=metrics.candidate_id, certified=certified,
                                 failed_gates=failed,
                                 promotion="eligible_for_signed_human_promotion" if certified else "reject")
    registry.record(result)
    return result

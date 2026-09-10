def calibrated_probability(raw_score: float, evidence_count: int) -> float:
    raw = max(0.0, min(1.0, raw_score))
    # Conservative evidence-count shrinkage: low evidence is pulled toward uncertainty.
    weight = min(1.0, max(0.0, evidence_count / 4.0))
    return max(0.0, min(1.0, 0.5 * (1.0 - weight) + raw * weight))

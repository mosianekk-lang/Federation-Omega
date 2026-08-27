from federation.lona_quant_node.robustness import RunMetrics, RobustnessEvidence, promotion_score


def run(ret, sharpe, dd, trades=12):
    return RunMetrics(total_return=ret, sharpe=sharpe, max_drawdown=dd, trades=trades)


def test_strong_evidence_can_reach_research_admission():
    evidence = RobustnessEvidence(
        holdout=run(35, 1.1, 16),
        benchmark=run(25, 0.8, 20),
        perturbations=(run(29, 0.9, 18), run(31, 1.0, 17), run(21, 0.8, 19)),
        cross_assets=(run(20, 0.8, 18), run(12, 0.7, 17)),
        adverse_cost=run(25, 0.8, 18),
    )
    result = promotion_score(evidence)
    assert result['state'] == 'ROBUSTNESS_RESEARCH_ADMITTED'


def test_weak_holdout_is_not_promoted():
    evidence = RobustnessEvidence(
        holdout=run(-5, -0.2, 35, trades=3),
        benchmark=run(25, 0.8, 20),
        perturbations=(run(-2, -0.1, 30), run(1, 0.1, 28)),
        cross_assets=(run(-8, -0.3, 32), run(-3, -0.1, 29)),
        adverse_cost=run(-10, -0.4, 40),
    )
    result = promotion_score(evidence)
    assert result['state'] == 'REJECT_OR_QUARANTINE'


def test_positive_return_alone_does_not_imply_admission():
    evidence = RobustnessEvidence(
        holdout=run(10, 0.3, 31, trades=4),
        benchmark=run(35, 1.0, 20),
        perturbations=(run(4, 0.2, 30), run(-1, 0.0, 34)),
        cross_assets=(run(2, 0.1, 33), run(-4, -0.2, 36)),
        adverse_cost=run(1, 0.1, 34),
    )
    result = promotion_score(evidence)
    assert result['state'] != 'ROBUSTNESS_RESEARCH_ADMITTED'

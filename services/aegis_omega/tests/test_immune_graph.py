from aegis_omega.adversarial.twin import AdversarialScenario, build_scenario
from aegis_omega.adversarial.immune_graph import analyze_evidence_graph

def test_replay_graph_detects_duplicates_and_penalizes_trust():
    report=analyze_evidence_graph(build_scenario(AdversarialScenario.REPLAY_FLOOD).events); assert report.duplicate_events==19; assert report.replay_ratio>.9; assert report.poisoning_resistance_factor<=.4
def test_source_concentration_is_detected():
    report=analyze_evidence_graph(build_scenario(AdversarialScenario.SOURCE_CONCENTRATION).events); assert report.independent_sources==1; assert report.source_concentration==1.0; assert report.poisoning_resistance_factor<.5
def test_cross_source_convergence_has_high_corroboration():
    report=analyze_evidence_graph(build_scenario(AdversarialScenario.CROSS_SOURCE_CONVERGENCE).events); assert report.independent_sources==4; assert report.independent_classes==4; assert report.corroboration_score>=.95; assert report.poisoning_resistance_factor==1.0

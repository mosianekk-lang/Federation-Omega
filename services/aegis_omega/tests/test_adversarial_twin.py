from aegis_omega.adversarial.twin import AdversarialScenario, build_scenario, scenario_suite

def test_suite_covers_each_scenario_once():
    suite=scenario_suite()
    assert len(suite) == len(AdversarialScenario)
    assert {x.scenario for x in suite} == set(AdversarialScenario)
    assert all(all(e.consent for e in x.events) for x in suite)

def test_replay_flood_reuses_same_event_identity():
    case=build_scenario(AdversarialScenario.REPLAY_FLOOD)
    assert len({e.event_id for e in case.events}) == 1
    assert len(case.events) >= 10

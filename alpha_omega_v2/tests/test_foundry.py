from alpha_omega_foundry import SolutionFoundry

def test_operational_release(tmp_path):
    idea={"title":"T","description":"Build an operational data workflow","users":["u"],"outcomes":["o"]}
    r=SolutionFoundry(tmp_path).operational_release(idea)
    assert r["state"]=="OPERATIONAL_VERIFIED_LOCAL"
    assert r["readback"]["pass"] is True
    assert r["persistence"]["pass"] is True
    assert r["health"]["pass"] is True
    assert r["rollback"]["target_absent"] is True

def test_portfolio_order(tmp_path):
    ideas=[
        {"title":"A","description":"a","value":4,"urgency":3,"reuse":2,"risk":8,"complexity":8},
        {"title":"B","description":"b","value":9,"urgency":9,"reuse":9,"risk":2,"complexity":3},
    ]
    ranked=SolutionFoundry(tmp_path).score_portfolio(ideas)
    assert ranked[0]["idea"]["title"]=="B"

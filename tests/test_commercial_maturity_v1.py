from federation.commercial_maturity_v1 import CommercialMaturityController


def test_commercial_ready_requires_every_applicable_gate():
    c=CommercialMaturityController(("FUNCTIONALITY","SECURITY","RELIABILITY"))
    assert c.evaluate({"FUNCTIONALITY":True,"SECURITY":True}).state=="COMMERCIAL_MATURITY_OPEN"
    assert c.evaluate({"FUNCTIONALITY":True,"SECURITY":True,"RELIABILITY":True}).state=="COMMERCIAL_READY_VERIFIED"


def test_failed_gate_cannot_be_hidden_by_other_passes():
    c=CommercialMaturityController(("FUNCTIONALITY","SECURITY","RELIABILITY"))
    court=c.evaluate({"FUNCTIONALITY":True,"SECURITY":False,"RELIABILITY":True})
    assert court.state=="COMMERCIAL_MATURITY_OPEN" and court.failed==("SECURITY",)

from aegis_omega.storage import build_case_store
from aegis_omega.evidence_store import build_evidence_store
from aegis_omega.event_bus import build_event_bus
from aegis_omega.schemas import Assessment
def test_local_adapters_are_safe_defaults():
    assert build_case_store('memory').get('missing') is None; assert build_evidence_store('').__class__.__name__=='NullEvidenceStore'; assert build_event_bus('','').__class__.__name__=='NullEventBus'
def test_no_high_impact_side_effect_from_event_bus_default():
    a=Assessment(case_id='case',risk_score=.2,confidence=.5,disposition='observe',signals=[]); assert build_event_bus('','').publish_assessment(a) is None

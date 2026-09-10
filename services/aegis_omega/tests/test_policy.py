from aegis_omega.schemas import Assessment
from aegis_omega.policy import plan_response
def test_high_impact_actions_need_approval():
    a=Assessment(case_id='c',risk_score=.95,confidence=.95,disposition='containment_recommended',signals=[],requires_human_approval=True); p=plan_response(a); assert 'isolate_enterprise_access' in p.approval_required; assert 'isolate_enterprise_access' not in p.automated

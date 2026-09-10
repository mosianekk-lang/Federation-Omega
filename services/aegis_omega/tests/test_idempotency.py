import pytest
from fastapi.testclient import TestClient
from aegis_omega.storage import InMemoryCaseStore, IdempotencyCollision
from aegis_omega.schemas import Assessment
from aegis_omega.api import app

def test_memory_store_idempotent_replay_and_collision():
    store=InMemoryCaseStore(); a=Assessment(case_id='c1',risk_score=.2,confidence=.4,disposition='observe',signals=[]); first=store.put(a,[],request_id='request-1',request_hash='hash-a'); assert store.resolve_request('request-1','hash-a')==first
    with pytest.raises(IdempotencyCollision): store.resolve_request('request-1','hash-b')
def test_api_assessment_request_is_idempotent_and_collision_fails_closed():
    client=TestClient(app); body={'request_id':'request-123','events':[{'event_id':'idem-a','device_id':'dev','event_class':'network_risk','severity':.2,'source':'net','consent':True}]}; a=client.post('/v1/assess',json=body); b=client.post('/v1/assess',json=body); assert a.status_code==b.status_code==200; assert a.json()['case_id']==b.json()['case_id']; changed={**body,'events':[{'event_id':'idem-b','device_id':'dev','event_class':'network_risk','severity':.9,'source':'net','consent':True}]}; assert client.post('/v1/assess',json=changed).status_code==409
def test_api_caps_assessment_batch_size():
    client=TestClient(app); event={'event_id':'abc','device_id':'dev','event_class':'network_risk','severity':.2,'source':'net','consent':True}; events=[]
    for i in range(257): row=dict(event); row['event_id']=f'event-{i}'; events.append(row)
    assert client.post('/v1/assess',json={'request_id':'too-many-001','events':events}).status_code==422
def test_outbox_failure_is_retry_healed(monkeypatch):
    import aegis_omega.api as api
    class FlakyBus:
        def __init__(self): self.calls=0
        def publish_assessment(self,assessment): self.calls+=1; (_ for _ in ()).throw(RuntimeError('synthetic pubsub outage')) if self.calls==1 else None; return 'provider-message-1'
    bus=FlakyBus(); monkeypatch.setattr(api,'event_bus',bus); client=TestClient(app); body={'request_id':'outbox-retry-001','events':[{'event_id':'outbox-a','device_id':'dev','event_class':'device_integrity','severity':.7,'source':'integrity','consent':True}]}; first=client.post('/v1/assess',json=body); assert first.status_code==503; second=client.post('/v1/assess',json=body); assert second.status_code==200; case=client.get(f"/v1/cases/{second.json()['case_id']}"); assert case.status_code==200 and case.json()['evidence_chain_valid'] is True

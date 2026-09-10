from aegis_omega.schemas import SecurityEvent, EventClass
from aegis_omega.provenance import seal_event, verify_event_with_keyring
from aegis_omega.evidence_chain import compile_evidence_chain, verify_evidence_chain
def _sealed(i,key='k1',secret='a'*32):
    e=SecurityEvent(event_id=f'event-{i}',device_id='dev',event_class=EventClass.APP_RISK,severity=.4,source='sensor',consent=True); return seal_event(e,secret,key)
def test_evidence_chain_detects_tampering():
    events=[_sealed(1),_sealed(2)]; chain=compile_evidence_chain(events); assert verify_evidence_chain(events,chain); broken=[dict(x) for x in chain]; broken[1]['previous_hash']='bad'; assert not verify_evidence_chain(events,broken)
def test_keyring_supports_provenance_key_rotation_reference():
    old=_sealed(1,'key-v1','a'*32); new=_sealed(2,'key-v2','b'*32); ring={'key-v1':'a'*32,'key-v2':'b'*32}; assert verify_event_with_keyring(old,ring); assert verify_event_with_keyring(new,ring); assert not verify_event_with_keyring(old,{'key-v2':'b'*32})

from aegis_omega.schemas import SecurityEvent,EventClass
from aegis_omega.normalize import normalize_event
from aegis_omega.provenance import seal_event,verify_event
def test_seal_and_verify_and_minimize():
    e=SecurityEvent(event_id='abc',device_id='dev',event_class=EventClass.APP_RISK,severity=.5,source=' TestSensor ',attributes={'password':'secret','feature':'ok'},consent=True); n=normalize_event(e); assert n.source=='testsensor'; assert n.attributes['password']=='[minimized]'; s=seal_event(n,'key'); assert verify_event(s,'key'); assert not verify_event(s,'wrong')

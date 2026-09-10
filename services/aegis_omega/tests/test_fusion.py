from aegis_omega.schemas import SecurityEvent, EventClass
from aegis_omega.fusion import assess_events
def ev(i,cls,source,sev=.95,conf=.95): return SecurityEvent(event_id=f'evt{i}',device_id='dev',event_class=cls,severity=sev,confidence=conf,source=source,consent=True)
def test_corroboration_escalates_multisource_case():
    a=assess_events([ev(1,EventClass.DEVICE_INTEGRITY,'integrity'),ev(2,EventClass.FORENSIC_ARTIFACT,'forensics'),ev(3,EventClass.NETWORK_RISK,'network'),ev(4,EventClass.IDENTITY_RISK,'identity')]); assert a.disposition in {'investigate','containment_recommended'}; assert a.confidence>=.9; assert a.requires_human_approval is True
def test_single_weak_signal_not_conviction():
    a=assess_events([ev(1,EventClass.NETWORK_RISK,'network',.15,.5)]); assert a.disposition=='observe'

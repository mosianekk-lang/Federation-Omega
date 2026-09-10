from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from enum import Enum
import random
from ..schemas import EventClass,SecurityEvent
class AdversarialScenario(str,Enum):
    BENIGN_BASELINE="benign_baseline"; BENIGN_BURST="benign_burst"; CROSS_SOURCE_CONVERGENCE="cross_source_convergence"; LOW_AND_SLOW="low_and_slow"; SENSOR_DROPOUT="sensor_dropout"; SOURCE_CONCENTRATION="source_concentration"; REPLAY_FLOOD="replay_flood"; CONFIDENCE_POISON="confidence_poison"; CLOCK_SKEW="clock_skew"; PARTIAL_EVIDENCE="partial_evidence"; PRIVACY_PRESSURE="privacy_pressure"
@dataclass(frozen=True,slots=True)
class ScenarioCase:
    scenario:AdversarialScenario; events:tuple[SecurityEvent,...]; expected_min_disposition:str; expected_threat_like:bool; rationale:str
def _event(idx,cls,source,severity,confidence,*,base,minutes=0,event_id=None,attributes=None):
    return SecurityEvent(event_id=event_id or f"sim-{idx:03d}",device_id="synthetic-device",timestamp=base+timedelta(minutes=minutes),event_class=cls,severity=severity,confidence=confidence,source=source,attributes={"synthetic":True,**(attributes or {})},consent=True)
def build_scenario(scenario:AdversarialScenario,*,seed:int=7)->ScenarioCase:
    rng=random.Random(seed); base=datetime(2026,1,1,12,0,tzinfo=timezone.utc)
    if scenario is AdversarialScenario.BENIGN_BASELINE:return ScenarioCase(scenario,(_event(1,EventClass.CONTROL_STATE,"platform",.08,.95,base=base),_event(2,EventClass.NETWORK_RISK,"network",.10,.70,base=base,minutes=1)),"observe",False,"Low-severity benign control/network noise.")
    if scenario is AdversarialScenario.BENIGN_BURST:return ScenarioCase(scenario,tuple(_event(i,EventClass.NETWORK_RISK,"network",.12+rng.random()*.06,.75,base=base,minutes=i,event_id=f"benign-{i}") for i in range(1,14)),"observe",False,"High-volume benign single-source burst must not inflate risk.")
    if scenario is AdversarialScenario.CROSS_SOURCE_CONVERGENCE:return ScenarioCase(scenario,(_event(1,EventClass.DEVICE_INTEGRITY,"integrity",.92,.94,base=base),_event(2,EventClass.FORENSIC_ARTIFACT,"forensics",.95,.96,base=base,minutes=2),_event(3,EventClass.IDENTITY_RISK,"identity",.84,.86,base=base,minutes=3),_event(4,EventClass.NETWORK_RISK,"network",.80,.82,base=base,minutes=4)),"investigate",True,"Independent high-confidence defensive signals converge.")
    if scenario is AdversarialScenario.LOW_AND_SLOW:return ScenarioCase(scenario,(_event(1,EventClass.APP_RISK,"app",.55,.72,base=base),_event(2,EventClass.NETWORK_RISK,"network",.58,.70,base=base,minutes=20),_event(3,EventClass.IDENTITY_RISK,"identity",.61,.74,base=base,minutes=45),_event(4,EventClass.CONTROL_STATE,"platform",.50,.80,base=base,minutes=55)),"investigate",True,"Moderate independent signals accumulate over time.")
    if scenario is AdversarialScenario.SENSOR_DROPOUT:return ScenarioCase(scenario,(_event(1,EventClass.DEVICE_INTEGRITY,"integrity",.91,.93,base=base),_event(2,EventClass.FORENSIC_ARTIFACT,"forensics",.92,.94,base=base,minutes=4)),"investigate",True,"Threat-like case remains detectable with major sensor loss.")
    if scenario is AdversarialScenario.SOURCE_CONCENTRATION:return ScenarioCase(scenario,tuple(_event(i,EventClass.APP_RISK if i%2 else EventClass.NETWORK_RISK,"single-sensor",.88,.90,base=base,minutes=i,event_id=f"concentrated-{i}") for i in range(1,13)),"observe",False,"Single-source high volume is treated as suspicious evidence quality, not automatic compromise.")
    if scenario is AdversarialScenario.REPLAY_FLOOD:
        original=_event(1,EventClass.NETWORK_RISK,"network",.87,.89,base=base,event_id="replay-same"); return ScenarioCase(scenario,tuple(original.model_copy() for _ in range(20)),"observe",False,"Duplicate event replay must not manufacture corroboration.")
    if scenario is AdversarialScenario.CONFIDENCE_POISON:return ScenarioCase(scenario,(_event(1,EventClass.APP_RISK,"sensor-a",.99,1.0,base=base),_event(2,EventClass.APP_RISK,"sensor-a",.98,1.0,base=base,minutes=1),_event(3,EventClass.CONTROL_STATE,"platform",.10,.95,base=base,minutes=2)),"observe",False,"Extreme confidence from one source/class is capped by graph diversity.")
    if scenario is AdversarialScenario.CLOCK_SKEW:return ScenarioCase(scenario,(_event(1,EventClass.DEVICE_INTEGRITY,"integrity",.88,.91,base=base),_event(2,EventClass.FORENSIC_ARTIFACT,"forensics",.90,.91,base=base,minutes=1800),_event(3,EventClass.IDENTITY_RISK,"identity",.75,.80,base=base,minutes=1860)),"investigate",True,"Temporal incoherence lowers confidence but does not erase independent evidence.")
    if scenario is AdversarialScenario.PARTIAL_EVIDENCE:return ScenarioCase(scenario,(_event(1,EventClass.PLATFORM_ALERT,"platform",.82,.78,base=base),_event(2,EventClass.NETWORK_RISK,"network",.72,.70,base=base,minutes=3)),"investigate",True,"Two independent partial signals should trigger investigation, not automatic containment.")
    if scenario is AdversarialScenario.PRIVACY_PRESSURE:return ScenarioCase(scenario,(_event(1,EventClass.PLATFORM_ALERT,"platform",.20,.80,base=base,attributes={"message_body":"sensitive synthetic content","token":"synthetic-token","safe_flag":"ok"}),),"observe",False,"Sensitive content keys must be minimized before persistence or inference.")
    raise ValueError(f"unsupported scenario: {scenario}")
def scenario_suite(*,seed:int=7)->tuple[ScenarioCase,...]:return tuple(build_scenario(item,seed=seed+index) for index,item in enumerate(AdversarialScenario))

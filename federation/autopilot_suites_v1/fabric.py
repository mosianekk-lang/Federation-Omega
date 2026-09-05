from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from federation.autopilot_suites_v1.event_wake_mesh import EventWakeMesh, EventEnvelope
from federation.autopilot_suites_v1.durable_park_resume import DurableParkResume
from federation.autopilot_suites_v1.external_wait_state_machine import ExternalWaitStateMachine
from federation.autopilot_suites_v1.mission_air_traffic_control import MissionAirTrafficControl
from federation.autopilot_suites_v1.adaptive_wake_cadence import AdaptiveWakeCadence
from federation.autopilot_suites_v1.trigger_recovery_reflexes import TriggerRecoveryReflexes
from federation.autopilot_suites_v1.opportunity_autopilot import OpportunityAutopilot
from federation.autopilot_suites_v1.autonomous_deadline_engine import AutonomousDeadlineEngine
from federation.autopilot_suites_v1.autopilot_value_governor import AutopilotValueGovernor

SUITE_IDS=(
 'EVENT_WAKE_MESH','DURABLE_PARK_RESUME','ADAPTIVE_WAKE_CADENCE','MISSION_AIR_TRAFFIC_CONTROL',
 'SCOPED_AUTO_APPROVAL_MEMORY','TRIGGER_RECOVERY_REFLEXES','EXTERNAL_WAIT_STATE_MACHINE','OPPORTUNITY_AUTOPILOT',
 'AUTONOMOUS_DEADLINE_ENGINE','PERSISTENT_MISSION_SANDBOX','AUTOPILOT_VALUE_GOVERNOR')

@dataclass(frozen=True)
class FabricReceipt:
    event_id: str
    woken_missions: tuple[str,...]
    resumed_missions: tuple[str,...]
    authority_delta: str='NONE'
    external_effect: bool=False

class AutopilotSuitesFabric:
    """Thin composition fabric. It is not another scheduler or authority plane."""
    def __init__(self,state_dir:str|Path):
        p=Path(state_dir); p.mkdir(parents=True,exist_ok=True)
        self.event_mesh=EventWakeMesh(); self.park=DurableParkResume(p/'park.json'); self.wait=ExternalWaitStateMachine()
        self.traffic=MissionAirTrafficControl(); self.cadence=AdaptiveWakeCadence(); self.reflex=TriggerRecoveryReflexes.defaults()
        self.opportunity=OpportunityAutopilot(); self.deadline=AutonomousDeadlineEngine(); self.value=AutopilotValueGovernor(p/'value.json')
    def handle_event(self,e:EventEnvelope):
        wake=self.event_mesh.ingest(e)
        ev={'event_id':e.event_id,'kind':e.event_type,'key':e.subject,'value':e.payload_hash,'wait_state':e.event_type}
        resumed=set(self.park.resume_for_event(ev))|set(self.wait.on_event(ev))
        return FabricReceipt(e.event_id,wake.matched_missions,tuple(sorted(resumed)))
    @property
    def suite_count(self): return len(SUITE_IDS)

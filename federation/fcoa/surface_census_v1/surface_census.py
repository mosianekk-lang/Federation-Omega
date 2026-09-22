from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping

class Observation(str, Enum):
    USER_VISIBLE_ACTIVE = "USER_VISIBLE_ACTIVE"
    SCREENSHOT_VISIBLE_ACTIVE = "SCREENSHOT_VISIBLE_ACTIVE"
    CONNECTOR_ONLINE = "CONNECTOR_ONLINE"
    CONNECTOR_OFFLINE = "CONNECTOR_OFFLINE"
    CONNECTOR_PING_OK = "CONNECTOR_PING_OK"
    CONNECTOR_PING_FAILED = "CONNECTOR_PING_FAILED"
    LOCAL_HELPER_HEARTBEAT = "LOCAL_HELPER_HEARTBEAT"
    LOCALLLM_HEARTBEAT = "LOCALLLM_HEARTBEAT"
    TERMINAL_EXEC_OK = "TERMINAL_EXEC_OK"
    GUI_ACTION_OK = "GUI_ACTION_OK"
    GUI_ACTION_UNAVAILABLE = "GUI_ACTION_UNAVAILABLE"

class RouteState(str, Enum):
    QUALIFIED = "QUALIFIED"
    REACHABLE_NO_GUI_ACTION = "REACHABLE_NO_GUI_ACTION"
    UNREACHABLE = "UNREACHABLE"
    UNKNOWN = "UNKNOWN"

@dataclass(frozen=True)
class SurfaceEvidence:
    route_id: str
    observations: frozenset[Observation]
    capabilities: frozenset[str] = frozenset()
    metadata: Mapping[str, str] = field(default_factory=dict)

@dataclass(frozen=True)
class RouteAssessment:
    route_id: str
    state: RouteState
    reason: str
    capabilities: frozenset[str]

@dataclass(frozen=True)
class DeviceAssessment:
    device_state: str
    control_state: str
    routes: tuple[RouteAssessment, ...]
    next_action: str
    evidence_rule: str = "ROUTE_OFFLINE_NE_DEVICE_OFFLINE"

GUI_CAPS = frozenset({
    "device.screen.read","device.pointer.move","device.pointer.click",
    "device.pointer.scroll","device.keyboard.key","device.keyboard.text",
})

class FCOASurfaceCensus:
    def assess_route(self, ev: SurfaceEvidence) -> RouteAssessment:
        obs,caps=ev.observations,ev.capabilities
        if Observation.GUI_ACTION_OK in obs or GUI_CAPS.issubset(caps):
            return RouteAssessment(ev.route_id,RouteState.QUALIFIED,"GUI_CONTROL_PROVEN",caps)
        if Observation.LOCAL_HELPER_HEARTBEAT in obs and ("device.keyboard.text" in caps or "device.pointer.click" in caps):
            return RouteAssessment(ev.route_id,RouteState.QUALIFIED,"LOCAL_HELPER_GUI_CONTROL",caps)
        if Observation.TERMINAL_EXEC_OK in obs:
            return RouteAssessment(ev.route_id,RouteState.REACHABLE_NO_GUI_ACTION,"TERMINAL_REACHABLE_CAN_BOOTSTRAP_HELPER_OR_WIN32",caps)
        if Observation.CONNECTOR_ONLINE in obs or Observation.CONNECTOR_PING_OK in obs or Observation.LOCALLLM_HEARTBEAT in obs:
            return RouteAssessment(ev.route_id,RouteState.REACHABLE_NO_GUI_ACTION,"ROUTE_REACHABLE_GUI_UNPROVEN",caps)
        if Observation.CONNECTOR_OFFLINE in obs or Observation.CONNECTOR_PING_FAILED in obs:
            return RouteAssessment(ev.route_id,RouteState.UNREACHABLE,"THIS_ROUTE_UNREACHABLE_ONLY",caps)
        return RouteAssessment(ev.route_id,RouteState.UNKNOWN,"NO_CURRENT_ROUTE_EVIDENCE",caps)

    def assess_device(self, evidence: Iterable[SurfaceEvidence]) -> DeviceAssessment:
        evidence=tuple(evidence); routes=tuple(self.assess_route(e) for e in evidence)
        visible=any(Observation.USER_VISIBLE_ACTIVE in e.observations or Observation.SCREENSHOT_VISIBLE_ACTIVE in e.observations for e in evidence)
        qualified=[r for r in routes if r.state==RouteState.QUALIFIED]
        reachable=[r for r in routes if r.state in {RouteState.QUALIFIED,RouteState.REACHABLE_NO_GUI_ACTION}]
        unknown=[r for r in routes if r.state==RouteState.UNKNOWN]
        if qualified:
            return DeviceAssessment("OBSERVED_ACTIVE" if visible else "PRESUMED_ACTIVE_FROM_CONTROL_PROOF","GUI_CONTROL_QUALIFIED",routes,"USE_BEST_QUALIFIED_ROUTE")
        if reachable:
            return DeviceAssessment("OBSERVED_ACTIVE" if visible else "REACHABLE","CONTROL_ROUTE_REACHABLE_GUI_BOOTSTRAP_REQUIRED",routes,"BOOTSTRAP_FCOA_DEVICE_HELPER_OR_WIN32_SENDINPUT_THROUGH_REACHABLE_ROUTE")
        if visible:
            return DeviceAssessment("OBSERVED_ACTIVE","ACTIVE_BUT_NOT_CURRENTLY_REACHABLE_BY_ENUMERATED_CONTROL_ROUTES",routes,"HARVEST_OR_BIND_ALTERNATE_CONTROL_SURFACE;_DO_NOT_CALL_DEVICE_OFFLINE")
        if unknown:
            return DeviceAssessment("UNKNOWN","UNKNOWN_NOT_ABSENT",routes,"COMPLETE_ESTATE_CENSUS_BEFORE_ABSENCE_CLAIM")
        return DeviceAssessment("UNREACHABLE_AFTER_ENUMERATED_ROUTE_CENSUS","NO_QUALIFIED_CONTROL_ROUTE",routes,"RETRY_ONLY_WITH_CHANGED_MECHANISM_OR_NEW_ROUTE_EVIDENCE")

    @staticmethod
    def preferred_route(routes: Iterable[RouteAssessment]) -> str | None:
        priority={"direct_gui":0,"computer_use":1,"local_helper":2,"remote_terminal_helper":3,"remote_terminal_win32":4,"localllm_bridge":5,"vm_gui":6}
        q=[r for r in routes if r.state==RouteState.QUALIFIED]
        if not q: return None
        q.sort(key=lambda r:(priority.get(r.route_id,100),r.route_id))
        return q[0].route_id

    @staticmethod
    def residual_plan(routes: Iterable[RouteAssessment]) -> tuple[str,...]:
        routes=tuple(routes)
        if any(r.state==RouteState.QUALIFIED for r in routes):
            return ("USE_QUALIFIED_ROUTE",)
        if any(r.reason=="TERMINAL_REACHABLE_CAN_BOOTSTRAP_HELPER_OR_WIN32" for r in routes):
            return ("START_FCOA_DEVICE_CONTROL_HELPER_VIA_TERMINAL","IF_HELPER_UNAVAILABLE_USE_WIN32_SENDINPUT_AND_SCREEN_CAPTURE","VERIFY_SCREEN_FOREGROUND_CURSOR_READBACK")
        return ("CENSUS_DIRECT_GUI_COMPUTER_USE_REMOTE_TERMINAL_LOCALLLM_VM_ROUTES","BIND_OR_BUILD_OUTBOUND_DEVICE_BRIDGE","VERIFY_WITH_SCREEN_READBACK_AND_BENIGN_CURSOR_MOVE_RESTORE")

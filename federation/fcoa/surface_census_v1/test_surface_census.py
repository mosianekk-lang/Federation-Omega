from surface_census import *

def ev(route,*obs,caps=()):
    return SurfaceEvidence(route,frozenset(obs),frozenset(caps))

def test_one_offline_route_does_not_make_device_offline_when_screenshot_active():
    c=FCOASurfaceCensus(); d=c.assess_device([ev("rdc",Observation.CONNECTOR_OFFLINE),ev("vision",Observation.SCREENSHOT_VISIBLE_ACTIVE)])
    assert d.device_state=="OBSERVED_ACTIVE"; assert "DO_NOT_CALL_DEVICE_OFFLINE" in d.next_action

def test_terminal_route_can_bootstrap_gui_helper():
    c=FCOASurfaceCensus(); d=c.assess_device([ev("remote_terminal_helper",Observation.TERMINAL_EXEC_OK)])
    assert d.control_state=="CONTROL_ROUTE_REACHABLE_GUI_BOOTSTRAP_REQUIRED"

def test_local_helper_with_mouse_or_keyboard_is_qualified():
    assert FCOASurfaceCensus().assess_route(ev("local_helper",Observation.LOCAL_HELPER_HEARTBEAT,caps=("device.pointer.click",))).state==RouteState.QUALIFIED

def test_full_gui_capability_set_is_qualified_without_observation_flag():
    assert FCOASurfaceCensus().assess_route(ev("x",caps=GUI_CAPS)).state==RouteState.QUALIFIED

def test_unknown_is_not_absent():
    assert FCOASurfaceCensus().assess_device([ev("x")]).control_state=="UNKNOWN_NOT_ABSENT"

def test_all_routes_unreachable_is_census_scoped_not_physical_offline():
    assert FCOASurfaceCensus().assess_device([ev("a",Observation.CONNECTOR_OFFLINE),ev("b",Observation.CONNECTOR_PING_FAILED)]).device_state=="UNREACHABLE_AFTER_ENUMERATED_ROUTE_CENSUS"

def test_prefer_direct_gui():
    c=FCOASurfaceCensus(); rs=[c.assess_route(ev("local_helper",Observation.GUI_ACTION_OK)),c.assess_route(ev("direct_gui",Observation.GUI_ACTION_OK))]
    assert c.preferred_route(rs)=="direct_gui"

def test_prefer_computer_use_over_helper():
    c=FCOASurfaceCensus(); rs=[c.assess_route(ev("local_helper",Observation.GUI_ACTION_OK)),c.assess_route(ev("computer_use",Observation.GUI_ACTION_OK))]
    assert c.preferred_route(rs)=="computer_use"

def test_residual_plan_uses_terminal_helper():
    c=FCOASurfaceCensus(); p=c.residual_plan([c.assess_route(ev("remote_terminal_helper",Observation.TERMINAL_EXEC_OK))]); assert p[0]=="START_FCOA_DEVICE_CONTROL_HELPER_VIA_TERMINAL"

def test_residual_plan_builds_bridge_if_none_reachable():
    c=FCOASurfaceCensus(); p=c.residual_plan([c.assess_route(ev("rdc",Observation.CONNECTOR_OFFLINE))]); assert "BIND_OR_BUILD_OUTBOUND_DEVICE_BRIDGE" in p

def test_connector_online_without_gui_not_qualified():
    assert FCOASurfaceCensus().assess_route(ev("rdc",Observation.CONNECTOR_ONLINE)).state==RouteState.REACHABLE_NO_GUI_ACTION

def test_gui_action_ok_is_qualified():
    assert FCOASurfaceCensus().assess_route(ev("vm_gui",Observation.GUI_ACTION_OK)).state==RouteState.QUALIFIED

def test_visible_plus_reachable_without_gui_is_active():
    c=FCOASurfaceCensus(); assert c.assess_device([ev("vision",Observation.USER_VISIBLE_ACTIVE),ev("rdc",Observation.CONNECTOR_ONLINE)]).device_state=="OBSERVED_ACTIVE"

def test_visibility_alone_does_not_claim_control():
    assert FCOASurfaceCensus().assess_device([ev("vision",Observation.SCREENSHOT_VISIBLE_ACTIVE)]).control_state=="ACTIVE_BUT_NOT_CURRENTLY_REACHABLE_BY_ENUMERATED_CONTROL_ROUTES"

def test_terminal_and_offline_connector_selects_bootstrap_not_absence():
    c=FCOASurfaceCensus(); assert c.assess_device([ev("old_connector",Observation.CONNECTOR_OFFLINE),ev("remote_terminal_win32",Observation.TERMINAL_EXEC_OK)]).control_state=="CONTROL_ROUTE_REACHABLE_GUI_BOOTSTRAP_REQUIRED"

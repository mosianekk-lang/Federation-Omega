import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CFG=ROOT/"config"/"fuse-parallel-frontend-continuity-v1.json"

def load():
    return json.loads(CFG.read_text(encoding="utf-8"))

def test_parallel_frontend_contract():
    d=load()
    assert d["schema"]=="FUSE_PARALLEL_FRONTEND_CONTINUITY_V1"
    assert d["creates_new_controller"] is False
    assert d["scope_start"]=="2026-01-01"
    assert d["execution_model"]["frontend_lane"]=="OWNER_INTERACTION_PROJECTION_ONLY"
    assert d["execution_model"]["backend_lane"]=="DURABLE_SOVEREIGN_EXECUTION"
    laws=set(d["continuity_laws"])
    assert "FRONTEND_MESSAGE_NE_MISSION_RESTART" in laws
    assert "FRONTEND_MESSAGE_NE_GLOBAL_PAUSE" in laws
    assert "ONGOING_DEPLOYMENT_CONTINUES_IF_NONINTERSECTING" in laws
    assert "PARALLEL_LANE_PREFERRED_FOR_INDEPENDENT_NEW_WORK" in laws

def test_owner_input_classification():
    d=load()
    c=d["owner_input_classifier"]
    assert c["STATUS_OR_QUESTION"]=="READ_FROM_CURRENT_PROJECTION_WITHOUT_PAUSING_EXECUTION"
    assert "PARALLEL_WORK_LANE" in c["INDEPENDENT_NEW_OBJECTIVE"]
    assert "INTERSECTING_LANE" in c["CONFLICTING_OBJECTIVE"]

def test_autonomy_rules():
    d=load()
    laws=set(d["automation_laws"])
    assert "ALL_NONTERMINAL_SYSTEMS_AUTO_CONTINUE" in laws
    assert "AUTO_HARVEST_ON_TRUE_CAPABILITY_GAP" in laws
    assert "AUTO_BUILD_ONLY_MINIMUM_TRUE_RESIDUAL" in laws
    assert "AUTO_FAILOVER_FOR_PROVIDER_OR_ROUTE_FAILURE" in laws

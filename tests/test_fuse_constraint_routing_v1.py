import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CFG=ROOT/"config"/"fuse-constraint-routing-v1.json"

def load():
    return json.loads(CFG.read_text(encoding="utf-8"))

def test_constraint_routing_contract():
    d=load()
    assert d["schema"]=="FUSE_CONSTRAINT_ROUTING_V1"
    assert d["creates_new_controller"] is False
    assert "FAILED_ROUTE_NE_MISSION_FAILURE" in d["laws"]
    assert "LOCAL_BLOCKER_NE_GLOBAL_STALL" in d["laws"]
    assert "UNKNOWN_EFFECT_REQUIRES_READBACK" in d["laws"]
    assert d["classes"]["provider"]=="ALTERNATE_PROVIDER_OR_LOCAL"
    assert d["classes"]["source_fence"]=="HOLD_INTERSECTING_LANE_CONTINUE_DISJOINT"

def test_parallelism_is_effect_aware():
    d=load()
    assert d["parallelism"]["read_only"]=="SAFE_PARALLEL"
    assert d["parallelism"]["reversible_internal"]=="BOUNDED_PARALLEL"
    assert d["parallelism"]["effectful"]=="EFFECT_ID_SERIALIZED"

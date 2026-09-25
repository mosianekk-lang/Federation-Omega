import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CFG=ROOT/"config"/"fuse-24x7-autonomy-v1.json"

def load():
    return json.loads(CFG.read_text(encoding="utf-8"))

def test_24x7_contract():
    d=load()
    assert d["schema"]=="FUSE_24X7_AUTONOMY_V1"
    assert d["creates_new_controller"] is False
    assert d["operating_mode"]=="EVENT_DRIVEN_CONTINUOUS_WITH_HOURLY_FALLBACK_SWEEP"
    assert d["auto_harvest"]["enabled"] is True
    assert d["auto_build"]["enabled"] is True
    assert d["parallelism"]["local_blocker_global_stall"] is False
    assert d["owner_surface"]["recoverable_failure"]=="REPAIR_REROUTE_CONTINUE"

def test_autonomy_boundaries_and_reuse():
    d=load()
    assert d["autonomy"]["read_only"]=="AUTO"
    assert d["autonomy"]["reversible_internal"]=="AUTO"
    assert "BUILD_ONLY_TRUE_RESIDUALS" in d["auto_build"]["rule"]
    assert d["auto_build"]["no_duplicate_controller"] is True

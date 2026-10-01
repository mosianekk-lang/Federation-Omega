import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "fuse-forest-first-prompts-v2e.json"

def load():
    return json.loads(CFG.read_text(encoding="utf-8"))

def test_forest_first_v2e_contract():
    d = load()
    assert d["schema"] == "FUSE_FOREST_FIRST_PROMPT_PACK_V2E"
    assert d["chapter_range"] == "291-330"
    assert d["chapter_count"] == 40
    chapters = d["chapters"]
    nums = [x["chapter"] for x in chapters]
    ids = [x["id"] for x in chapters]
    assert nums == list(range(291, 331))
    assert len(ids) == len(set(ids))
    assert d["activation"]["safe_prework"] == "AUTO"
    assert d["activation"]["quiet_when_healthy"] is True
    assert d["activation"]["preserve_existing_mission_identity"] is True

def test_causal_preemption_coverage():
    d = load()
    ids = {x["id"] for x in d["chapters"]}
    required = {
        "MISSION_HORIZON_FORECAST",
        "HIDDEN_DEPENDENCY_INFERENCE",
        "PROOF_LAG_PREDICTOR",
        "FAILURE_PRECURSOR_CORRELATOR",
        "CROSS_MISSION_CONFLICT_PREEMPT",
        "SILENT_STALL_SENSOR",
        "PREEMPTIVE_OWNER_FRICTION_TEST",
        "FOREST_CAUSAL_FIXED_POINT",
    }
    assert required <= ids

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "fuse-forest-first-prompts-v2g.json"

def load():
    return json.loads(CFG.read_text(encoding="utf-8"))

def test_v2g_contract():
    d = load()
    assert d["schema"] == "FUSE_FOREST_FIRST_PROMPT_PACK_V2G"
    assert d["chapter_range"] == "351-400"
    assert d["chapter_count"] == 50
    assert len(d["chapters"]) == 50
    ids = [x["id"] for x in d["chapters"]]
    assert len(ids) == len(set(ids))
    nums = [x["chapter"] for x in d["chapters"]]
    assert nums == list(range(351, 401))
    assert d["activation"]["no_new_controller"] is True
    assert d["activation"]["preserve_existing_mission_identity"] is True

def test_v2g_is_preemptive_not_reactive_only():
    d = load()
    ids = {x["id"] for x in d["chapters"]}
    required = {
        "LATENT_REQUIREMENT_SYNTHESIS",
        "FUTURE_OWNER_QUESTION_PREDICTOR",
        "CAPABILITY_UNDERUSE_DETECTOR",
        "UPSTREAM_CHANGE_FORECAST",
        "HOT_STANDBY_QUALIFIER",
        "DEADLINE_FORESIGHT",
        "FRICTION_CAUSAL_PREDICTOR",
        "STATE_RECONCILIATION_BEFORE_FANOUT",
        "PREEMPTIVE_FINAL_ANSWER_SYNTHESIS",
        "OWNER_ZERO_SURPRISE_FIXED_POINT",
    }
    assert required <= ids

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "fuse-forest-first-prompts-v2f.json"

def load():
    return json.loads(CFG.read_text(encoding="utf-8"))

def test_v2f_contract():
    d = load()
    assert d["schema"] == "FUSE_FOREST_FIRST_PROMPT_PACK_V2F"
    assert d["chapter_count"] == 20
    nums = [x["chapter"] for x in d["chapters"]]
    assert nums == list(range(331, 351))
    ids = [x["id"] for x in d["chapters"]]
    assert len(ids) == len(set(ids))
    assert d["activation"]["preserve_existing_mission_identity"] is True

def test_unknown_unknown_and_final_mile_coverage():
    ids = {x["id"] for x in load()["chapters"]}
    assert {
        "UNKNOWN_UNKNOWN_SAMPLER",
        "FRAGILITY_MAP",
        "SEMANTIC_STATE_DIVERGENCE",
        "FINAL_MILE_CLOSURE_PREDICTOR",
        "PROOF_SUFFICIENCY_FORECAST",
        "FOREST_FINAL_MILE_FIXED_POINT",
    } <= ids

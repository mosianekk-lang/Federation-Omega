import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "fuse-forest-first-prompts-v2d.json"

def load():
    return json.loads(CFG.read_text(encoding="utf-8"))

def test_forest_first_v2d_contract():
    d = load()
    assert d["schema"] == "FUSE_FOREST_FIRST_PROMPT_PACK_V2D"
    assert d["parent"] == "FUSE_FOREST_FIRST_ANTICIPATORY_V1"
    assert d["chapter_range"] == "261-290"
    assert d["chapter_count"] == 30
    chapters = d["chapters"]
    assert len(chapters) == 30
    assert [x["chapter"] for x in chapters] == list(range(261,291))
    ids = [x["id"] for x in chapters]
    assert len(ids) == len(set(ids))

def test_estate_wide_preemptive_completion_scope():
    d = load()
    ids = {x["id"] for x in d["chapters"]}
    required = {
        "ESTATE_UNFINISHED_WORK_CENSUS",
        "REPAIR_QUEUE_WORK_STEAL",
        "OWNER_INTENT_DEBT_SWEEPER",
        "MIRROR_FALSE_PASS_REOPEN",
        "DEVICE_CARRIER_WATCH",
        "FOREST_GLOBAL_FIXED_POINT",
        "OWNER_INTERVENTION_BEFORE_IT_EXISTS",
    }
    assert required <= ids
    assert d["activation"]["scope"] == "ALL_GOVERNED_NONTERMINAL_FUSE_WORK"
    assert d["activation"]["safe_actions"] == "AUTO"

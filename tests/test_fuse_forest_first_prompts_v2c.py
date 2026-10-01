import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "fuse-forest-first-prompts-v2c.json"

def load():
    return json.loads(CFG.read_text(encoding="utf-8"))

def test_forest_first_v2c_contract():
    d = load()
    assert d["schema"] == "FUSE_FOREST_FIRST_PROMPT_PACK_V2C"
    assert d["parent"] == "FUSE_FOREST_FIRST_ANTICIPATORY_V1"
    assert d["chapter_range"] == "236-260"
    assert d["chapter_count"] == 25
    chapters = d["chapters"]
    assert len(chapters) == 25
    assert [x["chapter"] for x in chapters] == list(range(236,261))
    ids = [x["id"] for x in chapters]
    assert len(ids) == len(set(ids))
    assert d["activation"]["default_for_material_missions"] is True
    assert d["activation"]["safe_prework_only_without_new_effect_authority"] is True
    assert d["activation"]["quiet_when_healthy"] is True

def test_preemptive_pack_targets_owner_rescue_before_it_occurs():
    d = load()
    ids = {x["id"] for x in d["chapters"]}
    required = {
        "LATENT_NEED_DETECTOR",
        "OWNER_ATTENTION_FORECAST",
        "SRE_PREINCIDENT_MODE",
        "QUEUE_AGING_RESOLVER",
        "TRACE_TO_EVAL_LOOP",
        "FOREST_WORK_STEALER",
        "PREEMPTIVE_FIXED_POINT",
    }
    assert required <= ids

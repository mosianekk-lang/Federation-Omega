import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "fuse-forest-first-prompts-v2h.json"

def load():
    return json.loads(CFG.read_text(encoding="utf-8"))

def test_v2h_contract():
    d = load()
    assert d["schema"] == "FUSE_FOREST_FIRST_PROMPT_PACK_V2H"
    assert d["chapter_range"] == "401-450"
    assert d["chapter_count"] == 50
    assert len(d["chapters"]) == 50
    nums = [x["chapter"] for x in d["chapters"]]
    assert nums == list(range(401, 451))
    ids = [x["id"] for x in d["chapters"]]
    assert len(ids) == len(set(ids))
    assert d["activation"]["no_new_controller"] is True
    assert d["activation"]["quiet_when_healthy"] is True

def test_v2h_self_maintaining_coverage():
    d = load()
    ids = {x["id"] for x in d["chapters"]}
    required = {
        "INTENT_CHANGE_SENTINEL",
        "STALE_PROOF_REPLACER",
        "TOOL_CONTRACT_DRIFT_PREDICTOR",
        "PRODUCTION_SEMANTIC_CANARY",
        "REPAIR_QUEUE_AGING",
        "ENVIRONMENT_PARITY_WATCH",
        "OWNER_VALUE_FORECAST",
        "FOREST_SELF_MAINTAINING_FIXED_POINT",
    }
    assert required <= ids

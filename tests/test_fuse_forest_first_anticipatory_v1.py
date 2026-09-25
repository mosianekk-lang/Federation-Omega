import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "fuse-forest-first-anticipatory-v1.json"

def load():
    return json.loads(CFG.read_text(encoding="utf-8"))

def test_forest_first_contract():
    d = load()
    assert d["schema"] == "FUSE_FOREST_FIRST_ANTICIPATORY_V1"
    assert d["creates_new_controller"] is False
    assert d["forest"] == "FOREST_V2"
    laws = set(d["laws"])
    assert "KNOWN_NEXT_ACTION_CONTINUES_WITHOUT_REPEAT_PROMPT" in laws
    assert "SAFE_CURRENTNESS_REFRESH_HAPPENS_BEFORE_STALENESS" in laws
    assert "FAILOVER_IS_PREQUALIFIED_WHEN_SAFE" in laws
    assert "DISJOINT_READY_WORK_CONTINUES_AROUND_LOCAL_BLOCKERS" in laws
    assert "MISSING_PROOF_IS_DETECTED_BEFORE_TERMINAL_DELIVERY" in laws

def test_owner_interruptions_are_not_default():
    d = load()
    s = d["owner_surface"]
    assert s["healthy"] == "QUIET_CONTINUATION"
    assert s["recoverable_failure"] == "REPAIR_AND_CONTINUE"
    assert s["owner_only_decision"] == "SURFACE_PREPARED_DECISION"

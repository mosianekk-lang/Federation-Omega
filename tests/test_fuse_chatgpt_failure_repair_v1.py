import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "fuse-chatgpt-failure-repair-v1.json"

def load():
    return json.loads(CFG.read_text(encoding="utf-8"))

def test_repair_fabric_core():
    d = load()
    assert d["schema"] == "FUSE_CHATGPT_FAILURE_REPAIR_FABRIC_V1"
    assert d["creates_new_controller"] is False
    assert d["baseline"]["weekly_mirror_audit"]["fail_recompile"] == 57
    required = {
        "NONTERMINAL_OUTPUT",
        "SOURCE_OR_CONTROL_PROOF_NOT_OUTCOME",
        "NONTERMINAL_STOP_WITH_MACHINE_ROUTE",
        "SOURCE_CONTROL_STOP_WITH_MACHINE_ROUTE",
        "REPORT_ONLY_OR_NEXT_ACTION_STOP",
    }
    assert required <= set(d["mirror_failure_repairs"])
    for key in required:
        assert len(d["mirror_failure_repairs"][key]["changed_mechanism"]) >= 2

def test_repair_reuses_existing_mission():
    d = load()
    p = d["affected_weekly_false_pass_policy"]
    assert p["count"] == 57
    assert p["disposition"] == "REOPEN_SAME_MISSION"
    assert p["restart"] is False
    assert p["duplicate_mission"] is False
    laws = set(d["global_laws"])
    assert "SAME_SEMANTIC_FAILURE_REQUIRES_CHANGED_MECHANISM" in laws
    assert "COMPLETED_WORK_AND_VALID_PROOF_ARE_PRESERVED" in laws

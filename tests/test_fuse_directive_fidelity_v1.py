import json
from pathlib import Path

CFG=Path(__file__).resolve().parents[1]/"config"/"fuse-directive-fidelity-v1.json"

def load():
    return json.loads(CFG.read_text(encoding="utf-8"))

def test_core():
    d=load()
    assert d["schema"]=="FUSE_DIRECTIVE_FIDELITY_V1"
    assert d["creates_new_controller"] is False
    assert "PRESERVE_DIRECTIVE_VERB_FORCE" in d["invariants"]
    assert "DO_NOT_CONVERT_EXECUTION_REQUEST_TO_PLAN" in d["anti_dilution"]
    assert "DO_NOT_CONVERT_COMPLETION_REQUEST_TO_STATUS_REPORT" in d["anti_dilution"]
    assert d["constraint_handling"]["rule"]=="PRESERVE_DIRECTIVE_RECORD_CONSTRAINT_SEPARATELY"

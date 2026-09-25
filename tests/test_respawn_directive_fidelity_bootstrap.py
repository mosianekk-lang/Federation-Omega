import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/"respawn"/"federation_manifest.json"
SERVICE=ROOT/"respawn"/"bootstrap_service.py"

def test_manifest_requires_directive_fidelity():
    d=json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert "load_directive_fidelity_contract" in d["bootstrap_order"]
    assert "DIRECTIVE_FIDELITY_REQUIRED" in d["bootstrap_invariants"]
    f=d["directive_fidelity_bootstrap"]
    assert f["enabled"] is True
    assert f["contract_id"]=="FUSE-DIRECTIVE-FIDELITY-V1"

def test_bootstrap_guard_checks_directive_fidelity():
    s=SERVICE.read_text(encoding="utf-8")
    assert "DIRECTIVE_FIDELITY_DISABLED_OR_MISSING" in s
    assert "DIRECTIVE_FIDELITY_CONTRACT_ID_MISMATCH" in s
    assert '"directive_fidelity_bootstrap"' in s

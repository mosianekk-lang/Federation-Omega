import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/"respawn"/"federation_manifest.json"
SERVICE=ROOT/"respawn"/"bootstrap_service.py"
SNAP=ROOT/"config"/"fuse-bootstrap-memory-snapshot-v1.json"
IMPROVE=ROOT/"config"/"fuse-bootstrap-self-improvement-v1.json"

def test_bootstrap_memory_snapshot_is_required():
    m=json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert "load_bootstrap_memory_snapshot" in m["bootstrap_order"]
    assert "validate_bootstrap_memory_snapshot" in m["bootstrap_order"]
    assert "run_bootstrap_self_improvement" in m["bootstrap_order"]
    assert "BOOTSTRAP_MEMORY_SNAPSHOT_REQUIRED" in m["bootstrap_invariants"]
    assert "BOOTSTRAP_SELF_IMPROVEMENT_REQUIRED" in m["bootstrap_invariants"]

def test_snapshot_and_improvement_contracts():
    s=json.loads(SNAP.read_text(encoding="utf-8"))
    i=json.loads(IMPROVE.read_text(encoding="utf-8"))
    assert s["schema"]=="FUSE_BOOTSTRAP_MEMORY_SNAPSHOT_V1"
    assert s["baseline"]["boot_kernel"]=="5.9.0"
    assert s["baseline"]["output_mirror"]=="3.0.0"
    assert "PRESERVE_DIRECTIVE_VERB_FORCE" in s["settings"]
    assert i["schema"]=="FUSE_BOOTSTRAP_SELF_IMPROVEMENT_V1"
    assert i["promotion_gate"]["tie_behavior"]=="KEEP_CURRENT_CHAMPION"
    assert i["promotion_gate"]["rollback"] if "rollback" in i["promotion_gate"] else i["promotion_gate"]["require_rollback"] is True

def test_respawn_exposes_and_validates_memory():
    s=SERVICE.read_text(encoding="utf-8")
    assert "bootstrap_memory_bundle" in s
    assert "BOOTSTRAP_MEMORY_SNAPSHOT_MISSING_OR_INVALID" in s
    assert "BOOTSTRAP_SELF_IMPROVEMENT_MISSING_OR_INVALID" in s
    assert '"bootstrap_memory_snapshot"' in s
    assert '"bootstrap_self_improvement"' in s

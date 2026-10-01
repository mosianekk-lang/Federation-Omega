import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "fuse-unified-capability-fabric-v1.json"

def load():
    return json.loads(CFG.read_text(encoding="utf-8"))

def test_unified_capability_fabric_contract():
    d = load()
    assert d["schema"] == "FUSE_UNIFIED_CAPABILITY_FABRIC_V1"
    assert d["sovereign_controller_created"] is False
    assert d["owner_experience"] == "ONE_FUSE_SYSTEM"
    assert d["service_count"] == 35
    services = d["registered_services"]
    assert len(services) == 35
    assert len(set(services)) == 35
    flattened = [s for items in d["capability_families"].values() for s in items]
    assert set(flattened) == set(services)
    assert len(flattened) == len(services)
    path = d["canonical_path"]
    assert path[0] == "OWNER_INTENT"
    assert "estate.resolve" in path
    assert "runtime.transactional" in path
    assert "OUTPUT_MIRROR" in path
    assert path[-1] == "OWNER"
    assert "NO_DUPLICATE_CONTROLLER_OR_PRODUCT_ROOT" in d["resolution_law"]
    assert d["family_convergence"]["product_surface_default"] == "ONE_FUSE_ECOSYSTEM"

def test_owner_does_not_have_to_pick_internal_plumbing():
    d = load()
    hidden = set(d["owner_command_compiler"]["owner_should_not_choose"])
    assert {"provider","model","connector","runtime","tool_chain","retry_strategy","internal_service"} <= hidden

def test_source_not_mistaken_for_outcome():
    d = load()
    assert d["build_policy"]["source_is_terminal"] is False
    assert d["proof_policy"]["terminal_delivery_requires_proof"] is True

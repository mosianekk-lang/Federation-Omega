import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def _run_node(path: str) -> dict:
    proc = subprocess.run(
        ["node", str(ROOT / path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )
    return json.loads(proc.stdout)


def test_hyper_intelligence_performance_court():
    report = _run_node("benchmarks/hyper_intelligence_performance_court_v1.mjs")
    assert report["passed"] is True
    assert report["cases"] == 11
    assert report["failures"] == []


def test_hyper_binding_is_in_bootstrap_and_mirror_contracts():
    mirror = json.loads((ROOT / "config" / "fuse-output-mirror-v3.json").read_text(encoding="utf-8"))
    bootstrap = json.loads((ROOT / "config" / "fuse-bootstrap-inheritance-v3.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "respawn" / "federation_manifest.json").read_text(encoding="utf-8"))

    hipb = mirror["hyper_intelligence_performance"]
    assert hipb["contract_id"] == "FUSE-HIPB-001"
    assert hipb["enabled"] is True
    assert hipb["matched_benchmark_required_for_hyper_performance_claim"] is True

    order = bootstrap["required_order"]
    assert "HYPER_INTELLIGENCE_PERFORMANCE_BINDING" in order
    assert order.index("HYPER_INTELLIGENCE_PERFORMANCE_BINDING") < order.index("ROUTE_COMPILE")
    assert bootstrap["hyper_intelligence_performance"]["contract_id"] == "FUSE-HIPB-001"

    boot = manifest["bootstrap_order"]
    assert "load_hyper_intelligence_performance_contract" in boot
    assert "compile_hyper_intelligence_plan" in boot
    assert boot.index("compile_hyper_intelligence_plan") < boot.index("execute")
    assert "HYPER_INTELLIGENCE_PERFORMANCE_BINDING_REQUIRED" in manifest["bootstrap_invariants"]
    assert "HYPER_PERFORMANCE_CLAIMS_REQUIRE_MATCHED_EMPIRICAL_PROOF" in manifest["bootstrap_invariants"]


def test_source_binding_does_not_inflate_runtime_proof():
    governance = json.loads((ROOT / "governance" / "hyper_intelligence_performance_binding_v1.json").read_text(encoding="utf-8"))
    boundary = governance["truth_boundary"]
    assert boundary["sentience_claimed"] is False
    assert boundary["omniscience_claimed"] is False
    assert boundary["hyper_performance_requires_matched_empirical_proof"] is True
    assert boundary["source_binding_proves_live_owner_runtime"] is False
    assert boundary["source_binding_proves_universal_provider_enforcement"] is False

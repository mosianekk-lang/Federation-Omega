import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_output_mirror_v2_developer1000_court():
    proc = subprocess.run(
        ["node", str(ROOT / "benchmarks" / "output_mirror_v2_developer1000_court.mjs")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )
    report = json.loads(proc.stdout)
    assert report["cases"] == 1000
    assert report["v1_1"]["fp"] == 500
    assert report["v2"]["accuracy"] == 1
    assert report["v2"]["fp"] == 0
    assert all(v == 1 for v in report["v2"]["by_dimension"].values())


def test_bootstrap_inheritance_v2_source_contract():
    contract = json.loads((ROOT / "config" / "fuse-bootstrap-inheritance-v2.json").read_text(encoding="utf-8"))
    assert contract["schema"] == "FUSE_BOOTSTRAP_INHERITANCE_V2"
    assert contract["boot_kernel"] == "5.8.0"
    assert contract["output_mirror_min_version"] == "2.0.0"
    assert contract["release_policy"] == "ZERO_FAIL_ACROSS_ALL_REQUIRED_DIMENSIONS"
    assert contract["required_before_route_compilation"] is True
    assert contract["required_before_terminal_delivery"] is True
    assert contract["fail_closed"] is True
    assert len(contract["required_dimensions"]) == 10
    assert contract["developer1000"]["count"] == 1000
    assert contract["benchmark_court"]["cases"] == 1000
    assert contract["live_proof"]["bootstrap_guard_ok"] is True
    assert "START:FUSE_ONE" in contract["hydrate_on"]
    assert contract["required_order"].index("OUTPUT_MIRROR_V2") < contract["required_order"].index("ROUTE_COMPILE")
    assert contract["required_order"].index("OUTPUT_MIRROR_V2_RELEASE") < contract["required_order"].index("TERMINAL_DELIVERY")

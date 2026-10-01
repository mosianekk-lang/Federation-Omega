import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]


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


def test_output_mirror_v3_power_diary_court():
    report = _run_node("benchmarks/output_mirror_v3_power_diary_court.mjs")
    assert report["static_coverage_40_of_40"] is True
    assert report["chapter_count"] == 40
    assert report["family_count"] == 17
    assert report["positive_passes"] == 17
    assert report["negative_holds"] == 17
    assert report["all_behavioral_pass"] is True


def test_output_mirror_v3_preserves_developer1000_regression():
    report = _run_node("benchmarks/output_mirror_v3_developer1000_regression.mjs")
    assert report["cases"] == 1000
    assert report["v1_1"]["fp"] == 500
    assert report["v3"]["accuracy"] == 1
    assert report["v3"]["fp"] == 0


def test_power_diary_source_identity_and_bootstrap_contract():
    diary = json.loads((ROOT / "config" / "chatgpt-power-diary-v1.json").read_text(encoding="utf-8"))
    mirror = json.loads((ROOT / "config" / "fuse-output-mirror-v3.json").read_text(encoding="utf-8"))
    bootstrap = json.loads((ROOT / "config" / "fuse-bootstrap-inheritance-v3.json").read_text(encoding="utf-8"))
    expected = "3d95834ff0070e06c8de385b9240c65490d9b71ceb63fa5e3364f407261c0495"
    assert diary["owner_source"]["sha256"] == expected
    assert diary["owner_source"]["chapter_count"] == 40
    assert diary["owner_source_coverage"] == "40_OF_40"
    assert mirror["version"] == "3.0.0"
    assert mirror["power_diary"]["source_sha256"] == expected
    assert mirror["power_diary"]["family_count"] == 17
    assert bootstrap["boot_kernel"] == "5.10.1"
    assert bootstrap["output_mirror_min_version"] == "3.0.0"
    assert bootstrap["power_diary"]["source_sha256"] == expected
    assert bootstrap["power_diary"]["chapter_count"] == 40
    assert bootstrap["fail_closed"] is True

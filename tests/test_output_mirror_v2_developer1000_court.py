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

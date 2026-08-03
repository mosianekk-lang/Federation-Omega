from pathlib import Path
import json
import subprocess
import sys


def test_maintenance_runner_healthy(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_maintenance.py"
    result = subprocess.run(
        [sys.executable, str(script), "--workspace", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    receipt = json.loads((tmp_path / "maintenance_receipt.json").read_text(encoding="utf-8"))
    assert receipt["state"] == "HEALTHY"
    assert receipt["drift"]["drift"] is False
    assert receipt["retirement"]["retire"] is False
    assert (tmp_path / "heartbeat.jsonl").exists()
    assert (tmp_path / "learning_ledger.jsonl").exists()

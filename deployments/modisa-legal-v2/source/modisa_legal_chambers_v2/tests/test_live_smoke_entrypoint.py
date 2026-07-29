from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_documented_live_smoke_entrypoint_reaches_runtime_gate() -> None:
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "live_smoke.py"),
            "--matter",
            "MAT-SMOKE-ENTRYPOINT",
            "--mission",
            "Report runtime capability only.",
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode in {0, 2, 3}
    payload = json.loads(proc.stdout)
    if proc.returncode == 3:
        assert payload["status"] == "blocked"
        assert payload["model_execution_started"] is False
        assert "not installed" in payload["blocker"] or "OPENAI_API_KEY" in payload["blocker"]

#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    cases_path = root / "evals" / "cases.jsonl"
    cases = [json.loads(line) for line in cases_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    process = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    suite_passed = process.returncode == 0
    combined_output = (process.stdout + process.stderr)[-8000:]
    results = [
        {
            **case,
            "passed": suite_passed,
            "verification": "Covered by the single isolated full-suite run; pytest node retained for traceability.",
        }
        for case in cases
    ]
    passed = len(results) if suite_passed else 0
    report = {
        "suite": "MODISA Sovereign Legal Intelligence OS v2 local regression",
        "generated_at": datetime.now(UTC).isoformat(),
        "passed": passed,
        "total": len(results),
        "all_passed": suite_passed,
        "pytest_returncode": process.returncode,
        "pytest_output": combined_output,
        "results": results,
    }
    output = root / "evals" / "results" / "latest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"{passed}/{len(results)} evaluation cases passed")
    print(combined_output.strip())
    print(output)
    return 0 if suite_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    for path in (
        root / "evidenceops/fevx_adapter_v1/contracts/input-v1.schema.json",
        root / "evidenceops/fevx_adapter_v1/contracts/output-v1.schema.json",
    ):
        Draft202012Validator.check_schema(json.loads(path.read_text()))
    yaml.safe_load((root / "evidenceops/fevx_adapter_v1/POLICY.yaml").read_text())
    registration = json.loads(
        (root / "evidenceops/fevx_adapter_v1/registration.json").read_text()
    )
    assert registration["source_write_authority"] is False
    assert registration["verified_fact_write_authority"] is False
    assert registration["level_6_autonomy_granted"] is False
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

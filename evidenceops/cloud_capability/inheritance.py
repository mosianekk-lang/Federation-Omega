"""Audit mandatory cloud-capability inheritance across EvidenceOps artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CONTRACT_REF = "evidenceops/cloud_capability/contract.json"


def audit_inheritance(repository_root: str | Path) -> dict[str, Any]:
    root = Path(repository_root)
    contracts = sorted((root / "evidenceops").glob("**/BUILD_CONTRACT.json"))
    manifests = sorted((root / "evidenceops").glob("**/*manifest*.json"))
    checked: list[str] = []
    missing: list[str] = []
    for path in contracts:
        data = json.loads(path.read_text(encoding="utf-8"))
        checked.append(str(path.relative_to(root)))
        binding = data.get("cloud_capability_inheritance") or {}
        if binding.get("required") is not True or binding.get("contract_ref") != CONTRACT_REF:
            missing.append(str(path.relative_to(root)))
    manifest_bindings = []
    for path in manifests:
        data = json.loads(path.read_text(encoding="utf-8"))
        resources = data.get("required_resources")
        if isinstance(resources, list):
            manifest_bindings.append(str(path.relative_to(root)))
            if CONTRACT_REF not in resources:
                missing.append(str(path.relative_to(root)))
    return {
        "schema": "EVIDENCEOPS-CLOUD-INHERITANCE-AUDIT-1",
        "contract_ref": CONTRACT_REF,
        "build_contracts_checked": checked,
        "runtime_manifests_checked": manifest_bindings,
        "missing_bindings": sorted(set(missing)),
        "all_bound": not missing,
        "new_elements_inherit_by_default": True,
        "explicit_opt_out_allowed": False,
        "remediation_required": bool(missing),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--output")
    parser.add_argument("--require-all-bound", action="store_true")
    args = parser.parse_args(argv)
    result = audit_inheritance(args.repository_root)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["all_bound"] or not args.require_all_bound else 4


if __name__ == "__main__":
    raise SystemExit(main())

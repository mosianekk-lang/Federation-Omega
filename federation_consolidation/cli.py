from __future__ import annotations
import argparse
import json
from pathlib import Path
from .engine import FederationConsolidator

def main() -> int:
    parser = argparse.ArgumentParser(description="Federation Omega 24-hour consolidation kernel")
    parser.add_argument("command", choices=["validate", "canary", "release-gate", "succession"])
    parser.add_argument("--data-dir", default=str(Path(__file__).with_name("data")))
    parser.add_argument("--workspace", default="runtime/federation-consolidation")
    parser.add_argument("--source-commit", default="UNSET")
    args = parser.parse_args()

    engine = FederationConsolidator(args.data_dir)
    if args.command == "validate":
        payload = {
            "registry": engine.validate_registry().__dict__,
            "routes": engine.validate_routes().__dict__,
            "triage": engine.validate_pr_triage().__dict__,
            "lineage": engine.validate_lineage().__dict__,
            "drive": engine.validate_drive_publication().__dict__,
        }
        payload["valid"] = all(item["valid"] for item in payload.values() if isinstance(item, dict) and "valid" in item)
    elif args.command == "canary":
        payload = engine.e2e_canary(args.workspace)
    elif args.command == "release-gate":
        payload = engine.alpha_omega_release_gate()
    else:
        target = Path(args.workspace) / "succession_bundle.json"
        payload = engine.succession_bundle(args.source_commit, target)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("valid", payload.get("passed", payload.get("eligible", True))) else 1

if __name__ == "__main__":
    raise SystemExit(main())

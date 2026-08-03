from __future__ import annotations

import argparse
import json
from pathlib import Path

from programme_integrity import verify_from_paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the commercial programme register against the canonical C15 proof artifact.")
    parser.add_argument("--programme", default="alpha_omega_commercial/programme.json")
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    result = verify_from_paths(args.programme, args.artifact_root)
    output = Path(args.output) if args.output else Path(args.artifact_root) / "programme-register-integrity.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["status"] != "PROGRAMME_REGISTER_INTEGRITY_VERIFIED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
from pathlib import Path

from governed_authority_release import prove


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--receipt",
        type=Path,
        default=Path("alpha_omega_commercial/governed_authority_release_receipt.json"),
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=Path("alpha_omega_commercial/governed_authority_checkpoint.json"),
    )
    parser.add_argument(
        "--programme",
        type=Path,
        default=Path("alpha_omega_commercial/programme.json"),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = prove(args.receipt, args.checkpoint, args.programme, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from live_authority import CanonicalLiveAuthority
from runtime import utc_now


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    out = Path(args.output)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    manifest_path = Path(__file__).with_name("canonical_live_authority_manifest.json")
    authority = CanonicalLiveAuthority.from_file(manifest_path)
    receipt = authority.validate()
    receipt["generated_at"] = utc_now()

    (out / "canonical-live-authority-manifest.json").write_text(
        manifest_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (out / "canonical-live-authority-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    if receipt["status"] != "CANONICAL_LIVE_AUTHORITY_MANIFEST_VERIFIED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

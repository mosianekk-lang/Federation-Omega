#!/usr/bin/env python3
from __future__ import annotations

import hashlib
from pathlib import Path

EXCLUDED = {".git", ".pytest_cache", "__pycache__", "state", "backups", "build", "modisa_sovereign_legal_os.egg-info"}
EXCLUDED_FILES = {"MANIFEST.sha256", ".env", ".env.local"}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    rows: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in EXCLUDED for part in rel.parts) or path.name in EXCLUDED_FILES:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append(f"{digest}  {rel.as_posix()}")
    (root / "MANIFEST.sha256").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} file hashes to {root / 'MANIFEST.sha256'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

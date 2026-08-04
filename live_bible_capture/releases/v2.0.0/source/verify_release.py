from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
required = [
    "pyproject.toml",
    "README.md",
    "release_descriptor.json",
    "live_bible_fabric/__init__.py",
    "live_bible_fabric/fabric.py",
    "tests/test_fabric.py",
    "browser_extension/manifest.json",
    "browser_extension/background.js",
    "browser_extension/content.js",
    "browser_extension/popup.html",
    "browser_extension/popup.js",
    "docs/ARCHITECTURE.md",
]
missing = [path for path in required if not (ROOT / path).is_file()]
if missing:
    raise SystemExit(f"missing required files: {missing}")
descriptor = json.loads((ROOT / "release_descriptor.json").read_text())
assert descriptor["version"] == "2.0.0"
assert descriptor["authority_ceiling"] == "A1_REVERSIBLE_INTERNAL"
assert descriptor["external_effects"] == 0
assert "TURN_CONNECTOR" in descriptor["active_now"]
assert "CONTINUOUS_CHAT_SOURCE_FEED" in descriptor["provider_gated"]
print("LIVE_BIBLE_FABRIC_RELEASE_OK")

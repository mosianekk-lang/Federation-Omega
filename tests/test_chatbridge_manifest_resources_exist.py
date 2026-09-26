from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
COMPANION = ROOT / "chatbridge-companion"

def test_manifest_referenced_static_resources_exist():
    manifest = json.loads((COMPANION / "manifest.json").read_text(encoding="utf-8"))
    for entry in manifest.get("content_scripts", []):
        for rel in entry.get("js", []) + entry.get("css", []):
            assert (COMPANION / rel).is_file(), rel
    worker = manifest.get("background", {}).get("service_worker")
    if worker:
        assert (COMPANION / worker).is_file(), worker

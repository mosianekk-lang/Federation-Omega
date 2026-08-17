from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]
COMPANION = ROOT / "chatbridge-companion"


class BrowserCompanionSourceContractTests(unittest.TestCase):
    def test_manifest_is_narrow_and_ffcl_ordered(self) -> None:
        manifest = json.loads((COMPANION / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["manifest_version"], 3)
        self.assertEqual(manifest["version"], "0.3.0")
        self.assertEqual(manifest["permissions"], ["storage", "tabs"])
        self.assertEqual(
            manifest["content_scripts"][0]["js"],
            ["src/bridge-core.js", "src/content-script.js"],
        )
        for forbidden in (
            "nativeMessaging",
            "debugger",
            "management",
            "webRequestBlocking",
        ):
            self.assertNotIn(forbidden, manifest["permissions"])

    def test_local_write_precedes_optional_provider_upload(self) -> None:
        background = (COMPANION / "src" / "background.js").read_text(
            encoding="utf-8"
        )
        self.assertLess(
            background.index("await putCapture(captureRecord)"),
            background.index("await uploadCapture"),
        )
        self.assertIn("PROVIDER_UPLOAD_FAILED_LOCAL_DURABLE", background)
        self.assertIn("chrome.storage.session.get(\"chatbridgeConnectorToken\")", background)
        self.assertNotIn(
            "chrome.storage.local.set({chatbridgeConnectorToken", background
        )

    def test_terminal_capture_precedes_successor_tab(self) -> None:
        content = (COMPANION / "src" / "content-script.js").read_text(
            encoding="utf-8"
        )
        self.assertLess(
            content.index('capture("LIMIT_WARNING_CLICK"'),
            content.index('type: "CHATBRIDGE_OPEN"'),
        )
        self.assertIn("terminalObserved: true", content)

    def test_node_contract_suite(self) -> None:
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is not installed in this runner")
        subprocess.run(
            [
                node,
                "--test",
                "tests/bridge-core.test.js",
                "tests/ffcl-adapter-static.test.js",
                "tests/readiness-contract.test.js",
            ],
            cwd=COMPANION,
            check=True,
            capture_output=True,
            text=True,
            timeout=90,
        )


if __name__ == "__main__":
    unittest.main()

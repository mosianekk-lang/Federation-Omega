from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]
COMPANION = ROOT / "chatbridge-companion"


class BrowserCompanionSourceContractTests(unittest.TestCase):
    def test_manifest_matches_admitted_v030_and_stays_browser_bounded(self) -> None:
        manifest = json.loads((COMPANION / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["manifest_version"], 3)
        self.assertEqual(manifest["version"], "0.3.0")
        self.assertEqual(
            manifest["permissions"],
            ["storage", "unlimitedStorage", "downloads"],
        )
        self.assertEqual(manifest["host_permissions"], ["https://chatgpt.com/*"])
        self.assertEqual(
            manifest["content_scripts"][0]["js"],
            ["src/bridge-core.js", "src/content-script.js"],
        )
        for forbidden in (
            "nativeMessaging",
            "debugger",
            "management",
            "webRequest",
            "webRequestBlocking",
            "scripting",
        ):
            self.assertNotIn(forbidden, manifest["permissions"])

    def test_capture_is_written_locally_before_return_and_has_no_network_client(self) -> None:
        background = (COMPANION / "src" / "background.js").read_text(
            encoding="utf-8"
        )
        capture_start = background.index("async function capturePacket")
        capture_end = background.index("async function handleMessage")
        capture_body = background[capture_start:capture_end]
        self.assertLess(
            capture_body.index("await saveLedger(ledger)"),
            capture_body.index("return ledger"),
        )
        self.assertIn("chrome.storage.local.set", background)
        self.assertIn("chrome.downloads.download", background)
        self.assertNotIn("fetch(", background)
        self.assertNotIn("XMLHttpRequest", background)
        self.assertNotIn("WebSocket", background)

    def test_terminal_capture_precedes_successor_open(self) -> None:
        content = (COMPANION / "src" / "content-script.js").read_text(
            encoding="utf-8"
        )
        start = content.index("async function startSuccessor")
        end = content.index("function decorateLimitBanner")
        successor_body = content[start:end]
        self.assertLess(
            successor_body.index('await checkpoint("SUCCESSOR_REQUEST")'),
            successor_body.index('type: "CHATBRIDGE_OPEN"'),
        )
        self.assertIn('checkpoint("TERMINAL_WARNING_DETECTED")', content)
        self.assertIn('checkpoint("PERIODIC_WRITE_AHEAD")', content)
        self.assertIn('checkpoint("VISIBILITY_HIDDEN")', content)

    def test_node_contract_suite_for_current_companion(self) -> None:
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is not installed in this runner")
        subprocess.run(
            [
                node,
                "--test",
                "tests/bridge-core.test.js",
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

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
COMPANION = ROOT / "chatbridge-companion"
EDGE_AGENT = ROOT / "bef-edge-agent"
NATIVE_HOST = EDGE_AGENT / "native-host" / "bef_native_host.py"
CHATBRIDGE_EXTENSION_ID = "kacbginamagliaddmlkffhcadpamomjb"
EDGE_AGENT_EXTENSION_ID = "apokbhjjgiaceigelkedcelcecfmgnia"


def _extension_id(manifest_key: str) -> str:
    digest = hashlib.sha256(base64.b64decode(manifest_key)).digest()[:16]
    alphabet = "abcdefghijklmnop"
    return "".join(alphabet[b >> 4] + alphabet[b & 15] for b in digest)


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
        self.assertEqual(_extension_id(manifest["key"]), CHATBRIDGE_EXTENSION_ID)
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
            capture_body.index("await edgeEgress.flushLedger"),
        )
        self.assertLess(
            capture_body.index("await saveLedger(ledger)"),
            capture_body.index("return ledger"),
        )
        self.assertIn("chrome.storage.local.set", background)
        self.assertIn("chrome.downloads.download", background)
        self.assertNotIn("fetch(", background)
        self.assertNotIn("XMLHttpRequest", background)
        self.assertNotIn("WebSocket", background)
        self.assertNotIn("sendNativeMessage", background)

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

    def test_edge_agent_has_only_courier_authority_and_fixed_identity(self) -> None:
        manifest = json.loads((EDGE_AGENT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["manifest_version"], 3)
        self.assertEqual(manifest["permissions"], ["storage", "nativeMessaging"])
        self.assertNotIn("host_permissions", manifest)
        self.assertEqual(_extension_id(manifest["key"]), EDGE_AGENT_EXTENSION_ID)
        self.assertEqual(
            manifest["externally_connectable"]["ids"],
            [CHATBRIDGE_EXTENSION_ID],
        )
        background = (EDGE_AGENT / "src" / "background.js").read_text(encoding="utf-8")
        self.assertIn("sender.id !== protocol.CHATBRIDGE_EXTENSION_ID", background)
        self.assertIn("chrome.runtime.sendNativeMessage", background)
        for forbidden in ("fetch(", "XMLHttpRequest", "WebSocket"):
            self.assertNotIn(forbidden, background)

    def test_native_host_is_edge_agent_only_and_encrypts_before_spooling(self) -> None:
        template = json.loads(
            (EDGE_AGENT / "native-host" / "com.sovara.bef_edge.json.template").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(template["name"], "com.sovara.bef_edge")
        self.assertEqual(
            template["allowed_origins"],
            [f"chrome-extension://{EDGE_AGENT_EXTENSION_ID}/"],
        )
        source = NATIVE_HOST.read_text(encoding="utf-8")
        self.assertIn("WindowsDpapiProtector", source)
        self.assertIn("storedEncrypted", source)
        for forbidden in ("requests.", "urllib.request", "http.client", "socket."):
            self.assertNotIn(forbidden, source)
        result = subprocess.run(
            [sys.executable, str(NATIVE_HOST), "--self-test"],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertIn("BEF_NATIVE_HOST_SELF_TEST_PASS", result.stdout)

    def test_node_contract_suite_for_current_companion_and_edge_agent(self) -> None:
        node = shutil.which("node")
        npm = shutil.which("npm")
        if not node or not npm:
            self.skipTest("Node/npm is not installed in this runner")
        subprocess.run(
            [npm, "run", "check"],
            cwd=COMPANION,
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        subprocess.run(
            [npm, "run", "check"],
            cwd=EDGE_AGENT,
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )


if __name__ == "__main__":
    unittest.main()

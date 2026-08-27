from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHAT = ROOT / "chatbridge-companion"
BEF = ROOT / "bef-edge-agent"
RUNTIME = BEF / "runtime"
NATIVE = BEF / "native-host"


def extension_id(manifest_path: Path) -> str:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(base64.b64decode(manifest["key"])).digest()[:16]
    alphabet = "abcdefghijklmnop"
    return "".join(alphabet[nibble] for byte in digest for nibble in (byte >> 4, byte & 0x0F))


class BEFWindowsRuntimeBootstrapTests(unittest.TestCase):
    def test_manifest_keys_bind_exact_extension_ids(self):
        self.assertEqual(extension_id(CHAT / "manifest.json"), "kacbginamagliaddmlkffhcadpamomjb")
        self.assertEqual(extension_id(BEF / "manifest.json"), "apokbhjjgiaceigelkedcelcecfmgnia")

    def test_bef_accepts_only_exact_chatbridge_identity(self):
        manifest = json.loads((BEF / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["externally_connectable"]["ids"], ["kacbginamagliaddmlkffhcadpamomjb"])
        self.assertEqual(set(manifest["permissions"]), {"storage", "nativeMessaging"})
        self.assertNotIn("host_permissions", manifest)

    def test_chatbridge_remains_browser_bounded(self):
        manifest = json.loads((CHAT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(set(manifest["permissions"]), {"storage", "unlimitedStorage", "downloads"})
        self.assertEqual(manifest["host_permissions"], ["https://chatgpt.com/*"])
        self.assertNotIn("nativeMessaging", manifest["permissions"])

    def test_native_host_registration_is_current_user_and_exact_origin(self):
        source = (NATIVE / "install_native_host.ps1").read_text(encoding="utf-8")
        self.assertIn("HKCU:\\Software\\Microsoft\\Edge\\NativeMessagingHosts", source)
        self.assertNotIn("HKLM:", source)
        self.assertIn("chrome-extension://$ExpectedEdgeExtensionId/", source)
        self.assertIn("apokbhjjgiaceigelkedcelcecfmgnia", source)

    def test_bootstrap_has_no_dependency_download_or_general_network_route(self):
        source = (RUNTIME / "bootstrap_windows_canary.ps1").read_text(encoding="utf-8")
        for forbidden in ("Invoke-WebRequest", "Start-BitsTransfer", "curl.exe", "irm ", "iwr "):
            self.assertNotIn(forbidden, source)
        self.assertIn("build_native_host.ps1", source)
        self.assertIn("install_native_host.ps1", source)
        self.assertIn("--load-extension=", source)
        self.assertIn("--user-data-dir=", source)

    def test_bootstrap_derives_and_checks_both_extension_ids(self):
        source = (RUNTIME / "bootstrap_windows_canary.ps1").read_text(encoding="utf-8")
        self.assertIn("Get-ChromiumExtensionId", source)
        self.assertIn("kacbginamagliaddmlkffhcadpamomjb", source)
        self.assertIn("apokbhjjgiaceigelkedcelcecfmgnia", source)
        self.assertIn("BEF_EXTERNALLY_CONNECTABLE_BINDING_DRIFT", source)

    def test_runtime_readback_requires_progressive_real_evidence(self):
        source = (RUNTIME / "verify_windows_canary.ps1").read_text(encoding="utf-8")
        ordering = [
            "RUNTIME_NOT_BOUND",
            "NATIVE_HOST_REGISTERED_VERIFIED",
            "BROWSER_PROFILE_BINDING_VERIFIED",
            "LIVE_ENCRYPTED_SPOOL_RECEIPT_OBSERVED",
        ]
        positions = [source.index(item) for item in ordering]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("provider-native hidden events", source.lower())

    def test_spool_cli_exposes_redacted_receipts_and_bounded_dpf_evidence(self):
        source = (NATIVE / "bef_spool.py").read_text(encoding="utf-8")
        self.assertIn("_public_receipt_projection", source)
        self.assertIn("--observable-scope-evidence", source)
        self.assertIn('"provider_native_complete": False', source)
        self.assertIn("FULL_OBSERVABLE_RENDERED_CHAT_EVIDENCE_ONLY", source)
        self.assertIn("BEF_SPOOL_RECEIPTS_READBACK", source)
        self.assertIn("BEF_OBSERVABLE_SCOPE_EVIDENCE", source)

    def test_rollback_is_scoped_and_preserves_spool_by_default(self):
        source = (RUNTIME / "rollback_windows_canary.ps1").read_text(encoding="utf-8")
        self.assertIn("CommandLine -match", source)
        self.assertIn("EdgeCanaryProfile", source)
        self.assertIn("EncryptedSpoolPreserved", source)
        self.assertNotIn("Remove-Item -LiteralPath $spoolRoot", source)

    def test_runtime_scripts_preserve_truth_boundaries(self):
        for name in ("bootstrap_windows_canary.ps1", "verify_windows_canary.ps1", "rollback_windows_canary.ps1"):
            source = (RUNTIME / name).read_text(encoding="utf-8")
            self.assertIn("truthboundary", source.lower())


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile" / "fuse-mobile"
WORKFLOW = ROOT / ".github" / "workflows" / "fuse-mobile-android-build.yml"
POLICY = ROOT / "governance" / "github_airlock_policy.json"
SCANNER = MOBILE / "lab" / "scan_apk.py"


class FuseMobileAndroidBuildWorkflowV1Tests(unittest.TestCase):
    def test_sdk55_manifest_matches_proven_alignment(self) -> None:
        package = json.loads((MOBILE / "package.json").read_text())
        deps = package["dependencies"]
        self.assertEqual(deps["expo"], "~55.0.0")
        self.assertEqual(deps["expo-constants"], "~55.0.17")
        self.assertEqual(deps["expo-font"], "~55.0.8")
        self.assertEqual(deps["expo-linking"], "~55.0.17")
        self.assertEqual(deps["expo-router"], "~55.0.18")
        self.assertEqual(deps["expo-secure-store"], "~55.0.18")
        self.assertEqual(deps["react"], "19.2.0")
        self.assertEqual(deps["react-dom"], "19.2.0")
        self.assertEqual(deps["react-native"], "0.83.10")
        self.assertEqual(deps["react-native-safe-area-context"], "~5.6.2")
        self.assertEqual(deps["react-native-screens"], "~4.23.0")
        self.assertEqual(deps["react-native-web"], "~0.21.0")

    def test_app_config_drops_invalid_new_arch_override(self) -> None:
        app = json.loads((MOBILE / "app.json").read_text())
        self.assertNotIn("newArchEnabled", app["expo"])
        self.assertEqual(app["expo"]["android"]["package"], "com.federationomega.fusemobile")

    def _workflow_text_or_skip_export(self) -> str:
        if not WORKFLOW.is_file():
            self.skipTest("GitHub workflow controls are outside the reduced Phoenix exported-core surface")
        return WORKFLOW.read_text()

    def test_hosted_build_court_is_owner_only_and_non_effectful(self) -> None:
        text = self._workflow_text_or_skip_export()
        self.assertIn("FUSE_MOBILE_ANDROID_BUILD_V1", text)
        self.assertIn("author_association == 'OWNER'", text)
        self.assertIn("contents: read", text)
        self.assertIn("issues: read", text)
        self.assertNotIn("id-token:", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("git push", text)
        self.assertIn("persist-credentials: false", text)

    def test_build_court_generates_lock_and_real_apk_receipt(self) -> None:
        text = self._workflow_text_or_skip_export()
        for required in (
            "npm install --package-lock-only --ignore-scripts",
            "npm ci",
            "npx expo install --check",
            "npx expo-doctor",
            "npm run export:android",
            "npm run prebuild:android",
            "./gradlew assembleDebug --no-daemon",
            "app-debug.apk",
            "sha256sum",
            "ANDROID_DEBUG_APK_GENERATED_VERIFIED",
            "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
        ):
            self.assertIn(required, text)

    def test_apk_credential_scan_is_archive_aware_and_fail_closed(self) -> None:
        workflow = self._workflow_text_or_skip_export()
        scanner = SCANNER.read_text(encoding="utf-8")
        self.assertIn("python lab/scan_apk.py", workflow)
        self.assertIn("--apk android/app/build/outputs/apk/debug/app-debug.apk", workflow)
        self.assertIn("--output fuse-mobile-apk-security-scan.json", workflow)
        self.assertIn("APK_CREDENTIAL_SCAN_CLEAN", workflow)
        self.assertIn("fuse-mobile-apk-security-scan.json", workflow)
        self.assertIn("apk_credential_scan_receipt_sha256", workflow)
        self.assertNotIn("strings \"$APK\" | grep -E", workflow)

        self.assertIn("with zipfile.ZipFile(apk) as archive", scanner)
        self.assertIn('"pem_private_key"', scanner)
        self.assertIn('"openrouter_key"', scanner)
        self.assertIn('"google_api_key"', scanner)
        self.assertIn('"APK_CREDENTIAL_SCAN_FAILED"', scanner)
        self.assertIn("return 1 if matches else 0", scanner)
        self.assertIn('"credential_values_recorded": False', scanner)

    def test_apk_scanner_behavior_fails_closed_on_archive_member_secret(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            apk = Path(tmp) / "fixture.apk"
            receipt = Path(tmp) / "scan.json"
            synthetic_marker = "sk-" + "or-v1-" + ("A" * 30)
            with zipfile.ZipFile(apk, "w") as archive:
                archive.writestr("assets/clean.txt", b"ordinary fixture")
                archive.writestr("assets/leak.txt", synthetic_marker.encode("ascii"))
            proc = subprocess.run(
                [sys.executable, str(SCANNER), "--apk", str(apk), "--output", str(receipt)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            payload = json.loads(receipt.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "APK_CREDENTIAL_SCAN_FAILED")
            self.assertGreaterEqual(payload["archive_members_scanned"], 2)
            self.assertTrue(any(item["pattern"] == "openrouter_key" for item in payload["matches"]))
            self.assertFalse(payload["credential_values_recorded"])
            self.assertNotIn(synthetic_marker, receipt.read_text(encoding="utf-8"))

    def test_airlock_explicitly_quarantines_build_workflow(self) -> None:
        if not POLICY.is_file():
            self.skipTest("repository workflow governance is outside the reduced Phoenix exported-core surface")
        policy = json.loads(POLICY.read_text())
        path = ".github/workflows/fuse-mobile-android-build.yml"
        self.assertIn(path, policy["active_workflow_allowlist"])
        self.assertEqual(policy["allowed_events"][path], ["issues"])
        self.assertIn(path, policy["execution_quarantine"]["keep_active"])
        self.assertNotIn(path, policy["oidc_workflow_allowlist"])


if __name__ == "__main__":
    unittest.main()

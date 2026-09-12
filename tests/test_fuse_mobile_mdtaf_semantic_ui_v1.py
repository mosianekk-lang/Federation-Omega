from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/fuse-mobile-android-build.yml"
SMOKE = ROOT / "mobile/fuse-mobile/lab/run_android_smoke.sh"
CERTIFY = ROOT / "mobile/fuse-mobile/lab/certify.py"


class FuseMobileMdtafSemanticUiV1Tests(unittest.TestCase):
    """Failure-first contract for the v0.3 detached-APK semantic false-green.

    Process/activity/network liveness is not enough. The MDTAF artifact must be
    self-contained and the rendered FUSE UI must be observed before release gates
    may turn green.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.smoke = SMOKE.read_text(encoding="utf-8")
        cls.certify = CERTIFY.read_text(encoding="utf-8")

    def test_detached_mdtaf_build_is_standalone_not_metro_dependent(self) -> None:
        self.assertIn("assembleRelease", self.workflow)
        self.assertIn("app-release.apk", self.workflow)
        self.assertNotIn("assembleDebug --no-daemon", self.workflow)

    def test_build_preflights_embedded_android_js_bundle(self) -> None:
        self.assertIn("assets/index.android.bundle", self.workflow)
        self.assertIn("EMBEDDED_JS_BUNDLE_PRESENT", self.workflow)

    def test_smoke_vetoes_react_script_boot_failures(self) -> None:
        self.assertIn("Unable to load script", self.smoke)
        self.assertIn("REACT_BOOT_ERROR", self.smoke)

    def test_smoke_requires_semantic_fuse_ui_at_every_launch_phase(self) -> None:
        for marker in (
            "first_launch_ui_state",
            "relaunch_ui_state",
            "offline_launch_ui_state",
            "recovery_launch_ui_state",
        ):
            self.assertIn(marker, self.smoke)
        self.assertIn("FUSE", self.smoke)
        self.assertIn("ui-", self.smoke)

    def test_certificate_has_explicit_semantic_ui_and_bundle_gates(self) -> None:
        for marker in (
            '"embedded_js_bundle"',
            '"semantic_ui_first_launch"',
            '"semantic_ui_relaunch"',
            '"semantic_ui_offline_launch"',
            '"semantic_ui_recovery_launch"',
            '"no_react_boot_error"',
        ):
            self.assertIn(marker, self.certify)


if __name__ == "__main__":
    unittest.main()

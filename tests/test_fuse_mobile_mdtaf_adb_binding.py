from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "mobile" / "fuse-mobile" / "lab"
HELPER = LAB / "resolve_sdk_adb.sh"
SMOKE = LAB / "run_android_smoke.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "fuse-mobile-android-build.yml"
BARE_ADB = re.compile(r"(?m)^[ \t]*adb(?:[ \t]|$)")


class FuseMobileMdtafAdbBindingTests(unittest.TestCase):
    def _sdk(self, root: Path) -> tuple[Path, Path]:
        sdk = root / "sdk"
        adb = sdk / "platform-tools" / "adb"
        adb.parent.mkdir(parents=True)
        adb.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
        adb.chmod(0o755)
        return sdk, adb

    def _run_resolver(self, *, sdk: Path | None, adb_bin: str | None = None) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.pop("ANDROID_SDK_ROOT", None)
        env.pop("ANDROID_HOME", None)
        env.pop("ADB_BIN", None)
        if sdk is not None:
            env["ANDROID_SDK_ROOT"] = str(sdk)
        if adb_bin is not None:
            env["ADB_BIN"] = adb_bin
        return subprocess.run(
            ["bash", str(HELPER)],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_exact_sdk_platform_tools_adb_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sdk, adb = self._sdk(Path(tmp))
            proc = self._run_resolver(sdk=sdk, adb_bin=str(adb))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout.strip(), str(adb.resolve()))

    def test_missing_sdk_root_fails_closed(self) -> None:
        proc = self._run_resolver(sdk=None)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("must identify the Android SDK", proc.stderr)

    def test_missing_exact_sdk_adb_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sdk = Path(tmp) / "sdk"
            sdk.mkdir()
            proc = self._run_resolver(sdk=sdk)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("missing or not executable", proc.stderr)

    def test_bare_ambient_adb_bin_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sdk, _ = self._sdk(Path(tmp))
            proc = self._run_resolver(sdk=sdk, adb_bin="adb")
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("ambient/bare adb is forbidden", proc.stderr)

    def test_mismatched_absolute_adb_bin_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sdk, _ = self._sdk(root)
            other = root / "other-adb"
            other.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
            other.chmod(0o755)
            proc = self._run_resolver(sdk=sdk, adb_bin=str(other))
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("does not match SDK_ROOT/platform-tools/adb", proc.stderr)

    def test_workflow_uses_exact_sdk_adb_not_ambient_command(self) -> None:
        if not WORKFLOW.exists():
            # Phoenix reduced exported-core intentionally omits repository workflow
            # controls. Preserve semantic assurance before skipping only the
            # unavailable workflow-text assertion: the exact-ADB resolver and
            # smoke harness must still be exported and their behavioral tests
            # in this class remain mandatory.
            self.assertTrue(HELPER.is_file(), "reduced export lost exact SDK adb resolver")
            self.assertTrue(SMOKE.is_file(), "reduced export lost Android smoke harness")
            helper = HELPER.read_text(encoding="utf-8")
            smoke = SMOKE.read_text(encoding="utf-8")
            self.assertIn('EXPECTED_ADB="$SDK_ROOT/platform-tools/adb"', helper)
            self.assertIn('ADB="$(bash "$SCRIPT_DIR/resolve_sdk_adb.sh")"', smoke)
            self.assertIsNone(BARE_ADB.search(smoke), "reduced-export smoke harness contains bare ambient adb")
            self.skipTest("workflow-free export excludes repository workflow controls")

        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('ADB="$SDK_ROOT/platform-tools/adb"', workflow)
        self.assertIn('ADB_BIN="$SDK_ROOT/platform-tools/adb"', workflow)
        self.assertIn('test -x "$ADB"', workflow)
        self.assertIn('ADB_BIN="$ADB" bash mobile/fuse-mobile/lab/resolve_sdk_adb.sh', workflow)
        self.assertIsNone(BARE_ADB.search(workflow), "workflow contains a bare ambient adb invocation")

    def test_smoke_harness_resolves_exact_sdk_adb_and_has_no_bare_invocation(self) -> None:
        smoke = SMOKE.read_text(encoding="utf-8")
        self.assertIn('ADB="$(bash "$SCRIPT_DIR/resolve_sdk_adb.sh")"', smoke)
        self.assertIn('test -x "$ADB"', smoke)
        self.assertIsNone(BARE_ADB.search(smoke), "smoke harness contains a bare ambient adb invocation")


if __name__ == "__main__":
    unittest.main()

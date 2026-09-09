from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "mobile" / "fuse-mobile" / "lab" / "resolve_android_sdk_tools.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "fuse-mobile-android-build.yml"


class FuseMobileMdtafSdkToolchainResolutionTests(unittest.TestCase):
    def _sdk(self, root: Path) -> Path:
        sdk = root / "sdk"
        (sdk / "cmdline-tools").mkdir(parents=True)
        return sdk

    def _install(self, sdk: Path, name: str, revision: str, *, sdkmanager: bool = True, avdmanager: bool = True) -> Path:
        tool = sdk / "cmdline-tools" / name
        (tool / "bin").mkdir(parents=True)
        (tool / "source.properties").write_text(f"Pkg.Revision = {revision}\n", encoding="utf-8")
        if sdkmanager:
            path = tool / "bin" / "sdkmanager"
            path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            path.chmod(0o755)
        if avdmanager:
            path = tool / "bin" / "avdmanager"
            path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            path.chmod(0o755)
        return tool

    def _run(self, sdk: Path | None, *, output_env: Path | None = None) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.pop("ANDROID_SDK_ROOT", None)
        env.pop("ANDROID_HOME", None)
        if sdk is not None:
            env["ANDROID_SDK_ROOT"] = str(sdk)
        cmd = ["bash", str(HELPER)]
        if output_env is not None:
            cmd += ["--output-env", str(output_env)]
        return subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True, check=False)

    @staticmethod
    def _parse(stdout: str) -> dict[str, str]:
        result: dict[str, str] = {}
        for line in stdout.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                result[key] = value
        return result

    def test_highest_concrete_revision_is_selected_without_latest_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sdk = self._sdk(Path(tmp))
            self._install(sdk, "12.0", "12.0")
            chosen = self._install(sdk, "19.0", "19.0")
            proc = self._run(sdk)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            values = self._parse(proc.stdout)
            self.assertEqual(values["CMDLINE_TOOLS_REVISION"], "19.0")
            self.assertEqual(Path(values["CMDLINE_TOOLS_ROOT"]), chosen.resolve())

    def test_physical_latest_directory_is_accepted_by_exact_revision_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sdk = self._sdk(Path(tmp))
            chosen = self._install(sdk, "latest", "12.0")
            proc = self._run(sdk)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            values = self._parse(proc.stdout)
            self.assertEqual(Path(values["CMDLINE_TOOLS_ROOT"]), chosen.resolve())
            self.assertEqual(values["CMDLINE_TOOLS_LAYOUT_NAME"], "latest")
            self.assertEqual(values["CMDLINE_TOOLS_REVISION"], "12.0")
            self.assertEqual(values["CMDLINE_TOOLS_IDENTITY_SOURCE"], "source.properties:Pkg.Revision")

    def test_latest_symlink_is_not_provenance_and_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sdk = self._sdk(Path(tmp))
            concrete = self._install(sdk, "18.0", "18.0")
            (sdk / "cmdline-tools" / "latest").symlink_to(concrete, target_is_directory=True)
            proc = self._run(sdk)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            values = self._parse(proc.stdout)
            self.assertEqual(Path(values["CMDLINE_TOOLS_ROOT"]), concrete.resolve())
            self.assertNotIn("/latest", values["CMDLINE_TOOLS_ROOT"])

    def test_missing_sdk_root_fails_closed(self) -> None:
        proc = self._run(None)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("must identify the Android SDK", proc.stderr)

    def test_missing_cmdline_tools_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sdk = Path(tmp) / "sdk"
            sdk.mkdir()
            proc = self._run(sdk)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("cmdline-tools directory is missing", proc.stderr)

    def test_tools_must_come_from_same_exact_installation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sdk = self._sdk(Path(tmp))
            self._install(sdk, "17.0-a", "17.0", avdmanager=False)
            self._install(sdk, "17.0-b", "17.0", sdkmanager=False)
            proc = self._run(sdk)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("no exact Android cmdline-tools installation", proc.stderr)

    def test_invalid_revision_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sdk = self._sdk(Path(tmp))
            self._install(sdk, "broken", "preview-current")
            valid = self._install(sdk, "16.0", "16.0")
            proc = self._run(sdk)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(Path(self._parse(proc.stdout)["CMDLINE_TOOLS_ROOT"]), valid.resolve())

    def test_revision_order_is_version_aware_not_lexicographic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sdk = self._sdk(Path(tmp))
            self._install(sdk, "9.0", "9.0")
            chosen = self._install(sdk, "10.0", "10.0")
            proc = self._run(sdk)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            values = self._parse(proc.stdout)
            self.assertEqual(values["CMDLINE_TOOLS_REVISION"], "10.0")
            self.assertEqual(Path(values["CMDLINE_TOOLS_ROOT"]), chosen.resolve())

    def test_env_receipt_contains_exact_resolved_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sdk = self._sdk(root)
            chosen = self._install(sdk, "20.0", "20.0")
            receipt = root / "resolved.env"
            proc = self._run(sdk, output_env=receipt)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            written = self._parse(receipt.read_text(encoding="utf-8"))
            self.assertEqual(written["CMDLINE_TOOLS_REVISION"], "20.0")
            self.assertEqual(written["CMDLINE_TOOLS_LAYOUT_NAME"], "20.0")
            self.assertEqual(written["CMDLINE_TOOLS_IDENTITY_SOURCE"], "source.properties:Pkg.Revision")
            self.assertEqual(Path(written["SDKMANAGER"]), (chosen / "bin" / "sdkmanager").resolve())
            self.assertEqual(Path(written["AVDMANAGER"]), (chosen / "bin" / "avdmanager").resolve())

    def test_workflow_binds_resolver_and_forbids_direct_latest_path(self) -> None:
        if not WORKFLOW.exists():
            self.skipTest("workflow-free export excludes repository workflow controls")
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("cmdline-tools/latest/bin/sdkmanager", workflow)
        self.assertNotIn("cmdline-tools/latest/bin/avdmanager", workflow)
        self.assertIn("resolve_android_sdk_tools.sh", workflow)
        self.assertIn("CMDLINE_TOOLS_REVISION", workflow)
        self.assertIn("SDKMANAGER", workflow)
        self.assertIn("AVDMANAGER", workflow)


if __name__ == "__main__":
    unittest.main()

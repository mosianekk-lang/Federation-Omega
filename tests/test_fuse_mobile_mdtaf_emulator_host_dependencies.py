from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "fuse-mobile-android-build.yml"
HELPER = ROOT / "mobile" / "fuse-mobile" / "lab" / "validate_emulator_host_dependencies.sh"


class FuseMobileMdtafEmulatorHostDependencyTests(unittest.TestCase):
    def _provision_block(self) -> str:
        if not WORKFLOW.exists():
            self.skipTest("workflow-free export excludes repository workflow controls")
        workflow = WORKFLOW.read_text(encoding="utf-8")
        return workflow.split(
            "- name: Provision clean Android virtual device in stable AVD namespace", 1
        )[1].split("- name: Boot AVD through bounded exact-SDK readiness court", 1)[0]

    def _make_executable(self, path: Path, body: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def _fake_sdk(self, root: Path, ldd_lines: list[str]) -> tuple[Path, Path, Path]:
        sdk = root / "sdk"
        qemu = sdk / "emulator" / "qemu" / "linux-x86_64" / "qemu-system-x86_64"
        emulator = sdk / "emulator" / "emulator"
        fake_ldd = root / "fake-ldd"
        self._make_executable(qemu, "#!/usr/bin/env bash\nexit 0\n")
        self._make_executable(emulator, "#!/usr/bin/env bash\necho 'Android emulator version TEST'\n")
        quoted = "\\n".join(line.replace("'", "'\\''") for line in ldd_lines)
        self._make_executable(fake_ldd, f"#!/usr/bin/env bash\nprintf '%b\\n' '{quoted}'\n")
        return sdk, qemu, fake_ldd

    def _run_helper(self, sdk: Path, fake_ldd: Path, evidence: Path) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["LDD_BIN"] = str(fake_ldd)
        return subprocess.run(
            [
                "bash",
                str(HELPER),
                "--sdk-root",
                str(sdk),
                "--evidence-dir",
                str(evidence),
                "--api-level",
                "35",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_bundled_emulator_library_is_not_misclassified_as_host_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sdk, _qemu, fake_ldd = self._fake_sdk(
                root,
                [
                    "libandroid-emu-tracing.so => not found",
                    "libpulse.so.0 => /lib/x86_64-linux-gnu/libpulse.so.0 (0x1)",
                ],
            )
            bundled = sdk / "emulator" / "lib64" / "libandroid-emu-tracing.so"
            bundled.parent.mkdir(parents=True, exist_ok=True)
            bundled.write_text("fake", encoding="utf-8")
            evidence = root / "evidence"
            result = self._run_helper(sdk, fake_ldd, evidence)
            self.assertEqual(result.returncode, 0, result.stderr)
            classification = (evidence / "emulator-host-dependency-classification-api-35.txt").read_text()
            self.assertIn("BUNDLED_INTERNAL\tlibandroid-emu-tracing.so", classification)
            self.assertIn("Android emulator version TEST", (evidence / "emulator-version-api-35.txt").read_text())

    def test_real_host_missing_library_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sdk, _qemu, fake_ldd = self._fake_sdk(root, ["libhost-missing.so.1 => not found"])
            evidence = root / "evidence"
            result = self._run_helper(sdk, fake_ldd, evidence)
            self.assertEqual(result.returncode, 43)
            classification = (evidence / "emulator-host-dependency-classification-api-35.txt").read_text()
            self.assertIn("HOST_MISSING\tlibhost-missing.so.1", classification)

    def test_bundle_symlink_escape_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sdk, _qemu, fake_ldd = self._fake_sdk(root, ["libescaped.so => not found"])
            outside = root / "outside.so"
            outside.write_text("fake", encoding="utf-8")
            link = sdk / "emulator" / "lib64" / "libescaped.so"
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(outside)
            evidence = root / "evidence"
            result = self._run_helper(sdk, fake_ldd, evidence)
            self.assertEqual(result.returncode, 43)
            classification = (evidence / "emulator-host-dependency-classification-api-35.txt").read_text()
            self.assertIn("INVALID_BUNDLE_PATH\tlibescaped.so", classification)

    def test_host_shared_library_repair_is_bounded_and_loader_aware(self) -> None:
        provision = self._provision_block()
        before = 'emulator-host-libs-before-api-${API_LEVEL}.txt'
        pulse_missing = "libpulse.so.0 => not found"
        pulse_install = "apt-get install -y --no-install-recommends libpulse0"
        provenance = 'emulator-host-package-provenance-api-${API_LEVEL}.txt'
        helper = "mobile/fuse-mobile/lab/validate_emulator_host_dependencies.sh"
        for token in (before, pulse_missing, pulse_install, provenance, helper):
            self.assertIn(token, provision)
        self.assertLess(provision.index(before), provision.index(pulse_install))
        self.assertLess(provision.index(pulse_install), provision.index(helper))
        self.assertNotIn("if grep -Fq '=> not found'", provision)

    def test_host_dependency_install_is_conditional_not_blind(self) -> None:
        provision = self._provision_block()
        condition = "if grep -Fq 'libpulse.so.0 => not found'"
        install = "apt-get install -y --no-install-recommends libpulse0"
        self.assertIn(condition, provision)
        self.assertIn(install, provision)
        self.assertLess(provision.index(condition), provision.index(install))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "fuse-mobile-android-build.yml"


class FuseMobileMdtafEmulatorHostDependencyTests(unittest.TestCase):
    def _provision_block(self) -> str:
        if not WORKFLOW.exists():
            self.skipTest("workflow-free export excludes repository workflow controls")
        workflow = WORKFLOW.read_text(encoding="utf-8")
        return workflow.split(
            "- name: Provision clean Android virtual device in stable AVD namespace", 1
        )[1].split("- name: Boot AVD through bounded exact-SDK readiness court", 1)[0]

    def test_host_shared_library_repair_is_bounded_and_fail_closed(self) -> None:
        provision = self._provision_block()
        sdk_install = '"$SDKMANAGER" "platform-tools" "emulator"'
        qemu_bind = 'QEMU="$SDK_ROOT/emulator/qemu/linux-x86_64/qemu-system-x86_64"'
        before = 'emulator-host-libs-before-api-${API_LEVEL}.txt'
        pulse_missing = "libpulse.so.0 => not found"
        pulse_install = "apt-get install -y --no-install-recommends libpulse0"
        provenance = 'emulator-host-package-provenance-api-${API_LEVEL}.txt'
        after = 'emulator-host-libs-after-api-${API_LEVEL}.txt'
        emulator_version = '"$EMULATOR" -version'
        for token in (sdk_install, qemu_bind, before, pulse_missing, pulse_install, provenance, after, emulator_version):
            self.assertIn(token, provision)
        self.assertLess(provision.index(sdk_install), provision.index(qemu_bind))
        self.assertLess(provision.index(qemu_bind), provision.index(before))
        self.assertLess(provision.index(before), provision.index(pulse_install))
        self.assertLess(provision.index(pulse_install), provision.index(after))
        self.assertLess(provision.index(after), provision.index(emulator_version))
        self.assertIn("if grep -Fq '=> not found'", provision)
        self.assertIn("exit 43", provision)

    def test_host_dependency_install_is_conditional_not_blind(self) -> None:
        provision = self._provision_block()
        condition = "if grep -Fq 'libpulse.so.0 => not found'"
        install = "apt-get install -y --no-install-recommends libpulse0"
        self.assertIn(condition, provision)
        self.assertIn(install, provision)
        self.assertLess(provision.index(condition), provision.index(install))
        self.assertIn("runner-host-provenance-api-${API_LEVEL}.txt", provision)
        self.assertIn("ImageVersion", provision)


if __name__ == "__main__":
    unittest.main()

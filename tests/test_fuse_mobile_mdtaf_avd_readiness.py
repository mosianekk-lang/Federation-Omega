from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "mobile" / "fuse-mobile" / "lab" / "boot_avd_bounded.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "fuse-mobile-android-build.yml"


class FuseMobileMdtafAvdReadinessTests(unittest.TestCase):
    def _fake_environment(self, root: Path, *, adb_mode: str) -> tuple[dict[str, str], Path]:
        sdk = root / "sdk"
        platform_tools = sdk / "platform-tools"
        emulator_dir = sdk / "emulator"
        avd_home = root / "avd-home"
        evidence = root / "evidence"
        platform_tools.mkdir(parents=True)
        emulator_dir.mkdir(parents=True)
        avd_home.mkdir()
        evidence.mkdir()
        (avd_home / "fuse-mdtaf-api-35.ini").write_text("path=fake\n", encoding="utf-8")
        kvm = root / "fake-kvm"
        kvm.write_text("fake\n", encoding="utf-8")

        adb = platform_tools / "adb"
        adb.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env bash
                set -euo pipefail
                mode="${FAKE_ADB_MODE:-ready}"
                if [[ "${1:-}" == "start-server" ]]; then exit 0; fi
                if [[ "${1:-}" == "version" ]]; then echo 'Android Debug Bridge version fake'; exit 0; fi
                if [[ "${1:-}" == "devices" ]]; then
                  echo 'List of devices attached'
                  if [[ "$mode" != "device_timeout" ]]; then echo 'emulator-5554 device product:fake model:fake'; fi
                  exit 0
                fi
                if [[ "${1:-}" == "-s" ]]; then
                  shift 2
                  if [[ "${1:-}" == "devices" ]]; then echo 'List of devices attached'; echo 'emulator-5554 device product:fake'; exit 0; fi
                  if [[ "${1:-}" == "shell" && "${2:-}" == "getprop" && "${3:-}" == "sys.boot_completed" ]]; then
                    if [[ "$mode" == "boot_timeout" ]]; then echo 0; else echo 1; fi
                    exit 0
                  fi
                  if [[ "${1:-}" == "shell" && "${2:-}" == "getprop" && "${3:-}" == "ro.build.version.sdk" ]]; then echo 35; exit 0; fi
                  if [[ "${1:-}" == "shell" && "${2:-}" == "getprop" && "${3:-}" == "ro.product.cpu.abi" ]]; then echo x86_64; exit 0; fi
                  if [[ "${1:-}" == "shell" && "${2:-}" == "input" ]]; then exit 0; fi
                fi
                echo "unexpected adb invocation: $*" >&2
                exit 64
                """
            ),
            encoding="utf-8",
        )
        adb.chmod(0o755)

        emulator = emulator_dir / "emulator"
        emulator.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env bash
                set -euo pipefail
                if [[ "${1:-}" == "-list-avds" ]]; then echo 'fuse-mdtaf-api-35'; exit 0; fi
                if [[ "${1:-}" == "-accel-check" ]]; then echo 'acceleration: fake-pass'; exit 0; fi
                trap 'exit 0' TERM INT
                while true; do sleep 1; done
                """
            ),
            encoding="utf-8",
        )
        emulator.chmod(0o755)

        env = os.environ.copy()
        env.update(
            {
                "ANDROID_SDK_ROOT": str(sdk),
                "ANDROID_HOME": str(sdk),
                "ANDROID_AVD_HOME": str(avd_home),
                "API_LEVEL": "35",
                "EVIDENCE_DIR": str(evidence),
                "KVM_DEVICE": str(kvm),
                "DEVICE_TIMEOUT_SECONDS": "1",
                "BOOT_TIMEOUT_SECONDS": "1",
                "POLL_INTERVAL_SECONDS": "0.05",
                "FAKE_ADB_MODE": adb_mode,
            }
        )
        return env, evidence

    @staticmethod
    def _terminate_success_emulator(evidence: Path) -> None:
        pid_path = evidence / "emulator-pid-api-35.txt"
        if not pid_path.exists():
            return
        pid = int(pid_path.read_text(encoding="utf-8").strip())
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    def test_source_forbids_unbounded_wait_and_requires_bounded_two_phase_readiness(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("wait-for-device", source)
        self.assertIn('"$ADB" start-server', source)
        self.assertIn("ANDROID_AVD_HOME", source)
        self.assertIn("${AVD_NAME}.ini", source)
        self.assertIn("-list-avds", source)
        self.assertIn("-accel-check", source)
        self.assertIn('kill -0 "$EMULATOR_PID"', source)
        self.assertIn("DEVICE_TIMEOUT_SECONDS", source)
        self.assertIn("BOOT_TIMEOUT_SECONDS", source)
        self.assertIn("sys.boot_completed", source)
        self.assertIn("adb-devices-failure", source)
        self.assertIn("emulator-tail-failure", source)

    def test_workflow_persists_one_avd_home_and_delegates_to_bounded_court(self) -> None:
        if not WORKFLOW.exists():
            self.skipTest("workflow-free export excludes repository workflow controls")
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("ANDROID_AVD_HOME=", workflow)
        self.assertIn('>> "$GITHUB_ENV"', workflow)
        self.assertIn("emulator -list-avds", workflow)
        self.assertIn("boot_avd_bounded.sh", workflow)
        self.assertNotIn("wait-for-device", workflow)

    def test_fake_ready_avd_passes_and_emits_ready_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env, evidence = self._fake_environment(Path(tmp), adb_mode="ready")
            proc = subprocess.run(["bash", str(SCRIPT)], cwd=ROOT, env=env, text=True, capture_output=True, timeout=10)
            try:
                self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
                self.assertEqual((evidence / "avd-readiness-api-35.txt").read_text(encoding="utf-8").strip(), "READY")
                self.assertEqual((evidence / "android-api.txt").read_text(encoding="utf-8").strip(), "35")
                self.assertEqual((evidence / "android-abi.txt").read_text(encoding="utf-8").strip(), "x86_64")
            finally:
                self._terminate_success_emulator(evidence)

    def test_device_discovery_timeout_fails_closed_with_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env, evidence = self._fake_environment(Path(tmp), adb_mode="device_timeout")
            proc = subprocess.run(["bash", str(SCRIPT)], cwd=ROOT, env=env, text=True, capture_output=True, timeout=10)
            self.assertEqual(proc.returncode, 6, proc.stderr or proc.stdout)
            self.assertIn("bounded adb device readiness timeout", proc.stderr)
            self.assertTrue((evidence / "adb-devices-failure-api-35.txt").is_file())
            self.assertTrue((evidence / "processes-failure-api-35.txt").is_file())
            self.assertTrue((evidence / "emulator-tail-failure-api-35.txt").is_file())

    def test_boot_completion_timeout_is_separately_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env, evidence = self._fake_environment(Path(tmp), adb_mode="boot_timeout")
            proc = subprocess.run(["bash", str(SCRIPT)], cwd=ROOT, env=env, text=True, capture_output=True, timeout=10)
            self.assertEqual(proc.returncode, 8, proc.stderr or proc.stdout)
            self.assertIn("bounded sys.boot_completed timeout", proc.stderr)
            self.assertTrue((evidence / "readiness-failure-api-35.txt").is_file())


if __name__ == "__main__":
    unittest.main()

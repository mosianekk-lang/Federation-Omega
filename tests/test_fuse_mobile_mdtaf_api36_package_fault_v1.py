from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "mobile" / "fuse-mobile" / "lab"
HELPER = LAB / "run_android_package_network_fault.sh"
SMOKE = LAB / "run_android_smoke.sh"


class FuseMobileMdtafApi36PackageFaultTests(unittest.TestCase):
    def test_helper_is_fail_closed_and_package_scoped(self) -> None:
        source = HELPER.read_text(encoding="utf-8")
        for marker in (
            "set-chain3-enabled true",
            "get-chain3-enabled",
            "set-package-networking-enabled false",
            "get-package-networking-enabled",
            'test "$RULE" = "$PACKAGE_ID:deny"',
            'test "$RULE" = "$PACKAGE_ID:allow"',
            'test "$CHAIN" = "chain:disabled"',
        ):
            self.assertIn(marker, source)
        self.assertNotIn("iptables", source)
        self.assertNotIn("adb ", source)

    def test_smoke_preserves_device_wide_path_and_uses_fallback_only_after_failure(self) -> None:
        source = SMOKE.read_text(encoding="utf-8")
        self.assertIn("cmd connectivity airplane-mode enable", source)
        self.assertIn("OFFLINE_FAULT_MODE=\"DEVICE_WIDE_RADIO\"", source)
        self.assertIn("PACKAGE_FIREWALL_FALLBACK=1", source)
        self.assertIn('run_android_package_network_fault.sh" apply', source)
        self.assertIn('run_android_package_network_fault.sh" restore', source)
        self.assertIn('"offline_fault_mode"', source)
        self.assertIn('"package_firewall_fallback"', source)
        self.assertIn("PACKAGE_UID_FIREWALL_DENY", source)

    def test_helper_apply_restore_round_trip_with_exact_sdk_fake_adb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sdk = tmp_path / "sdk"
            platform = sdk / "platform-tools"
            platform.mkdir(parents=True)
            state = tmp_path / "state.json"
            state.write_text(json.dumps({"chain": False, "deny": False}), encoding="utf-8")
            adb = platform / "adb"
            adb.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env python3
                    import json, os, sys
                    from pathlib import Path
                    state_path=Path(os.environ['FAKE_ADB_STATE'])
                    state=json.loads(state_path.read_text())
                    args=sys.argv[1:]
                    def save(): state_path.write_text(json.dumps(state))
                    if args[:4]==['shell','cmd','connectivity','help']:
                        print('set-chain3-enabled [true|false]')
                        print('get-chain3-enabled')
                        print('set-package-networking-enabled [true|false] [package name]')
                        print('get-package-networking-enabled [package name]')
                    elif args[:4]==['shell','cmd','connectivity','set-chain3-enabled']:
                        state['chain']=args[4]=='true'; save()
                    elif args[:4]==['shell','cmd','connectivity','get-chain3-enabled']:
                        print('chain:'+('enabled' if state['chain'] else 'disabled'))
                    elif args[:4]==['shell','cmd','connectivity','set-package-networking-enabled']:
                        state['deny']=args[4]=='false'; save()
                    elif args[:4]==['shell','cmd','connectivity','get-package-networking-enabled']:
                        print(args[4]+':'+('deny' if state['deny'] else 'allow'))
                    else:
                        print('unsupported '+repr(args), file=sys.stderr); raise SystemExit(2)
                    """
                ),
                encoding="utf-8",
            )
            adb.chmod(adb.stat().st_mode | stat.S_IXUSR)
            evidence = tmp_path / "evidence"
            env = os.environ.copy()
            env.update(
                {
                    "ANDROID_SDK_ROOT": str(sdk),
                    "ADB_BIN": str(adb),
                    "FAKE_ADB_STATE": str(state),
                }
            )
            apply = subprocess.run(
                ["bash", str(HELPER), "apply", "--evidence-dir", str(evidence)],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(apply.returncode, 0, apply.stderr or apply.stdout)
            applied = json.loads(state.read_text(encoding="utf-8"))
            self.assertTrue(applied["chain"])
            self.assertTrue(applied["deny"])
            self.assertEqual(
                (evidence / "package-network-deny-readback.txt").read_text().strip(),
                "com.federationomega.fusemobile:deny",
            )

            restore = subprocess.run(
                ["bash", str(HELPER), "restore", "--evidence-dir", str(evidence)],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(restore.returncode, 0, restore.stderr or restore.stdout)
            restored = json.loads(state.read_text(encoding="utf-8"))
            self.assertFalse(restored["chain"])
            self.assertFalse(restored["deny"])
            self.assertEqual(
                (evidence / "package-network-restore-readback.txt").read_text().strip(),
                "com.federationomega.fusemobile:allow",
            )


if __name__ == "__main__":
    unittest.main()

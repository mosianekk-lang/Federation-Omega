"""Bridge the existing pytest/API courts into ProofOS's unittest runner."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


class FuseOneIntegrationAdmissionTests(unittest.TestCase):
    def test_real_integration_courts_execute_and_collect_api_tests(self):
        with tempfile.TemporaryDirectory(prefix="fuse-one-admission-") as temporary:
            junit = Path(temporary) / "pytest-results.xml"
            env = {**os.environ, "PYTEST_ADDOPTS": f"--junitxml={junit}", "PYTHONDONTWRITEBYTECODE": "1"}
            result = subprocess.run(
                [sys.executable, "scripts/verify_fuse_one_os.py"],
                cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=180, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout[-6000:])
            self.assertTrue(junit.is_file(), "Integration runner must provide collected test evidence")
            cases = ET.parse(junit).findall(".//testcase")
            api_cases = [case for case in cases if "test_fuse_one_os_api" in case.get("classname", "")]
            self.assertGreaterEqual(len(api_cases), 9, "Pytest API functions must not disappear in unittest discovery")
            atomic_cases = [case for case in cases if "test_sol62_atomic_owned_mission" in case.get("classname", "")]
            self.assertGreaterEqual(len(atomic_cases), 15, "Atomic ownership and crash-recovery tests must execute in admission")
            for case in api_cases + atomic_cases:
                self.assertIsNone(case.find("skipped"), case.get("name"))
                self.assertIsNone(case.find("failure"), case.get("name"))
                self.assertIsNone(case.find("error"), case.get("name"))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JSON = ROOT / "mobile" / "fuse-mobile" / "app.json"
PACKAGE_JSON = ROOT / "mobile" / "fuse-mobile" / "package.json"
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
EXPECTED_RELEASE_VERSION = "0.3.0"


class FuseMobileVersionContractTests(unittest.TestCase):
    def test_expo_and_package_release_versions_are_identical(self) -> None:
        app = json.loads(APP_JSON.read_text(encoding="utf-8"))["expo"]
        package = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
        self.assertRegex(app["version"], SEMVER)
        self.assertEqual(app["version"], package["version"])
        self.assertEqual(app["version"], EXPECTED_RELEASE_VERSION)

    def test_release_application_identifiers_remain_canonical(self) -> None:
        app = json.loads(APP_JSON.read_text(encoding="utf-8"))["expo"]
        canonical = "com.federationomega.fusemobile"
        self.assertEqual(app["android"]["package"], canonical)
        self.assertEqual(app["ios"]["bundleIdentifier"], canonical)

    def test_package_remains_private_application_surface(self) -> None:
        package = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
        self.assertEqual(package["name"], "fuse-mobile")
        self.assertIs(package["private"], True)


if __name__ == "__main__":
    unittest.main()

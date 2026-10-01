from __future__ import annotations

import unittest

import federation.fcoa.memory_fabric_v1 as memory_pkg
import federation.fcoa.surface_census_v1 as surface_pkg


class FCOARuntimePackageRepairV1Tests(unittest.TestCase):
    def test_memory_package_imports(self):
        self.assertTrue(hasattr(memory_pkg, "FCOAMemoryNode"))

    def test_surface_census_package_imports(self):
        self.assertTrue(hasattr(surface_pkg, "FCOASurfaceCensus"))


if __name__ == "__main__":
    unittest.main()

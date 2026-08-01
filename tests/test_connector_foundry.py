import unittest

from evidenceops.connector_foundry.conformance import run_ects


class ConnectorFoundryConformanceTests(unittest.TestCase):
    def test_ects_reference_connector(self) -> None:
        report = run_ects()
        self.assertEqual(report["state"], "PASS")
        self.assertEqual(report["failed"], 0)
        self.assertEqual(report["passed"], 6)
        self.assertEqual(len(report["report_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()

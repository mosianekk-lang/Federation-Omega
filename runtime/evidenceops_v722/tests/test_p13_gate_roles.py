from __future__ import annotations

import sys
import unittest
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parents[1] / "p13_source_freshness"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import run_raw_provider_cycle as p13  # noqa: E402


class P13GateRoleTests(unittest.TestCase):
    def test_core_official_classes_are_only_current_rules_and_base_acts(self) -> None:
        self.assertEqual(
            p13.CORE_OFFICIAL_CLASSES,
            {
                "CURRENT_PRIMARY_RULES",
                "BASE_ACT_CONSOLIDATED_CURRENTNESS_UNVERIFIED",
            },
        )
        self.assertNotIn(p13.CONSULTATIVE_CLASS, p13.CORE_OFFICIAL_CLASSES)
        self.assertNotIn(p13.SECONDARY_CLASS, p13.CORE_OFFICIAL_CLASSES)

    def test_consultative_notice_is_an_optional_noncurrent_watch(self) -> None:
        self.assertEqual(
            p13.gate_role(p13.CONSULTATIVE_CLASS),
            "CONSULTATIVE_WATCH_OPTIONAL_NONCURRENT",
        )
        self.assertEqual(
            p13.classify(p13.CONSULTATIVE_CLASS, False, False, False),
            "CONSULTATIVE_NOTICE_PROVIDER_UNAVAILABLE_NONCURRENT",
        )

    def test_secondary_resources_remain_optional_archive_material(self) -> None:
        self.assertEqual(
            p13.gate_role(p13.SECONDARY_CLASS),
            "SECONDARY_ARCHIVE_OPTIONAL",
        )
        self.assertEqual(
            p13.classify(p13.SECONDARY_CLASS, False, False, False),
            "SECONDARY_RESOURCE_RAW_ARCHIVE_PROVIDER_BLOCKED",
        )

    def test_unknown_source_class_fails_closed(self) -> None:
        self.assertEqual(p13.gate_role("UNKNOWN"), "UNCLASSIFIED_FAIL_CLOSED")
        self.assertEqual(
            p13.classify("UNKNOWN", False, False, False),
            "UNCLASSIFIED_SOURCE_RETRIEVAL_FAILED",
        )


if __name__ == "__main__":
    unittest.main()

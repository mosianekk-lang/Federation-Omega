from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_level7_plus_v1 import EventClass, OwnerBoundary
from benchmarking.cfbe_omega.kim_dataverse_unified_event_contract_v1 import InstitutionalEvent, validate_institutional_event


class KimDataverseUnifiedEventContractTests(unittest.TestCase):
    def test_digest_only_event_contract_is_deterministic(self) -> None:
        event = InstitutionalEvent(
            "e", EventClass.MAINTENANCE, "phoenix", "a" * 40, "obj", "lane", ("proof",), OwnerBoundary.NONE, False, "sha256:" + "b" * 64
        )
        first = validate_institutional_event(event)
        second = validate_institutional_event(event)
        self.assertEqual(first, second)
        self.assertFalse(first["raw_payload_stored"])
        self.assertFalse(first["authority_inherited"])

    def test_external_effect_without_boundary_classification_fails_closed(self) -> None:
        event = InstitutionalEvent(
            "e", EventClass.MISSION, "system", "a" * 40, "obj", "lane", (), OwnerBoundary.NONE, True, "sha256:" + "b" * 64
        )
        with self.assertRaises(ValueError):
            validate_institutional_event(event)

    def test_raw_payload_shape_is_not_accepted_as_digest(self) -> None:
        event = InstitutionalEvent(
            "e", EventClass.RECOVERY, "system", "a" * 40, None, "lane", (), OwnerBoundary.NONE, False, "raw secret-like content"
        )
        with self.assertRaises(ValueError):
            validate_institutional_event(event)


if __name__ == "__main__":
    unittest.main()

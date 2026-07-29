from pathlib import Path

import pytest

from modisa_v2.inventory import inventory_eml


def test_actual_council_eml_reconciles_when_available():
    """Local-only confidential-evidence canary.

    The native Council EML must never be committed to CI. A clean CI environment therefore
    records this test as skipped rather than falsely passing it. The canary is executed only
    in an authorised evidence runtime where the exact native file is mounted.
    """
    path = Path("/mnt/data/Direct Council Notice and Request for Governance Assurance and Record Preservation.eml")
    if not path.exists():
        pytest.skip("Confidential Council EML is intentionally absent from portable CI")
    result = inventory_eml(
        path,
        application_visible_count=23,
        application_attachment_count=13,
        application_inline_count=10,
    )
    assert result.recursive_instance_count == 23
    assert result.completeness_state in {"VERIFIED", "VERIFIED_WITH_CATEGORY_DIFFERENCE"}

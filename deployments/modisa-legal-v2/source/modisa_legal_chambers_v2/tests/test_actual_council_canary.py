from pathlib import Path

from modisa_v2.inventory import inventory_eml


def test_actual_council_eml_reconciles_when_available():
    path = Path("/mnt/data/Direct Council Notice and Request for Governance Assurance and Record Preservation.eml")
    if not path.exists():
        return
    result = inventory_eml(
        path,
        application_visible_count=23,
        application_attachment_count=13,
        application_inline_count=10,
    )
    assert result.recursive_instance_count == 23
    assert result.completeness_state in {"VERIFIED", "VERIFIED_WITH_CATEGORY_DIFFERENCE"}

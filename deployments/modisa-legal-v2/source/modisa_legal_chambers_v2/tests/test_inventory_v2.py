from email.message import EmailMessage
from pathlib import Path
import zipfile

import pytest

from modisa_v2.inventory import InventoryLimitExceeded, InventoryLimits, inventory_eml, inventory_zip


def build_nested_eml(path: Path) -> None:
    nested = EmailMessage()
    nested.set_content("nested")
    nested.add_attachment(b"one", maintype="application", subtype="pdf", filename="one.pdf")
    outer = EmailMessage()
    outer.set_content("outer")
    outer.add_attachment(nested.as_bytes(), maintype="message", subtype="rfc822", filename="nested.eml")
    outer.add_attachment(b"two", maintype="application", subtype="pdf", filename="two.pdf")
    path.write_bytes(outer.as_bytes())


def test_three_level_inventory_reconciles(tmp_path: Path):
    path = tmp_path / "test.eml"
    build_nested_eml(path)
    result = inventory_eml(path, application_attachment_count=3, application_inline_count=0)
    assert result.top_level_count == 2
    assert result.recursive_instance_count == 3
    assert result.completeness_state == "VERIFIED"


def test_mime_part_limit_fails_closed(tmp_path: Path):
    path = tmp_path / "test.eml"
    build_nested_eml(path)
    with pytest.raises(InventoryLimitExceeded):
        inventory_eml(path, limits=InventoryLimits(max_parts=1))


def test_zip_bomb_ratio_is_blocked(tmp_path: Path):
    path = tmp_path / "bomb.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("large.txt", b"A" * 1_000_000)
    with pytest.raises(InventoryLimitExceeded):
        inventory_zip(path, limits=InventoryLimits(max_zip_ratio=5.0))

from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
import zipfile

from .ingestion import (
    DOCX_TYPE,
    IngestionError,
    MAX_OOXML_ARCHIVE_ENTRIES,
    MAX_OOXML_ENTRY_UNCOMPRESSED,
    MAX_OOXML_TOTAL_UNCOMPRESSED,
    _validate_ooxml_archive,
    parse_document,
)
from .verify_rc6 import verify as verify_rc6


def verify() -> dict[str, object]:
    rc6 = verify_rc6()

    stream = BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:p><w:r><w:t>Bounded</w:t></w:r></w:p></w:body></w:document>',
        )
    normal = parse_document(stream.getvalue(), DOCX_TYPE)

    total_limit_denied = False
    fake_total = SimpleNamespace(
        infolist=lambda: [
            SimpleNamespace(filename=f"x/{index}.xml", flag_bits=0, file_size=7_000_000, compress_size=7_000_000)
            for index in range(4)
        ]
    )
    try:
        _validate_ooxml_archive(fake_total)
    except IngestionError as exc:
        total_limit_denied = str(exc) == "OOXML_ARCHIVE_UNCOMPRESSED_LIMIT"

    encrypted_denied = False
    fake_encrypted = SimpleNamespace(
        infolist=lambda: [
            SimpleNamespace(filename="word/document.xml", flag_bits=1, file_size=100, compress_size=80)
        ]
    )
    try:
        _validate_ooxml_archive(fake_encrypted)
    except IngestionError as exc:
        encrypted_denied = str(exc) == "OOXML_ENCRYPTED_ENTRY_UNSUPPORTED"

    checks = {
        "rc6_regression": bool(rc6.get("passed")),
        "normal_docx_remains_usable": normal.text == "Bounded"
        and normal.parser_id == "DOCX_STDLIB_V2_BOUNDED",
        "bounded_archive_profile_visible": normal.metadata.get("archive_security_profile") == "OOXML_BOUNDED_V1",
        "archive_entry_ceiling_configured": MAX_OOXML_ARCHIVE_ENTRIES <= 512,
        "per_entry_uncompressed_ceiling_configured": MAX_OOXML_ENTRY_UNCOMPRESSED <= 8_000_000,
        "total_uncompressed_ceiling_configured": MAX_OOXML_TOTAL_UNCOMPRESSED <= 25_000_000,
        "total_uncompressed_overflow_denied": total_limit_denied,
        "encrypted_ooxml_denied": encrypted_denied,
        "provider_maturity_not_overpromoted": rc6.get("maturity") == "PROVIDER_BINDING_READY",
        "production_claim_remains_false": rc6.get("production_claim") is False,
    }
    return {
        "passed": all(checks.values()),
        "release": "1.0.0-rc7",
        "maturity": "PROVIDER_BINDING_READY",
        "internal_product_state": "INGESTION_RESOURCE_HARDENED_CANDIDATE",
        "scientific_state": rc6.get("internal_product_state"),
        "portfolio_state": rc6.get("portfolio_state"),
        "checks": checks,
        "production_claim": False,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(verify(), indent=2, sort_keys=True))

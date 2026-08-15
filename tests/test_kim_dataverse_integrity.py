from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from evidenceops.kim_dataverse.projection_contract import (
    ProjectionContractError,
    ProviderEffectProof,
    RuntimeAttestationObservation,
    SourceFrontierObservation,
    compile_projection,
    require_expected_source,
)
from evidenceops.kim_dataverse.schema_contract import KDVSchemaRegistry, SchemaContractError
from evidenceops.kim_dataverse.xlsx_semantic import XlsxSemanticWorkbook


class ProjectionContractTests(unittest.TestCase):
    def test_source_runtime_provider_remain_separate(self):
        source = SourceFrontierObservation(
            source_id="Federation-Omega", version_or_sha="new-main",
            observed_at="2026-08-15T09:00:00+02:00", verification_state="SIGNED_VERIFIED",
            query_time_provider_read=True,
        )
        runtime = RuntimeAttestationObservation(
            attestation_id="ATT-010", bound_source_version="older-main",
            observed_at="2026-08-15T08:22:00+02:00", scope="FEDERATION_OMEGA",
            qualification_state="QUALIFIED",
        )
        provider = ProviderEffectProof(
            provider="github-actions", receipt_id="RG-001",
            observed_at="2026-08-15T08:26:00+02:00", scope="SYS-FEDERATION-OMEGA",
            effect_state="HOST_BINDING_VERIFIED", truth_boundary="Does not prove SYS-ARCHITRON.",
        )
        projection = compile_projection(source=source, runtime=runtime, provider=provider)
        self.assertFalse(projection.source_runtime_same_version)
        self.assertFalse(projection.maturity_inheritance_allowed)
        self.assertTrue(projection.present_tense_source_claim_allowed)
        self.assertEqual(projection.runtime_attestation_frontier["bound_source_version"], "older-main")

    def test_persisted_source_is_as_of_without_query_time_read(self):
        source = SourceFrontierObservation(
            source_id="repo", version_or_sha="abc", observed_at="2026-08-15T09:00:00+02:00",
            verification_state="VERIFIED",
        )
        projection = compile_projection(source=source)
        self.assertTrue(projection.as_of_only)
        self.assertFalse(projection.present_tense_source_claim_allowed)

    def test_compare_and_set_fails_closed(self):
        with self.assertRaisesRegex(ProjectionContractError, "SOURCE_PRECONDITION_FAILED"):
            require_expected_source(expected="old", observed="new")


class SchemaContractTests(unittest.TestCase):
    def _registry(self) -> KDVSchemaRegistry:
        payload = {
            "schema_version": "TEST", "truth_boundary": "test",
            "sheets": [{"sheet_name": "S", "xlsx_export_name": "S", "role": "current_projection",
                "formula_count": 0, "table_blocks": [{"block_id": "S#R1", "header_row_1based": 1,
                    "data_start_row_1based": 2, "data_end_row_1based": 2, "fields": [
                        {"column_index_1based": 1, "name": "Flag", "logical_type": "boolean"},
                        {"column_index_1based": 2, "name": "Priority", "logical_type": "number"},
                        {"column_index_1based": 3, "name": "Observed_At", "logical_type": "timestamp_string"},
                    ]}] }],
        }
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(payload, tmp); tmp.close()
        return KDVSchemaRegistry.load(tmp.name)

    def test_normalises_legacy_string_types_for_new_write(self):
        registry = self._registry()
        row = registry.normalise_record(
            "S", {"Flag": "TRUE", "Priority": "0.9", "Observed_At": "2026-08-15T09:00:00+02:00"},
            require_full_schema=True,
        )
        self.assertIs(row["Flag"], True)
        self.assertEqual(row["Priority"], 0.9)

    def test_rejects_naive_timestamp(self):
        registry = self._registry()
        with self.assertRaisesRegex(SchemaContractError, "TIMESTAMP_TIMEZONE_REQUIRED"):
            registry.normalise_record(
                "S", {"Flag": True, "Priority": 1, "Observed_At": "2026-08-15T09:00:00"},
                require_full_schema=True,
            )


class XlsxSemanticTests(unittest.TestCase):
    def _fixture(self) -> Path:
        path = Path(tempfile.mkdtemp()) / "fixture.xlsx"
        content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/></Types>'''
        root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'''
        workbook = '''<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="S" sheetId="1" r:id="rId1"/></sheets></workbook>'''
        workbook_rels = '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>'''
        strings = '''<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="3" uniqueCount="3"><si><t>zero</t></si><si><t>one</t></si><si><t>resolved-text</t></si></sst>'''
        sheet = '''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="s"><v>2</v></c></row></sheetData></worksheet>'''
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("[Content_Types].xml", content_types); z.writestr("_rels/.rels", root_rels)
            z.writestr("xl/workbook.xml", workbook); z.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
            z.writestr("xl/sharedStrings.xml", strings); z.writestr("xl/worksheets/sheet1.xml", sheet)
        return path

    def test_shared_string_index_is_decoded(self):
        workbook = XlsxSemanticWorkbook.load(self._fixture())
        cell = workbook.cell("S", "A1")
        self.assertEqual(cell.value, "resolved-text")
        self.assertEqual(cell.ooxml_type, "s")

    def test_sheet_name_collision_fails_closed(self):
        workbook = XlsxSemanticWorkbook.load(self._fixture())
        with self.assertRaisesRegex(Exception, "XLSX_SHEETS_MISSING|XLSX_SHEET_NAME_COLLISION"):
            workbook.assert_sheet_identity_compatible(["A" * 32, "A" * 31 + "B"])


if __name__ == "__main__":
    unittest.main()

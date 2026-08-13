from __future__ import annotations

from io import BytesIO
from pathlib import Path
import base64
import json
import secrets
import tempfile
import unittest
import zipfile

from evidenceops.capital_intelligence_os.ingestion import (
    DOCX_TYPE,
    PDF_TYPE,
    XLSX_TYPE,
    IngestionError,
    parse_document,
)
from evidenceops.capital_intelligence_os.local_runtime import LocalRuntimeApplication
from evidenceops.capital_intelligence_os.policy import RuntimePolicy


class ParserTests(unittest.TestCase):
    def test_text_json_and_email_parsers(self):
        self.assertEqual(parse_document(b"hello", "text/plain").text, "hello")
        self.assertIn('"a": 1', parse_document(b'{"a":1}', "application/json").text)
        email_bytes = (
            b"From: seller@example.com\r\nTo: buyer@example.com\r\n"
            b"Subject: Diligence Update\r\nMIME-Version: 1.0\r\n"
            b"Content-Type: text/plain; charset=utf-8\r\n\r\nRevenue schedule attached"
        )
        parsed = parse_document(email_bytes, "message/rfc822")
        self.assertIn("Diligence Update", parsed.text)
        self.assertIn("Revenue schedule attached", parsed.text)

    def test_docx_parser(self):
        stream = BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr(
                "word/document.xml",
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body><w:p><w:r><w:t>Material Contract</w:t></w:r></w:p></w:body></w:document>",
            )
        parsed = parse_document(stream.getvalue(), DOCX_TYPE)
        self.assertEqual(parsed.text, "Material Contract")
        self.assertEqual(parsed.parser_id, "DOCX_STDLIB_V2_BOUNDED")
        self.assertEqual(parsed.metadata["archive_security_profile"], "OOXML_BOUNDED_V1")

    def test_xlsx_parser(self):
        stream = BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr(
                "xl/sharedStrings.xml",
                '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                "<si><t>Revenue</t></si></sst>",
            )
            archive.writestr(
                "xl/worksheets/sheet1.xml",
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<sheetData><row r="1"><c r="A1" t="s"><v>0</v></c>'
                '<c r="B1"><v>100</v></c></row></sheetData></worksheet>',
            )
        parsed = parse_document(stream.getvalue(), XLSX_TYPE)
        self.assertIn("Revenue", parsed.text)
        self.assertIn("100", parsed.text)
        self.assertEqual(parsed.metadata["nonempty_cells"], 2)
        self.assertEqual(parsed.metadata["archive_security_profile"], "OOXML_BOUNDED_V1")

    def test_pdf_requires_explicit_extraction(self):
        with self.assertRaisesRegex(IngestionError, "PDF_TEXT_EXTRACTION_REQUIRED"):
            parse_document(b"%PDF-reference", PDF_TYPE)
        parsed = parse_document(
            b"%PDF-reference",
            PDF_TYPE,
            extracted_text="Audited revenue is 100.",
        )
        self.assertEqual(parsed.parser_id, "PDF_EXTERNAL_TEXT_V1")
        self.assertTrue(parsed.warnings)


class PolicyTests(unittest.TestCase):
    def test_runtime_roles_are_configured_not_header_supplied(self):
        policy = RuntimePolicy("x" * 32, runtime_roles=("operator",))
        principal = policy.authenticate("Bearer " + "x" * 32, "t", "u")
        self.assertEqual(principal.roles, ("operator",))
        with self.assertRaisesRegex(ValueError, "unsupported runtime roles"):
            RuntimePolicy("x" * 32, runtime_roles=("operator", "self_granted_admin"))

    def test_new_workspace_routes_are_safe_but_financial_routes_remain_denied(self):
        policy = RuntimePolicy("x" * 32)
        policy.authorize("POST", "/v1/documents")
        policy.authorize("POST", "/v1/search")
        policy.authorize("GET", "/v1/diligence")
        policy.authorize("GET", "/v1/workspace")
        with self.assertRaisesRegex(PermissionError, "CONSEQUENTIAL_ROUTE_NOT_EXPOSED"):
            policy.authorize("POST", "/trade/order")


class WorkspaceRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.token = secrets.token_urlsafe(32)
        self.app = LocalRuntimeApplication(
            Path(self.temp.name) / "state.sqlite3",
            Path(self.temp.name) / "audit.sqlite3",
            self.token,
        )
        self.headers = {
            "Authorization": "Bearer " + self.token,
            "X-Tenant-ID": "tenant-a",
            "X-User-ID": "user-a",
        }

    def tearDown(self):
        self.app.close()
        self.temp.cleanup()

    def _document_body(
        self,
        *,
        content: bytes,
        logical_key: str = "financials",
        filename: str = "financials.json",
        document_type: str = "audited financial statements",
        content_type: str = "application/json",
        information_class: str = "CONFIDENTIAL",
        extracted_text: str = "",
    ) -> bytes:
        return json.dumps(
            {
                "logical_key": logical_key,
                "filename": filename,
                "document_type": document_type,
                "content_type": content_type,
                "content_base64": base64.b64encode(content).decode(),
                "information_class": information_class,
                "source_id": "synthetic-test-source",
                "extracted_text": extracted_text,
                "tags": ["synthetic", "diligence"],
            }
        ).encode()

    def test_confidential_ingest_duplicate_search_diligence_and_workspace(self):
        before = self.app.handle("GET", "/v1/diligence", self.headers)[1]["completeness"]
        body = self._document_body(content=b'{"revenue":100,"ebitda":20}')
        first = self.app.handle("POST", "/v1/documents", self.headers, body)
        second = self.app.handle("POST", "/v1/documents", self.headers, body)
        self.assertEqual(first[0], 200)
        self.assertFalse(first[1]["duplicate"])
        self.assertTrue(second[1]["duplicate"])
        self.assertGreater(first[1]["diligence"]["completeness"], before)

        search = self.app.handle(
            "POST",
            "/v1/search",
            self.headers,
            json.dumps({"query": "revenue"}).encode(),
        )
        self.assertEqual(search[0], 200)
        self.assertEqual(search[1]["result_count"], 1)

        workspace = self.app.handle("GET", "/v1/workspace", self.headers)
        self.assertEqual(workspace[0], 200)
        self.assertEqual(workspace[1]["document_count"], 1)
        self.assertEqual(len(workspace[1]["bundle_sha256"]), 64)
        self.assertTrue(workspace[1]["requires_human_decision"])
        self.assertFalse(workspace[1]["external_effects"])
        self.assertNotIn("extracted_text", workspace[1]["documents"][0])

    def test_version_chain_and_tenant_isolation(self):
        first = self.app.handle(
            "POST",
            "/v1/documents",
            self.headers,
            self._document_body(content=b'{"revenue":100}'),
        )
        second = self.app.handle(
            "POST",
            "/v1/documents",
            self.headers,
            self._document_body(content=b'{"revenue":120}', filename="financials-v2.json"),
        )
        self.assertEqual(first[1]["document"]["version_no"], 1)
        self.assertEqual(second[1]["document"]["version_no"], 2)
        self.assertEqual(
            second[1]["document"]["previous_document_id"],
            first[1]["document"]["document_id"],
        )
        other = {
            "Authorization": "Bearer " + self.token,
            "X-Tenant-ID": "tenant-b",
            "X-User-ID": "user-b",
        }
        snapshot = self.app.handle("GET", "/v1/workspace", other)
        self.assertEqual(snapshot[0], 200)
        self.assertEqual(snapshot[1]["document_count"], 0)

    def test_request_header_cannot_smuggle_restricted_role(self):
        headers = {**self.headers, "X-Roles": "admin,restricted_access"}
        result = self.app.handle(
            "POST",
            "/v1/documents",
            headers,
            self._document_body(
                content=b'{"secret":"restricted"}',
                information_class="RESTRICTED",
            ),
        )
        self.assertEqual(result[0], 400)
        self.assertIn("DOCUMENT_CLASSIFICATION_ACCESS_DENIED", result[1]["detail"])

    def test_runtime_can_be_explicitly_bound_to_restricted_role(self):
        self.app.close()
        self.app = LocalRuntimeApplication(
            Path(self.temp.name) / "state2.sqlite3",
            Path(self.temp.name) / "audit2.sqlite3",
            self.token,
            runtime_roles=("operator", "restricted_access"),
        )
        result = self.app.handle(
            "POST",
            "/v1/documents",
            self.headers,
            self._document_body(
                content=b'{"secret":"restricted"}',
                information_class="RESTRICTED",
            ),
        )
        self.assertEqual(result[0], 200)

    def test_malformed_base64_and_unknown_routes_fail_closed(self):
        bad = json.dumps(
            {
                "logical_key": "x",
                "filename": "x.txt",
                "document_type": "material contracts",
                "content_type": "text/plain",
                "content_base64": "not-@-base64",
                "information_class": "CONFIDENTIAL",
                "source_id": "synthetic",
            }
        ).encode()
        self.assertEqual(self.app.handle("POST", "/v1/documents", self.headers, bad)[0], 400)
        self.assertEqual(self.app.handle("GET", "/admin", self.headers)[0], 403)
        self.assertEqual(self.app.handle("POST", "/payments", self.headers, b"{}")[0], 403)

    def test_pdf_external_text_is_searchable_but_label_remains_explicit(self):
        body = self._document_body(
            content=b"%PDF-reference",
            logical_key="contract",
            filename="contract.pdf",
            document_type="material contracts",
            content_type="application/pdf",
            extracted_text="Change of control requires consent.",
        )
        result = self.app.handle("POST", "/v1/documents", self.headers, body)
        self.assertEqual(result[0], 200)
        self.assertEqual(result[1]["parser"]["parser_id"], "PDF_EXTERNAL_TEXT_V1")
        self.assertTrue(result[1]["parser"]["warnings"])
        search = self.app.handle(
            "POST",
            "/v1/search",
            self.headers,
            json.dumps({"query": "change control consent"}).encode(),
        )
        self.assertEqual(search[1]["result_count"], 1)

    def test_health_and_ready_include_vault_integrity(self):
        health = self.app.handle("GET", "/health", self.headers)
        ready = self.app.handle("GET", "/ready", self.headers)
        self.assertTrue(health[1]["vault_quick_check"])
        self.assertTrue(ready[1]["ready"])
        self.assertIn("deal_member", ready[1]["runtime_roles"])


if __name__ == "__main__":
    unittest.main()

import tempfile
from pathlib import Path
import unittest

import pymupdf

from federation.adobe_omega_email_print_v1 import (
    EmailPrintProfile,
    compile_print_html,
    parse_rfc822,
    render_rfc822,
)


BASIC = b"""From: Alice <alice@example.com>\r
To: Bob <bob@example.com>\r
Cc: Carol <carol@example.com>\r
Date: Sun, 7 Sep 2026 02:00:00 +0200\r
Subject: Print ready test\r
Message-ID: <print-1@example.com>\r
MIME-Version: 1.0\r
Content-Type: text/plain; charset=utf-8\r
\r
Hello Bob.\r
This email must become a print-ready PDF.\r
"""


HTML = b"""From: Alice <alice@example.com>\r
To: Bob <bob@example.com>\r
Date: Sun, 7 Sep 2026 02:00:00 +0200\r
Subject: HTML safety test\r
Message-ID: <print-2@example.com>\r
MIME-Version: 1.0\r
Content-Type: text/html; charset=utf-8\r
\r
<html><body><h1>Hello</h1><script>alert('x')</script><p style=\"color:red\">Body</p><img src=\"https://tracker.example/pixel.png\" alt=\"tracker\"></body></html>\r
"""


ATTACHMENT = b"""From: Alice <alice@example.com>\r
To: Bob <bob@example.com>\r
Date: Sun, 7 Sep 2026 02:00:00 +0200\r
Subject: Attachment test\r
Message-ID: <print-3@example.com>\r
MIME-Version: 1.0\r
Content-Type: multipart/mixed; boundary=BOUND\r
\r
--BOUND\r
Content-Type: text/plain; charset=utf-8\r
\r
Attached is the report.\r
--BOUND\r
Content-Type: text/plain; name=report.txt\r
Content-Disposition: attachment; filename=report.txt\r
Content-Transfer-Encoding: base64\r
\r
cmVwb3J0LWNvbnRlbnQ=\r
--BOUND--\r
"""


class AdobeOmegaEmailPrintTests(unittest.TestCase):
    def test_parse_rfc822_preserves_evidentiary_headers(self):
        view = parse_rfc822(BASIC)
        self.assertEqual(view.subject, "Print ready test")
        self.assertIn("alice@example.com", view.from_)
        self.assertIn("bob@example.com", view.to)
        self.assertIn("carol@example.com", view.cc)
        self.assertEqual(view.message_id, "<print-1@example.com>")
        self.assertIn("print-ready PDF", view.text_body)

    def test_print_profile_fingerprint_is_deterministic(self):
        a = EmailPrintProfile().fingerprint()
        b = EmailPrintProfile().fingerprint()
        self.assertEqual(a, b)
        self.assertEqual(len(a), 64)

    def test_html_sanitizer_removes_active_content_and_blocks_remote_images(self):
        view = parse_rfc822(HTML)
        html, active_removed, remote_blocked = compile_print_html((view,), EmailPrintProfile())
        self.assertTrue(active_removed)
        self.assertEqual(remote_blocked, 1)
        self.assertNotIn("<script", html.lower())
        self.assertNotIn("tracker.example/pixel.png", html)
        self.assertIn("[tracker]", html)
        self.assertIn("color:red", html)

    def test_attachment_manifest_is_included(self):
        view = parse_rfc822(ATTACHMENT)
        self.assertEqual(len(view.attachments), 1)
        html, _, _ = compile_print_html((view,), EmailPrintProfile())
        self.assertIn("report.txt", html)
        self.assertIn("Attachments", html)

    def test_basic_message_renders_and_semantically_reads_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "email.pdf"
            receipt = render_rfc822(BASIC, path)
            self.assertTrue(path.exists())
            self.assertTrue(receipt.semantic_readback_verified)
            self.assertFalse(receipt.provider_effect_performed)
            self.assertEqual(receipt.paper, "A4")
            self.assertEqual(receipt.orientation, "PORTRAIT")
            self.assertGreater(receipt.selected_page_count, 0)
            with pymupdf.open(path) as doc:
                text = "\n".join(page.get_text() for page in doc)
                self.assertIn("Print ready test", text)
                self.assertIn("alice@example.com", text)
                self.assertIn("print-ready PDF", text)

    def test_landscape_profile_changes_page_geometry(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "landscape.pdf"
            receipt = render_rfc822(
                BASIC,
                path,
                EmailPrintProfile(orientation="LANDSCAPE"),
            )
            self.assertGreater(receipt.page_width_pt, receipt.page_height_pt)

    def test_background_printing_can_be_disabled(self):
        view = parse_rfc822(HTML)
        profile = EmailPrintProfile(print_backgrounds=False)
        from federation.adobe_omega_email_print_v1 import _print_css
        css = _print_css(profile)
        self.assertIn("background-color:transparent", css)
        html, _, _ = compile_print_html((view,), profile)
        self.assertIn("HTML safety test", html)

    def test_page_range_validation_rejects_invalid_ranges(self):
        with self.assertRaises(ValueError):
            EmailPrintProfile(page_ranges="4-2").validate()
        with self.assertRaises(ValueError):
            EmailPrintProfile(page_ranges="zero").validate()

    def test_render_receipt_binds_source_pdf_profile_and_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt = render_rfc822(BASIC, Path(tmp) / "receipt.pdf")
            self.assertEqual(len(receipt.source_sha256), 64)
            self.assertEqual(len(receipt.pdf_sha256), 64)
            self.assertEqual(len(receipt.profile_sha256), 64)
            self.assertEqual(len(receipt.extracted_text_sha256), 64)
            self.assertEqual(len(receipt.receipt_sha256), 64)
            self.assertIn("From", receipt.header_fields_present)
            self.assertIn("To", receipt.header_fields_present)
            self.assertIn("Subject", receipt.header_fields_present)


if __name__ == "__main__":
    unittest.main()

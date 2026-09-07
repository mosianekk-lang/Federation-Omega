from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from federation.adobe_omega_email_print_v1 import EmailPrintProfile
from federation.adobe_omega_mailbox_batch_v1 import (
    MailProvider,
    convert_mailbox_batch,
    gmail_connector_message,
    outlook_connector_message,
)


GMAIL_RAW = b"""From: Alice <alice@example.com>\r\nTo: Bob <bob@example.com>\r\nCc: Audit <audit@example.com>\r\nDate: Sun, 07 Sep 2026 02:00:00 +0200\r\nSubject: Gmail print proof\r\nMessage-ID: <gmail-proof@example.com>\r\nMIME-Version: 1.0\r\nContent-Type: text/html; charset=utf-8\r\n\r\n<html><body><p>Gmail body <strong>verified</strong>.</p><script>alert(1)</script></body></html>\r\n"""


class AdobeOmegaMailboxBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            import pymupdf  # noqa: F401
        except ImportError as exc:
            raise unittest.SkipTest("PyMuPDF runtime unavailable") from exc

    def test_gmail_raw_mime_adapter_preserves_source_and_headers(self) -> None:
        message = gmail_connector_message({
            "id": "gmail-1",
            "thread_id": "thread-1",
            "raw_mime": GMAIL_RAW.decode("utf-8"),
        })
        self.assertEqual(MailProvider.GMAIL, message.provider)
        self.assertEqual("gmail-1", message.provider_message_id)
        self.assertEqual("<gmail-proof@example.com>", message.internet_message_id)
        self.assertEqual(GMAIL_RAW, message.source_bytes)
        self.assertIn("Gmail print proof", message.view.subject)

    def test_outlook_connector_shape_normalizes_body_and_recipients(self) -> None:
        message = outlook_connector_message({
            "id": "outlook-1",
            "subject": "Outlook print proof",
            "from": {"emailAddress": {"name": "Sender", "address": "sender@example.com"}},
            "toRecipients": [{"emailAddress": {"name": "Recipient", "address": "recipient@example.com"}}],
            "ccRecipients": [{"emailAddress": {"address": "audit@example.com"}}],
            "receivedDateTime": "2026-09-07T02:05:00+02:00",
            "internet_message_id": "<outlook-proof@example.com>",
            "body": {"contentType": "html", "content": "<p>Outlook body verified.</p>"},
            "conversationId": "conversation-1",
        })
        self.assertEqual(MailProvider.OUTLOOK, message.provider)
        self.assertIn("sender@example.com", message.view.from_)
        self.assertIn("recipient@example.com", message.view.to)
        self.assertEqual("<outlook-proof@example.com>", message.internet_message_id)
        self.assertIn("Outlook body verified", message.view.html_body)

    def test_gmail_and_outlook_batch_render_real_pdfs_with_semantic_readback(self) -> None:
        gmail = gmail_connector_message({
            "id": "gmail-1",
            "thread_id": "thread-1",
            "raw_mime": GMAIL_RAW.decode("utf-8"),
        })
        outlook = outlook_connector_message({
            "id": "outlook-1",
            "subject": "Outlook print proof",
            "from": {"emailAddress": {"name": "Sender", "address": "sender@example.com"}},
            "toRecipients": [{"emailAddress": {"address": "recipient@example.com"}}],
            "receivedDateTime": "2026-09-07T02:05:00+02:00",
            "internet_message_id": "<outlook-proof@example.com>",
            "body": {"contentType": "text", "content": "Outlook body verified."},
        })
        with tempfile.TemporaryDirectory() as tmp:
            receipt = convert_mailbox_batch(
                (gmail, outlook),
                tmp,
                EmailPrintProfile(paper="A4", orientation="PORTRAIT"),
                max_messages=10,
            )
            self.assertEqual(2, receipt.converted_count)
            self.assertEqual(0, receipt.failed_count)
            self.assertFalse(receipt.provider_effect_performed)
            self.assertEqual((("GMAIL", 1), ("OUTLOOK", 1)), receipt.provider_counts)
            self.assertTrue(all(item.semantic_readback_verified for item in receipt.items))
            for item in receipt.items:
                path = Path(tmp) / item.output_name
                self.assertTrue(path.is_file())
                self.assertGreater(path.stat().st_size, 1000)
                self.assertEqual(64, len(item.pdf_sha256))
            self.assertEqual(64, len(receipt.receipt_sha256))

    def test_duplicate_provider_identity_is_rejected(self) -> None:
        message = gmail_connector_message({
            "id": "gmail-1",
            "raw_mime": GMAIL_RAW.decode("utf-8"),
        })
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "duplicate provider message identity"):
                convert_mailbox_batch((message, message), tmp)

    def test_batch_limit_is_enforced_before_render(self) -> None:
        message = gmail_connector_message({
            "id": "gmail-1",
            "raw_mime": GMAIL_RAW.decode("utf-8"),
        })
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "batch exceeds"):
                convert_mailbox_batch((message, message), tmp, max_messages=1)


if __name__ == "__main__":
    unittest.main()

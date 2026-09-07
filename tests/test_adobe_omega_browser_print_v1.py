import unittest

from federation.adobe_omega_browser_print_v1 import (
    BrowserPrintContract,
    compile_cdp_print_to_pdf,
    default_email_footer_template,
    default_email_header_template,
    email_print_css,
)


class AdobeOmegaBrowserPrintTests(unittest.TestCase):
    def test_a4_portrait_dimensions_compile(self):
        result = compile_cdp_print_to_pdf(BrowserPrintContract())
        params = result["printToPDF"]
        self.assertFalse(params["landscape"])
        self.assertAlmostEqual(params["paperWidth"], 8.2677165354)
        self.assertAlmostEqual(params["paperHeight"], 11.6929133858)
        self.assertTrue(params["printBackground"])
        self.assertTrue(params["preferCSSPageSize"])

    def test_landscape_swaps_geometry(self):
        contract = BrowserPrintContract(landscape=True)
        params = compile_cdp_print_to_pdf(contract)["printToPDF"]
        self.assertGreater(params["paperWidth"], params["paperHeight"])

    def test_page_ranges_scale_margins_are_preserved(self):
        contract = BrowserPrintContract(
            page_ranges="1-3,5",
            scale=0.9,
            margin_top_in=0.3,
            margin_bottom_in=0.4,
            margin_left_in=0.5,
            margin_right_in=0.6,
        )
        params = compile_cdp_print_to_pdf(contract)["printToPDF"]
        self.assertEqual(params["pageRanges"], "1-3,5")
        self.assertEqual(params["scale"], 0.9)
        self.assertEqual(params["marginTop"], 0.3)
        self.assertEqual(params["marginRight"], 0.6)

    def test_accessibility_and_outline_are_first_class(self):
        params = compile_cdp_print_to_pdf(BrowserPrintContract())["printToPDF"]
        self.assertTrue(params["generateTaggedPDF"])
        self.assertTrue(params["generateDocumentOutline"])

    def test_font_wait_and_remote_resource_policy_are_explicit(self):
        result = compile_cdp_print_to_pdf(BrowserPrintContract(wait_for_fonts=True))
        self.assertTrue(result["preconditions"]["wait_for_fonts"])
        self.assertEqual(
            result["preconditions"]["remote_resource_policy"],
            "BLOCK_UNLESS_EXPLICITLY_ALLOWED",
        )
        self.assertFalse(result["provider_effect_performed"])

    def test_header_footer_templates_model_browser_tokens(self):
        header = default_email_header_template("Quarterly update")
        footer = default_email_footer_template()
        self.assertIn("Quarterly update", header)
        self.assertIn("class='date'", header)
        self.assertIn("pageNumber", footer)
        self.assertIn("totalPages", footer)

    def test_print_css_contains_paged_media_controls(self):
        css = email_print_css(paper="A4", landscape=False, margin_mm=14)
        self.assertIn("@page", css)
        self.assertIn("A4 portrait", css)
        self.assertIn("@media print", css)
        self.assertIn("break-inside: avoid-page", css)
        self.assertIn("orphans: 2", css)
        self.assertIn("print-color-adjust: exact", css)

    def test_invalid_page_range_fails_closed(self):
        with self.assertRaises(ValueError):
            BrowserPrintContract(page_ranges="5-2").validate()
        with self.assertRaises(ValueError):
            BrowserPrintContract(page_ranges="all").validate()

    def test_active_template_content_is_rejected(self):
        with self.assertRaises(ValueError):
            BrowserPrintContract(header_template="<script>alert(1)</script>").validate()


if __name__ == "__main__":
    unittest.main()

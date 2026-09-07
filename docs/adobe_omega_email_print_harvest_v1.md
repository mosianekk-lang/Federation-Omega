# Federation Adobe Ω — Email Print-to-PDF Harvest v1

**Build:** `BUILD-AO-011`  
**Purpose:** make email content printable as durable PDF without depending on Adobe, Gmail UI, Outlook UI, or a single browser session.

## Harvested browser / PDF-print controls

The public Chromium/Edge and CSS paged-media behavior is represented in `federation/adobe_omega_browser_print_v1.py`:

- Save/print to PDF as a paginated document.
- Portrait / landscape.
- A5, A4, A3, Letter, Legal and Ledger paper presets.
- Page ranges.
- Render scale.
- Top/right/bottom/left margins.
- Header/footer templates with date, title, page number and total pages.
- Background graphics / print color preservation.
- CSS `@media print` and `@page` page-size/orientation/margin control.
- CSS page fragmentation controls (`break-*`, `orphans`, `widows`).
- Prefer CSS page size rather than silently scaling to another paper size.
- Wait-for-fonts precondition for stable typography.
- Tagged PDF and document outline options when the Chromium runtime supports them.
- Return-as-stream support for bounded pipeline processing instead of mandatory base64 materialization.

Public references:

- MDN Printing / print media: https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Media_queries/Printing
- MDN CSS paged media: https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Paged_media
- MDN `@page`: https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/%40page
- MDN `print-color-adjust`: https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/print-color-adjust
- Chromium DevTools `Page.printToPDF`: https://chromedevtools.github.io/devtools-protocol/1-3/Page/#method-printToPDF
- Puppeteer PDF options: https://pptr.dev/api/puppeteer.pdfoptions

## Email-specific capability harvest

Browser print dialogs do not by themselves establish evidentiary email fidelity, so Adobe Ω adds an email normalization layer in `federation/adobe_omega_email_print_v1.py`:

- RFC 5322/MIME message parsing.
- From / To / Cc / Date / Subject / Message-ID preservation.
- Plain-text and HTML body handling.
- Active-content sanitization before print rendering.
- Remote tracking image blocking by default.
- Local CID/inline image resolution without remote disclosure.
- Attachment manifest with filename, MIME type, size and disposition.
- Quoted-thread content preservation through printable HTML flow.
- Long-line/preformatted wrapping.
- Wide table/image bounding to printable page width.
- A4 as the sovereign default, while allowing Letter/Legal and landscape.
- Page range selection.
- Header/footer page numbering.
- PDF metadata derived from the source message.
- Re-open/readback after PDF generation.
- Source hash, PDF hash, profile hash, extracted-text hash and deterministic receipt.
- No external provider effect in the local PyMuPDF route.

## Execution lanes

### Lane 1 — sovereign local / current implementation

PyMuPDF `Story` + `DocumentWriter` renders sanitized HTML/CSS into paginated PDF. PyMuPDF is already an admitted Federation dependency through FastDoc v2. The produced PDF is reopened with a separate parse pass to verify page geometry, headers and text presence before the receipt can say semantic readback passed.

This lane is designed to remain usable when Adobe, Gmail, Outlook or browser automation is unavailable.

### Lane 2 — Edge/Chromium fidelity / adapter contract

`BrowserPrintContract` compiles the exact current public `Page.printToPDF` parameter set but does not falsely claim a browser runtime. When an authorised local/hosted Chromium adapter is bound, it can use this contract to match browser print-preview behavior and add tagged-PDF/document-outline features.

### Lane 3 — optional Adobe Acrobat provider

The already-proven standalone Acrobat connector remains an optional provider route. It is not required for local email printing and cannot transfer authority to the local renderer.

## Print-ready truth boundary

`PRINT_READY_EMAIL_PDF` means:

1. the PDF parses successfully;
2. selected pages exist at the requested paper geometry/orientation;
3. evidentiary email headers are present in extracted PDF text when supplied;
4. printable body content is present;
5. the profile/source/output fingerprints are bound in the receipt;
6. active HTML is removed and remote resources follow policy;
7. provider effect is false for the local route.

It does **not** automatically mean PDF/X press-production compliance, PDF/A archival conformance, accessibility conformance, legal authenticity, or cryptographic email signature validation. Those are separate capability/proof gates.

## Next qualification waves

1. Run the local RFC-message regression court on hosted CI.
2. Add a Gmail-message adapter and an Outlook-message adapter that compile connector-visible messages into the same `EmailMessageView`; no send action is required.
3. Qualify high-fidelity Chromium/Edge rendering against the local renderer with matched fixtures.
4. Add optional PDF/A archival conversion/validation and tagged-PDF accessibility court.
5. Batch-render mailbox-selected messages with bounded concurrency, deterministic filenames, thread grouping and an index manifest.

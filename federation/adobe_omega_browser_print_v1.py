"""Federation Adobe Ω browser print-to-PDF contract v1.

Models the public Chromium/Edge print-to-PDF surface as a provider-neutral
contract.  It does not launch a browser by itself.  A future/local browser adapter
can consume the generated DevTools `Page.printToPDF` parameters after runtime
identity, executable availability and sandbox policy are verified.

The contract mirrors the useful browser print dialog controls: paper, orientation,
page ranges, scale, margins, headers/footers, background graphics and CSS page
size.  It additionally exposes tagged-PDF and document-outline options available
in current Chromium DevTools implementations.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from html import escape
import json
import re


SCHEMA = "FEDERATION_ADOBE_OMEGA_BROWSER_PRINT_V1"

PAPER_INCHES = {
    "A5": (5.8267716535, 8.2677165354),
    "A4": (8.2677165354, 11.6929133858),
    "A3": (11.6929133858, 16.5354330709),
    "LETTER": (8.5, 11.0),
    "LEGAL": (8.5, 14.0),
    "LEDGER": (11.0, 17.0),
}


@dataclass(frozen=True, slots=True)
class BrowserPrintContract:
    paper: str = "A4"
    landscape: bool = False
    display_header_footer: bool = True
    print_background: bool = True
    scale: float = 1.0
    margin_top_in: float = 0.45
    margin_bottom_in: float = 0.5
    margin_left_in: float = 0.45
    margin_right_in: float = 0.45
    page_ranges: str = ""
    prefer_css_page_size: bool = True
    tagged_pdf: bool = True
    document_outline: bool = True
    wait_for_fonts: bool = True
    transfer_mode: str = "ReturnAsStream"
    header_template: str = ""
    footer_template: str = ""

    def validate(self) -> "BrowserPrintContract":
        paper = self.paper.upper()
        if paper not in PAPER_INCHES:
            raise ValueError(f"unsupported paper preset: {paper}")
        if not 0.1 <= float(self.scale) <= 2.0:
            raise ValueError("scale must be between 0.1 and 2.0")
        if self.transfer_mode not in {"ReturnAsBase64", "ReturnAsStream"}:
            raise ValueError("invalid transfer_mode")
        for value in (self.margin_top_in, self.margin_bottom_in, self.margin_left_in, self.margin_right_in):
            if float(value) < 0 or float(value) > 2.5:
                raise ValueError("browser print margins must be between 0 and 2.5 inches")
        _validate_page_ranges(self.page_ranges)
        _validate_template(self.header_template)
        _validate_template(self.footer_template)
        return self

    @property
    def paper_width_in(self) -> float:
        width, height = PAPER_INCHES[self.paper.upper()]
        return height if self.landscape else width

    @property
    def paper_height_in(self) -> float:
        width, height = PAPER_INCHES[self.paper.upper()]
        return width if self.landscape else height

    def fingerprint(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return sha256(payload.encode("utf-8")).hexdigest()


def _validate_page_ranges(value: str) -> None:
    value = (value or "").strip()
    if not value:
        return
    for token in value.split(","):
        token = token.strip()
        if re.fullmatch(r"[1-9][0-9]*", token):
            continue
        match = re.fullmatch(r"([1-9][0-9]*)-([1-9][0-9]*)", token)
        if not match or int(match.group(1)) > int(match.group(2)):
            raise ValueError("invalid page range")


def _validate_template(value: str) -> None:
    lowered = (value or "").lower()
    if any(token in lowered for token in ("<script", "javascript:", "onload=", "onerror=")):
        raise ValueError("active content is prohibited in print header/footer templates")


def default_email_header_template(subject: str = "") -> str:
    title = escape(subject or "Email")
    return (
        "<div style='font-size:8px;width:100%;padding:0 8mm;color:#555;'>"
        f"<span>{title}</span>"
        "<span style='float:right' class='date'></span>"
        "</div>"
    )


def default_email_footer_template() -> str:
    return (
        "<div style='font-size:8px;width:100%;padding:0 8mm;color:#666;text-align:center;'>"
        "Page <span class='pageNumber'></span> of <span class='totalPages'></span>"
        "</div>"
    )


def compile_cdp_print_to_pdf(contract: BrowserPrintContract) -> dict[str, object]:
    """Compile exact public Chromium Page.printToPDF parameters.

    `wait_for_fonts` is returned separately as an execution precondition because it
    is a Puppeteer/browser-adapter concern, not a Page.printToPDF parameter.
    """
    contract.validate()
    print_params: dict[str, object] = {
        "landscape": contract.landscape,
        "displayHeaderFooter": contract.display_header_footer,
        "printBackground": contract.print_background,
        "scale": float(contract.scale),
        "paperWidth": contract.paper_width_in,
        "paperHeight": contract.paper_height_in,
        "marginTop": float(contract.margin_top_in),
        "marginBottom": float(contract.margin_bottom_in),
        "marginLeft": float(contract.margin_left_in),
        "marginRight": float(contract.margin_right_in),
        "pageRanges": contract.page_ranges,
        "headerTemplate": contract.header_template,
        "footerTemplate": contract.footer_template,
        "preferCSSPageSize": contract.prefer_css_page_size,
        "transferMode": contract.transfer_mode,
        "generateTaggedPDF": contract.tagged_pdf,
        "generateDocumentOutline": contract.document_outline,
    }
    return {
        "schema": SCHEMA,
        "printToPDF": print_params,
        "preconditions": {
            "emulate_media": "print",
            "wait_for_fonts": contract.wait_for_fonts,
            "network_idle_required": True,
            "remote_resource_policy": "BLOCK_UNLESS_EXPLICITLY_ALLOWED",
        },
        "contract_sha256": contract.fingerprint(),
        "provider_effect_performed": False,
    }


def email_print_css(
    *,
    paper: str = "A4",
    landscape: bool = False,
    margin_mm: float = 14.0,
    preserve_backgrounds: bool = True,
) -> str:
    paper = paper.upper()
    if paper not in PAPER_INCHES:
        raise ValueError("unsupported paper preset")
    if not 0 <= float(margin_mm) <= 50:
        raise ValueError("margin_mm must be between 0 and 50")
    orientation = "landscape" if landscape else "portrait"
    color = "exact" if preserve_backgrounds else "economy"
    background_override = "" if preserve_backgrounds else "*{background:transparent!important;}"
    return f"""
@page {{ size: {paper} {orientation}; margin: {float(margin_mm):.2f}mm; }}
@media print {{
  html, body {{ width: auto !important; min-width: 0 !important; }}
  body {{ overflow: visible !important; print-color-adjust: {color}; -webkit-print-color-adjust: {color}; }}
  table {{ max-width: 100% !important; border-collapse: collapse; }}
  img, svg, canvas {{ max-width: 100% !important; height: auto !important; }}
  pre, code {{ white-space: pre-wrap !important; overflow-wrap: anywhere; }}
  p, li, blockquote {{ orphans: 2; widows: 2; }}
  h1, h2, h3, h4, h5, h6 {{ break-after: avoid-page; }}
  tr, img, blockquote, .attachment-manifest {{ break-inside: avoid-page; }}
  a {{ overflow-wrap: anywhere; }}
  .screen-only, nav, [role='navigation'] {{ display: none !important; }}
  {background_override}
}}
"""

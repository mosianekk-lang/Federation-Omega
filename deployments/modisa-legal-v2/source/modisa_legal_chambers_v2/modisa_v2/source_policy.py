from __future__ import annotations

from urllib.parse import urlparse


PRIMARY_SOURCE_DOMAINS = {
    "gov.za",
    "www.gov.za",
    "justice.gov.za",
    "www.justice.gov.za",
    "labour.gov.za",
    "www.labour.gov.za",
    "ccma.org.za",
    "www.ccma.org.za",
    "saflii.org",
    "www.saflii.org",
    "concourt.org.za",
    "www.concourt.org.za",
}


def normalised_domain(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Authority source must be an absolute HTTP(S) URL")
    return parsed.netloc.lower().split(":", 1)[0]


def is_approved_primary_source(url: str) -> bool:
    domain = normalised_domain(url)
    return domain in PRIMARY_SOURCE_DOMAINS or any(domain.endswith("." + item) for item in PRIMARY_SOURCE_DOMAINS)


def enforce_primary_source(url: str) -> str:
    domain = normalised_domain(url)
    if not is_approved_primary_source(url):
        raise ValueError(f"Source domain is not approved as a primary-law source: {domain}")
    return domain

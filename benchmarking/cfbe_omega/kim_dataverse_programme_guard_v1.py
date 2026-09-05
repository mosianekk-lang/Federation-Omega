from __future__ import annotations

from pathlib import Path


FORBIDDEN_AUTHORITY_PHRASES = (
    "iam_wif_mutation_authorized\": true",
    "provider_effect_authorized\": true",
    "external_effect_authorized\": true",
    "financial_authority\": true",
    "destructive_authority\": true",
)


def scan_text_for_authority_expansion(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    return tuple(phrase for phrase in FORBIDDEN_AUTHORITY_PHRASES if phrase.lower() in lowered)


def scan_files(paths: tuple[Path, ...]) -> tuple[tuple[str, str], ...]:
    findings = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for phrase in scan_text_for_authority_expansion(text):
            findings.append((str(path), phrase))
    return tuple(findings)

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

EXCLUDED_PARTS = {".git", ".venv", "venv", "node_modules", "__pycache__"}
TEXT_SUFFIXES = {
    ".py", ".json", ".yaml", ".yml", ".md", ".txt", ".toml", ".ini",
    ".cfg", ".sh", ".js", ".ts", ".html", ".xml", ".csv"
}

ALLOWED_SENTINELS = {
    "PRIVATE_RUNTIME_CONFIG",
    "PRIVATE_RECEIPT_REFERENCE",
    "PRIVATE_IN_PLACE_BRIDGE",
    "PRIVATE_IN_PLACE_CANONICAL_BRIDGE",
}

RULES = [
    (
        "live_google_identifier",
        re.compile(
            r'(?i)(spreadsheet_id|parent_folder_id|file_id|folder_id|document_id|gmail_message_id)'
            r'\s*[=:]\s*["\'](?!PRIVATE_)([A-Za-z0-9_-]{20,})["\']'
        ),
    ),
    (
        "embedded_google_url",
        re.compile(r'https://(?:docs|drive)\.google\.com/(?:[^\s"\']+/){1,4}[A-Za-z0-9_-]{20,}'),
    ),
    (
        "private_key",
        re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    ),
    (
        "provider_secret",
        re.compile(r'(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|password)\s*[=:]\s*["\'][^"\']{8,}["\']'),
    ),
]


def iter_text_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_PARTS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        yield path


def main() -> int:
    findings: list[str] = []
    for path in iter_text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(sentinel in text for sentinel in ALLOWED_SENTINELS):
            # Sentinels are allowed, but the rest of the file is still scanned.
            pass
        for rule_name, pattern in RULES:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append(f"{path.relative_to(ROOT)}:{line}: {rule_name}")

    if findings:
        print("Public repository leak guard failed:")
        for finding in findings:
            print(f" - {finding}")
        return 1

    print("Public repository leak guard passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

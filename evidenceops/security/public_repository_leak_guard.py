from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]

EXCLUDED_PARTS = {".git", ".venv", "venv", "node_modules", "__pycache__"}
TEXT_SUFFIXES = {
    ".py", ".json", ".yaml", ".yml", ".md", ".txt", ".toml", ".ini",
    ".cfg", ".sh", ".js", ".ts", ".html", ".xml", ".csv"
}

SAFE_PLACEHOLDER_PREFIXES = (
    "PRIVATE_",
    "RETIRED_",
    "REDACTED",
    "PLACEHOLDER",
    "EXAMPLE_",
    "DUMMY_",
    "CHANGE_ME",
    "REPLACE_WITH_",
    "GOOGLE_DRIVE_",
    "KIM_CANONICAL_",
)

ID_ASSIGNMENT = re.compile(
    r"(?i)(spreadsheet_id|parent_folder_id|drive_file_id|google_drive_file_id|"
    r"file_id|folder_id|document_id|gmail_message_id|spreadsheetId|"
    r"parentFolderId|driveFileId|googleDriveFileId|fileId|folderId|documentId)"
    r"\s*[=:]\s*[\"']([^\"']+)[\"']"
)

PROVIDER_ASSIGNMENT = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|"
    r"password|service[_-]?token|signing[_-]?key)"
    r"\s*[=:]\s*[\"']([^\"']*)[\"']"
)

# Build the prefix in separate fragments so this detector does not match its
# own source text. The generic form covers project-scoped and legacy key forms.
OPENAI_KEY_PATTERN = re.compile(
    r"\b" + r"sk" + r"-(?:proj-)?[A-Za-z0-9_-]{20,}\b"
)

STATIC_RULES = [
    (
        "embedded_google_url",
        re.compile(
            r"https://(?:docs|drive)\.google\.com/(?:[^\s\"']+/){1,4}"
            r"[A-Za-z0-9_-]{20,}"
        ),
    ),
    (
        "private_key",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
    (
        "openai_api_key",
        OPENAI_KEY_PATTERN,
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


def is_safe_placeholder(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return True
    upper = stripped.upper()
    if upper.startswith(SAFE_PLACEHOLDER_PREFIXES):
        return True
    if stripped.startswith(("$", "${", "$(", "{{", "<")):
        return True
    return False


def looks_like_live_identifier(value: str) -> bool:
    stripped = value.strip()
    return (
        not is_safe_placeholder(stripped)
        and len(stripped) >= 20
        and re.fullmatch(r"[A-Za-z0-9_-]+", stripped) is not None
    )


def looks_like_literal_secret(value: str) -> bool:
    stripped = value.strip()
    if is_safe_placeholder(stripped):
        return False
    return len(stripped) >= 16


def add_finding(findings: list[str], path: pathlib.Path, text: str,
                start: int, rule_name: str) -> None:
    line = text.count("\n", 0, start) + 1
    findings.append(f"{path.relative_to(ROOT)}:{line}: {rule_name}")


def main() -> int:
    findings: list[str] = []
    for path in iter_text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        for match in ID_ASSIGNMENT.finditer(text):
            if looks_like_live_identifier(match.group(2)):
                add_finding(
                    findings, path, text, match.start(), "live_provider_identifier"
                )

        for match in PROVIDER_ASSIGNMENT.finditer(text):
            if looks_like_literal_secret(match.group(2)):
                add_finding(
                    findings, path, text, match.start(), "literal_provider_secret"
                )

        for rule_name, pattern in STATIC_RULES:
            for match in pattern.finditer(text):
                add_finding(findings, path, text, match.start(), rule_name)

    if findings:
        print("Public repository leak guard failed:")
        for finding in sorted(set(findings)):
            print(f" - {finding}")
        return 1

    print("Public repository leak guard passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

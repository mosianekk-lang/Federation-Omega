#!/usr/bin/env python3
"""Bundle-aware, fail-closed Google Apps Script authorization and lineage gate.

The public compatibility function ``validate_apps_script_source`` is preserved.
Version 2 additionally understands restorable fleet-backup JSON, audits every
embedded Apps Script file, detects global namespace collisions, separates
canonical target / OAuth consumer / legacy transport roles, and emits a
hash-bound receipt. The module performs no provider call or mutation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SCHEMA = "FEDOMEGA-APPS-SCRIPT-AUTHORIZATION-GATE-2"
VERSION = "2.1.0"
DEFAULT_CANONICAL_PROJECT_NUMBER = "257649435135"
DEFAULT_LEGACY_PROJECT_NUMBERS = (
    "516699068552",
    "516690968552",
    "979287460558",
)


class AppsScriptSecurityError(ValueError):
    """Raised when Apps Script source violates the authorization contract."""


class Severity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    INFO = "INFO"


@dataclass(frozen=True)
class ScriptFile:
    name: str
    file_type: str
    source: str

    @property
    def source_sha256(self) -> str:
        return hashlib.sha256(self.source.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Finding:
    code: str
    severity: Severity
    message: str
    files: tuple[str, ...]
    evidence: tuple[str, ...]
    remediation: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["severity"] = self.severity.value
        return value


@dataclass(frozen=True)
class ParsedSource:
    kind: str
    files: tuple[ScriptFile, ...]
    wrapper_metadata: Mapping[str, Any]
    raw_sha256: str


@dataclass(frozen=True)
class AuditReport:
    source_kind: str
    status: str
    canonical_target_project_number: str
    observed_project_numbers: tuple[str, ...]
    files: tuple[ScriptFile, ...]
    findings: tuple[Finding, ...]
    integrity: Mapping[str, Any]
    restructure_plan: tuple[str, ...]
    provider_authority_proven: bool = False
    provider_mutation_authorized: bool = False

    @property
    def counts(self) -> dict[str, int]:
        return {
            severity.value: sum(
                finding.severity == severity for finding in self.findings
            )
            for severity in Severity
        }

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": SCHEMA,
            "version": VERSION,
            "source_kind": self.source_kind,
            "status": self.status,
            "canonical_target_project_number": (
                self.canonical_target_project_number
            ),
            "observed_project_numbers": list(self.observed_project_numbers),
            "file_count": len(self.files),
            "files": [
                {
                    "name": item.name,
                    "type": item.file_type,
                    "characters": len(item.source),
                    "source_sha256": item.source_sha256,
                }
                for item in self.files
            ],
            "finding_counts": self.counts,
            "findings": [item.to_dict() for item in self.findings],
            "integrity": dict(self.integrity),
            "restructure_plan": list(self.restructure_plan),
            "provider_authority_proven": self.provider_authority_proven,
            "provider_mutation_authorized": self.provider_mutation_authorized,
            "truth_boundary": (
                "Static source and fleet-structure analysis only. This receipt "
                "does not issue a token, prove a principal, enable an API, "
                "change source, deploy a web app, mutate Google Cloud, or "
                "authorize provider effects."
            ),
        }
        payload["receipt_sha256"] = canonical_sha256(payload)
        return payload


_FUNCTION = re.compile(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(")
_PROJECT_NUMBER = re.compile(r"(?<!\d)(\d{12})(?!\d)")
_AUTH_SUBSTITUTION = re.compile(
    r"(?:approvalKey|gatewayToken|token|authorization)\s*"
    r"(?:[:=]\s*)?[^;\n]{0,100}?\|\|\s*"
    r"(?:CONFIG\.)?(?:APPROVAL_KEY|GATEWAY_TOKEN|TOKEN|AUTHORIZATION)",
    re.IGNORECASE,
)
_HARDCODED_AUTH = re.compile(
    r"(?:APPROVAL_KEY|GATEWAY_TOKEN|AUTHORIZATION_TOKEN)\s*:\s*"
    r"(['\"])(?P<value>[^'\"]+)\1",
    re.IGNORECASE,
)
_QUERY_SECRET = re.compile(
    r"getParam_\s*\(\s*e\s*,\s*['\"](?:key|token|approvalKey)['\"]\s*\)",
    re.IGNORECASE,
)
_PERSIST_APPROVAL = re.compile(
    r"appendRow\s*\(\s*\[[^\]]{0,1800}?"
    r"(?:normalized\.)?(?:approvalKey|gatewayToken|authorization)\b",
    re.IGNORECASE,
)
_GENERIC_2XX = re.compile(
    r"httpStatus\s*>?=\s*200[\s\S]{0,500}?httpStatus\s*<\s*300"
    r"[\s\S]{0,600}?body\.status\s*!==\s*['\"]FAILED['\"]",
    re.IGNORECASE,
)
_SELF_READBACK = re.compile(
    r"\bcommandRowFound\b|\bresultJsonPresent\b|"
    r"\bcompletedAtPresent\b|\breadbackVerified\b",
    re.IGNORECASE,
)
_HMAC = re.compile(
    r"computeHmacSha256Signature|verifySignedRequest|verifySignedEnvelope|\bHMAC\b",
    re.IGNORECASE,
)
_NONCE = re.compile(r"\bnonce\b", re.IGNORECASE)
_TIMESTAMP = re.compile(r"\btimestamp\b|issuedAt|Date\.now\(\)", re.IGNORECASE)
_CACHE_NONCE = re.compile(r"CacheService\.getScriptCache\(\)", re.IGNORECASE)
_DURABLE_NONCE = re.compile(
    r"claimNonce|NONCE_LEDGER|setProperty\([^\n]{0,120}nonce|nonceHash",
    re.IGNORECASE,
)
_IMMEDIATE_RUN = re.compile(
    r"body\.runNow\s*!==\s*false[\s\S]{0,300}?runNowBridge\s*\(",
    re.IGNORECASE,
)
_STATUS_METADATA = re.compile(
    r"projectNumber|spreadsheetUrl|runtimeUrl|capabilities",
    re.IGNORECASE,
)
_GET_BRIDGE_STATUS = re.compile(
    r"return\s+jsonOutput_\s*\(\s*getBridgeStatus\s*\(\s*\)\s*\)",
    re.IGNORECASE,
)
_MUTATION_SURFACE = re.compile(
    r"enableService_|ARCHON_enableRequiredApis|AUTO_ENABLE_APIS|"
    r"AUTO_ENABLE_AND_IGNITE|ARCHON_codeApply|promoteDeployment_|"
    r"updateProjectContent_",
    re.IGNORECASE,
)
_BEARER = re.compile(r"Authorization\s*:\s*['\"]Bearer\s*['\"]\s*\+", re.IGNORECASE)
_MUTABLE_URL = re.compile(r"getProperty\s*\(\s*OMEGA_CONTROL\.URL_PROPERTY\s*\)", re.IGNORECASE)
_HOST_PIN = re.compile(
    r"allowedHosts|ALLOWED_HOST|hostname\s*===|new\s+URL\s*\(|startsWith\s*\(\s*['\"]https://",
    re.IGNORECASE,
)
_NO_REDIRECT = re.compile(r"followRedirects\s*:\s*false", re.IGNORECASE)
_GATEWAY_TOKEN_POLICY = re.compile(r"32\+\s*character|length\s*<\s*32", re.IGNORECASE)
_GATEWAY_TOKEN_RUNTIME = re.compile(
    r"configuredToken\.length\s*<\s*32|suppliedToken\.length\s*<\s*32",
    re.IGNORECASE,
)

CRITICAL_GLOBALS = {
    "doGet",
    "doPost",
    "ARCHON_codeApply",
    "ARCHON_codeRollback",
    "ARCHON_codeStatus",
    "ARCHON_codeDryRun",
}
MUTATOR_GLOBALS = {"ARCHON_codeApply", "ARCHON_codeRollback"}
PRIVILEGED_SCOPES = {
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/script.projects",
    "https://www.googleapis.com/auth/script.deployments",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
}


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _finding(
    code: str,
    severity: Severity,
    message: str,
    files: Iterable[str],
    evidence: Iterable[str],
    remediation: str,
) -> Finding:
    return Finding(
        code=code,
        severity=severity,
        message=message,
        files=tuple(sorted(set(files))),
        evidence=tuple(evidence),
        remediation=remediation,
    )


def _function_body(source: str, name: str) -> str | None:
    match = re.search(
        rf"\bfunction\s+{re.escape(name)}\s*\([^)]*\)\s*\{{",
        source,
    )
    if not match:
        return None
    opening = match.end() - 1
    depth = 0
    quote: str | None = None
    escaped = False
    for cursor in range(opening, len(source)):
        char = source[cursor]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"', "`"}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1 : cursor]
    return None


def _delegated_signed_verifier(
    body: str,
    declarations: Mapping[str, list[str]],
    sources: Mapping[str, str],
) -> bool:
    """Recognize a doPost that immediately delegates to a bundle-local verifier.

    The call graph is deliberately bounded to one hop and only verifier-shaped
    names. This avoids requiring security logic to be duplicated inside the
    global router while still failing closed on an opaque dispatcher.
    """

    for called in re.findall(r"\b([A-Za-z_$][\w$]*)\s*\(", body):
        if not re.search(r"verify|authenticat|authoriz", called, re.I):
            continue
        for location in declarations.get(called, []):
            verifier_body = _function_body(sources[location], called) or ""
            verifier_context = verifier_body + "\n" + sources[location]
            if (
                _HMAC.search(verifier_context)
                and _NONCE.search(verifier_context)
                and _TIMESTAMP.search(verifier_context)
            ):
                return True
    return False


def parse_apps_script_source(source: str) -> ParsedSource:
    if not isinstance(source, str) or not source.strip():
        raise AppsScriptSecurityError("Apps Script source is required")
    normalized = source.lstrip("\ufeff")
    raw_sha256 = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    try:
        parsed = json.loads(normalized)
    except json.JSONDecodeError:
        return ParsedSource(
            kind="RAW_SOURCE",
            files=(ScriptFile("<source>", "SERVER_JS", source),),
            wrapper_metadata={},
            raw_sha256=raw_sha256,
        )

    if isinstance(parsed, Mapping) and isinstance(parsed.get("files"), list):
        files: list[ScriptFile] = []
        for item in parsed["files"]:
            if not isinstance(item, Mapping):
                continue
            files.append(
                ScriptFile(
                    name=str(item.get("name", "")),
                    file_type=str(item.get("type", "")),
                    source=str(item.get("source", "")),
                )
            )
        metadata = {
            key: value for key, value in parsed.items() if key != "files"
        }
        return ParsedSource(
            kind="FLEET_BACKUP_JSON",
            files=tuple(files),
            wrapper_metadata=metadata,
            raw_sha256=raw_sha256,
        )

    if isinstance(parsed, Mapping) and (
        "oauthScopes" in parsed or "webapp" in parsed or "runtimeVersion" in parsed
    ):
        return ParsedSource(
            kind="APPS_SCRIPT_MANIFEST",
            files=(ScriptFile("appsscript", "JSON", normalized),),
            wrapper_metadata={},
            raw_sha256=raw_sha256,
        )

    return ParsedSource(
        kind="JSON_SOURCE",
        files=(ScriptFile("<source>", "JSON", normalized),),
        wrapper_metadata={},
        raw_sha256=raw_sha256,
    )


def _manifest(files: Sequence[ScriptFile]) -> tuple[dict[str, Any], str | None]:
    for item in files:
        if item.name == "appsscript" or item.file_type.upper() == "JSON":
            try:
                value = json.loads(item.source)
            except json.JSONDecodeError:
                return {}, item.name
            if isinstance(value, dict):
                return value, item.name
    return {}, None


def _project_source_hash_candidates(files: Sequence[ScriptFile]) -> set[str]:
    ordered = sorted(files, key=lambda item: (item.name, item.file_type))
    candidates = {
        hashlib.sha256(
            "".join(item.source for item in ordered).encode("utf-8")
        ).hexdigest(),
        canonical_sha256(
            [
                {"name": item.name, "type": item.file_type, "source": item.source}
                for item in ordered
            ]
        ),
        canonical_sha256(
            {item.name: item.source for item in ordered}
        ),
    }
    return candidates

__all__ = [name for name in globals() if not name.startswith('__')]

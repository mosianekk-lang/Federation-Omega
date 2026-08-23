from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Iterable, Mapping


class Severity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"


@dataclass(frozen=True)
class Finding:
    code: str
    severity: Severity
    files: tuple[str, ...]
    evidence: str
    remediation: str

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["severity"] = self.severity.value
        return value


@dataclass(frozen=True)
class FleetResult:
    status: str
    canonical_target_project: str
    observed_project_numbers: tuple[str, ...]
    findings: tuple[Finding, ...]
    provider_authority_proven: bool = False
    provider_mutation_authorized: bool = False

    @property
    def counts(self) -> dict[str, int]:
        return {
            severity.value: sum(f.severity == severity for f in self.findings)
            for severity in Severity
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "canonical_target_project": self.canonical_target_project,
            "observed_project_numbers": list(self.observed_project_numbers),
            "finding_counts": self.counts,
            "findings": [item.to_dict() for item in self.findings],
            "provider_authority_proven": self.provider_authority_proven,
            "provider_mutation_authorized": self.provider_mutation_authorized,
        }


FUNCTION = re.compile(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(")
PROJECT_NUMBER = re.compile(r"(?<!\d)(\d{12})(?!\d)")
CRITICAL_GLOBALS = {
    "doGet", "doPost", "ARCHON_codeApply", "ARCHON_codeRollback",
    "ARCHON_codeStatus", "ARCHON_codeDryRun",
}


def analyze_backup(
    payload: Mapping[str, object],
    *,
    canonical_target_project: str,
    legacy_projects: Iterable[str] = (),
) -> FleetResult:
    raw_files = payload.get("files", [])
    files = {
        str(item.get("name", "")): str(item.get("source", ""))
        for item in raw_files
        if isinstance(item, Mapping)
    }
    findings: list[Finding] = []

    def add(code: str, severity: Severity, names: Iterable[str], evidence: str, remediation: str) -> None:
        findings.append(Finding(code, severity, tuple(sorted(set(names))), evidence, remediation))

    manifest = {}
    try:
        manifest = json.loads(files.get("appsscript", "{}"))
    except json.JSONDecodeError:
        pass
    webapp = manifest.get("webapp", {}) if isinstance(manifest, dict) else {}
    scopes = set(manifest.get("oauthScopes", [])) if isinstance(manifest, dict) else set()
    privileged_scopes = {
        "https://www.googleapis.com/auth/cloud-platform",
        "https://www.googleapis.com/auth/script.projects",
        "https://www.googleapis.com/auth/script.deployments",
    }
    if (
        isinstance(webapp, dict)
        and webapp.get("access") in {"ANYONE", "ANYONE_ANONYMOUS"}
        and webapp.get("executeAs") == "USER_DEPLOYING"
        and scopes.intersection(privileged_scopes)
    ):
        add(
            "PUBLIC_PRIVILEGED_WEBAPP", Severity.CRITICAL, ["appsscript"],
            "Broad web access executes as the deployer with cloud/project/deployment scopes.",
            "Split the privileged admin plane from a minimum-scope authenticated gateway.",
        )

    patterns = [
        ("STATIC_APPROVAL_SECRET", Severity.CRITICAL, r"APPROVAL_KEY\s*:\s*['\"][^'\"]+['\"]", "A fixed approval value is embedded in source.", "Use a rotatable secret only as HMAC key material."),
        ("DEFAULT_APPROVAL_BYPASS", Severity.CRITICAL, r"approvalKey\s*[:=][\s\S]{0,80}?\|\|\s*CONFIG\.APPROVAL_KEY", "Missing caller authentication falls back to approval.", "Reject missing authentication; verify timestamp, nonce, body hash, action and target."),
        ("SECRET_IN_QUERY_PARAMETER", Severity.HIGH, r"getParam_\s*\(\s*e\s*,\s*['\"]key['\"]", "A privileged key can be supplied in a URL query.", "Remove privileged GET actions and use signed POST envelopes."),
        ("APPROVAL_CREDENTIAL_PERSISTED", Severity.CRITICAL, r"appendRow\s*\(\s*\[[\s\S]{0,1600}?normalized\.approvalKey", "Raw approval material is written to the queue sheet.", "Persist only a redacted signature or credential-reference digest."),
        ("GENERIC_TRANSPORT_SUCCESS_PROMOTION", Severity.HIGH, r"httpStatus\s*>?=\s*200[\s\S]{0,500}?body\.status\s*!==\s*['\"]FAILED", "Generic 2xx transport can be promoted to DONE.", "Require an action-specific semantic verifier and downstream state delta."),
        ("SELF_READBACK_ONLY", Severity.HIGH, r"commandRowFound|resultJsonPresent|completedAtPresent|readbackVerified", "Completion primarily proves the bridge rewrote its own row.", "Separate transport receipt from independent provider-semantic readback."),
    ]
    for code, severity, pattern, evidence, remediation in patterns:
        matched = [name for name, source in files.items() if re.search(pattern, source)]
        if matched:
            add(code, severity, matched, evidence, remediation)

    declarations: dict[str, list[str]] = defaultdict(list)
    for name, source in files.items():
        for symbol in FUNCTION.findall(source):
            declarations[symbol].append(name)
    for symbol, locations in sorted(declarations.items()):
        if len(locations) > 1 and symbol in CRITICAL_GLOBALS:
            add(
                "DUPLICATE_GLOBAL_HANDLER", Severity.CRITICAL, locations,
                f"{symbol} is declared {len(locations)} times in the Apps Script global namespace.",
                "Expose one global router and namespace every internal/mutating handler.",
            )

    for symbol in ("ARCHON_codeApply", "ARCHON_codeRollback"):
        locations = declarations.get(symbol, [])
        if len(locations) > 1:
            strengths = [
                bool(re.search(r"verifySignedRequest|computeHmacSha256Signature", files[name]))
                for name in locations
            ]
            if any(strengths) and not all(strengths):
                add(
                    "MIXED_AUTH_MUTATOR_SHADOWING", Severity.CRITICAL, locations,
                    f"Duplicate {symbol} implementations have unequal authentication strength.",
                    "Quarantine the weaker mutator and retain one signed, backup-first transaction engine.",
                )

    gateway_files = [name for name, source in files.items() if "OMEGA_GATEWAY_TOKEN" in source]
    if gateway_files and not any(re.search(r"Token\.length\s*<\s*32|token\.length\s*<\s*32", files[name]) for name in gateway_files):
        add(
            "TOKEN_STRENGTH_NOT_ENFORCED", Severity.MEDIUM, gateway_files,
            "The documented 32-character token minimum is not enforced at runtime.",
            "Enforce the minimum or replace bearer equality with signed request envelopes.",
        )

    bearer_files = [
        name for name, source in files.items()
        if "OMEGA_CONTROL.URL_PROPERTY" in source and "Authorization: 'Bearer '" in source
        and "startsWith('https://" not in source and "new URL(" not in source
    ]
    if bearer_files:
        add(
            "CONFIGURABLE_BEARER_DESTINATION", Severity.HIGH, bearer_files,
            "A bearer token is sent to a property-controlled URL without strict host pinning.",
            "Require HTTPS, pin an allowed host/service identity and reject redirects before adding credentials.",
        )

    observed = set()
    for source in files.values():
        observed.update(PROJECT_NUMBER.findall(source))
    legacy_seen = observed.intersection(set(legacy_projects))
    mutation_surface = any(
        re.search(r"enableService_|ARCHON_enableRequiredApis|AUTO_ENABLE_APIS|ARCHON_codeApply", source)
        for source in files.values()
    )
    if legacy_seen and mutation_surface:
        add(
            "LEGACY_PROJECT_MUTATION_DEFAULT", Severity.CRITICAL, files.keys(),
            f"Effectful routes coexist with legacy project default(s): {sorted(legacy_seen)}.",
            "Keep legacy lineages transport-only and require exact target/consumer/principal proof before mutation.",
        )

    critical = sum(item.severity == Severity.CRITICAL for item in findings)
    high = sum(item.severity == Severity.HIGH for item in findings)
    status = "SECURITY_HOLD" if critical else "HARDENING_REQUIRED" if high else "SOURCE_REVIEW_PASS"
    return FleetResult(
        status=status,
        canonical_target_project=canonical_target_project,
        observed_project_numbers=tuple(sorted(observed)),
        findings=tuple(findings),
    )

#!/usr/bin/env python3
"""Bundle-aware, fail-closed Google Apps Script authorization gate.

Implementation primitives live in ``apps_script_authorization_model`` so the
scanner and receipt model remain independently testable. This compatibility
module retains the original public import and CLI surface.
"""

from __future__ import annotations

from ops.apps_script_authorization_model import *  # noqa: F401,F403


def audit_apps_script_source(
    source: str,
    *,
    canonical_project_number: str = DEFAULT_CANONICAL_PROJECT_NUMBER,
    legacy_project_numbers: Iterable[str] = DEFAULT_LEGACY_PROJECT_NUMBERS,
) -> dict[str, Any]:
    parsed = parse_apps_script_source(source)
    files = parsed.files
    sources = {item.name: item.source for item in files}
    findings: list[Finding] = []
    legacy = {str(item) for item in legacy_project_numbers}

    manifest, manifest_name = _manifest(files)
    webapp = manifest.get("webapp", {}) if isinstance(manifest, dict) else {}
    scopes_raw = manifest.get("oauthScopes", []) if isinstance(manifest, dict) else []
    scopes = set(scopes_raw) if isinstance(scopes_raw, list) else set()
    access = str(webapp.get("access", "")) if isinstance(webapp, Mapping) else ""
    execute_as = str(webapp.get("executeAs", "")) if isinstance(webapp, Mapping) else ""
    public_webapp = access in {"ANYONE", "ANYONE_ANONYMOUS"}
    public_privileged = (
        public_webapp
        and execute_as == "USER_DEPLOYING"
        and bool(scopes.intersection(PRIVILEGED_SCOPES))
    )
    if public_privileged:
        findings.append(
            _finding(
                "PUBLIC_PRIVILEGED_WEBAPP",
                Severity.CRITICAL,
                "A broadly reachable web app executes as the deployer while holding cloud, source, deployment, Drive or Sheets authority.",
                [manifest_name or "appsscript"],
                [f"webapp.access={access}", f"webapp.executeAs={execute_as}"],
                "Split privileged administration from public ingress. Keep broad scopes in an owner-only admin project and use a minimum-scope signed gateway separately.",
            )
        )

    declarations: dict[str, list[str]] = defaultdict(list)
    observed_numbers: set[str] = set()
    do_post_profiles: list[tuple[str, str]] = []
    for name, text in sources.items():
        observed_numbers.update(_PROJECT_NUMBER.findall(text))
        for symbol in _FUNCTION.findall(text):
            declarations[symbol].append(name)
        body = _function_body(text, "doPost")
        if body is not None:
            do_post_profiles.append((name, body))

    if not public_webapp:
        inline_public = any(
            re.search(r"['\"]access['\"]\s*:\s*['\"]ANYONE['\"]", text, re.I)
            for text in sources.values()
        )
        public_webapp = inline_public

    for name, text in sources.items():
        if _HARDCODED_AUTH.search(text):
            findings.append(
                _finding(
                    "STATIC_APPROVAL_SECRET",
                    Severity.CRITICAL,
                    "A fixed approval value is embedded in source.",
                    [name],
                    ["non-empty source literal assigned to an approval/token constant"],
                    "Remove the literal. Use a rotatable property only as HMAC key material; never accept the key itself as an approval decision.",
                )
            )
        if _AUTH_SUBSTITUTION.search(text):
            findings.append(
                _finding(
                    "DEFAULT_APPROVAL_BYPASS",
                    Severity.CRITICAL,
                    "Missing caller authentication falls back to a configured approval value.",
                    [name],
                    ["caller-supplied authentication uses || configured approval"],
                    "Reject absent authentication and verify an unchanged signed envelope bound to action, target, body hash, timestamp and nonce.",
                )
            )
        if _QUERY_SECRET.search(text):
            findings.append(
                _finding(
                    "SECRET_IN_QUERY_PARAMETER",
                    Severity.HIGH,
                    "A privileged credential can be supplied in a URL query parameter.",
                    [name],
                    ["GET parameter named key/token/approvalKey"],
                    "Remove privileged GET actions. Use signed POST envelopes and never place credentials in URLs.",
                )
            )
        if _PERSIST_APPROVAL.search(text):
            findings.append(
                _finding(
                    "APPROVAL_CREDENTIAL_PERSISTED",
                    Severity.CRITICAL,
                    "Authentication material is written into the command spreadsheet.",
                    [name],
                    ["approval/token field appended into a queue row"],
                    "Persist only a credential-reference or signature digest. Reverify the request before execution and discard raw authentication material.",
                )
            )
        if _GENERIC_2XX.search(text):
            findings.append(
                _finding(
                    "GENERIC_TRANSPORT_SUCCESS_PROMOTION",
                    Severity.HIGH,
                    "A generic HTTP 2xx and non-failure string can be promoted to DONE without action-specific semantic proof.",
                    [name],
                    ["2xx + status not FAILED => success"],
                    "Define a semantic verifier per action and require expected target identity plus observed state delta before completion.",
                )
            )
        if _SELF_READBACK.search(text):
            findings.append(
                _finding(
                    "SELF_READBACK_ONLY",
                    Severity.HIGH,
                    "Completion proof primarily verifies that the bridge rewrote its own row.",
                    [name],
                    ["row/result/completedAt presence treated as completion proof"],
                    "Keep transport and provider-semantic receipts separate; require independent downstream readback for external actions.",
                )
            )
        if _MUTABLE_URL.search(text) and _BEARER.search(text):
            if not _HOST_PIN.search(text) or not _NO_REDIRECT.search(text):
                findings.append(
                    _finding(
                        "CONFIGURABLE_BEARER_DESTINATION",
                        Severity.HIGH,
                        "A bearer credential is attached to a property-controlled URL without both strict host pinning and redirect rejection.",
                        [name],
                        ["OMEGA_URL property + Authorization: Bearer"],
                        "Require HTTPS, pin allowed hostname/service identity, reject redirects, and attach credentials only after URL validation.",
                    )
                )
        if _GATEWAY_TOKEN_POLICY.search(text) and "OMEGA_GATEWAY_TOKEN" in text:
            if not _GATEWAY_TOKEN_RUNTIME.search(text):
                findings.append(
                    _finding(
                        "TOKEN_STRENGTH_NOT_ENFORCED",
                        Severity.MEDIUM,
                        "The documented gateway-token minimum is not enforced at runtime.",
                        [name],
                        ["token length policy appears only in documentation/comments"],
                        "Enforce minimum strength and rotation metadata, or replace bearer equality with signed request envelopes.",
                    )
                )
        if _CACHE_NONCE.search(text) and _HMAC.search(text) and not _DURABLE_NONCE.search(text):
            findings.append(
                _finding(
                    "EPHEMERAL_NONCE_REPLAY_STORE",
                    Severity.MEDIUM,
                    "A mutation signature relies on an evictable cache as its replay ledger.",
                    [name],
                    ["CacheService nonce marker without durable nonce claim"],
                    "Claim nonce hashes atomically in bounded durable state, prune by expiry, and keep CacheService only as an accelerator.",
                )
            )

    if public_webapp:
        for name, body in do_post_profiles:
            signed = bool(
                (_HMAC.search(body) and _NONCE.search(body) and _TIMESTAMP.search(body))
                or _delegated_signed_verifier(body, declarations, sources)
            )
            if not signed:
                findings.append(
                    _finding(
                        "PUBLIC_UNSIGNED_POST",
                        Severity.CRITICAL,
                        "A public doPost entry does not directly prove HMAC, timestamp and nonce verification before dispatch.",
                        [name, manifest_name or "appsscript"],
                        ["public webapp + doPost without signed-envelope markers"],
                        "Verify the signed envelope inside the entry path before parsing privileged dispatch fields; fail closed on missing, stale or replayed requests.",
                    )
                )
            if _IMMEDIATE_RUN.search(body):
                findings.append(
                    _finding(
                        "PUBLIC_POST_IMMEDIATE_EXECUTION",
                        Severity.CRITICAL,
                        "The public request path can enqueue and immediately process a command in the same call.",
                        [name],
                        ["runNow defaults to execution unless explicitly false"],
                        "Separate authenticated admission from execution. Queue a digest-bound command and let a private worker reverify it before any effect.",
                    )
                )
        for name, text in sources.items():
            if _GET_BRIDGE_STATUS.search(text) and _STATUS_METADATA.search(text):
                findings.append(
                    _finding(
                        "PUBLIC_STATUS_METADATA_EXPOSURE",
                        Severity.HIGH,
                        "The unauthenticated status path can expose internal project, runtime, spreadsheet or capability metadata.",
                        [name],
                        ["default doGet -> getBridgeStatus with internal identifiers"],
                        "Return only a minimal liveness response publicly; require authenticated read scope for internal identifiers and inventory.",
                    )
                )

    combined_source = "\n".join(sources.values())
    if re.search(r"assertProviderMutationPermit", combined_source, re.I):
        required_binding_markers = {
            "transactionId",
            "requestSha256",
            "expectedBeforeHash",
            "expectedAfterHash",
            "oneUse",
        }
        missing_markers = sorted(
            marker
            for marker in required_binding_markers
            if marker not in combined_source
        )
        if missing_markers:
            findings.append(
                _finding(
                    "INCOMPLETE_EFFECT_PERMIT_BINDING",
                    Severity.CRITICAL,
                    "The provider/effect admission does not bind every mutation to the exact transaction, request and before/after source hashes.",
                    sources.keys(),
                    ["missing markers: " + ", ".join(missing_markers)],
                    "Bind the permit and provider receipt to transactionId, canonical mutation-intent hash, expected before/after hashes and an explicit one-use flag.",
                )
            )
        if not re.search(r"claimEffectPermit", combined_source, re.I):
            findings.append(
                _finding(
                    "EFFECT_PERMIT_REPLAY_UNGUARDED",
                    Severity.CRITICAL,
                    "An accepted effect permit is not durably claimed as one-use immediately before mutation.",
                    sources.keys(),
                    ["provider mutation admission without a durable permit claim"],
                    "Atomically consume a permit hash in bounded durable state immediately before the first provider mutation.",
                )
            )

    same_project_anchor = re.search(
        r"(?:PROVIDER_RECEIPT|EFFECT_PERMIT).*ANCHOR.*PROPERTY",
        combined_source,
        re.I,
    ) and re.search(r"PropertiesService\.getScriptProperties", combined_source)
    external_verifier = re.search(r"EXTERNAL_ADMISSION|ADMISSION_VERIFIER", combined_source, re.I)
    if same_project_anchor and not external_verifier:
        findings.append(
            _finding(
                "SAME_PROJECT_AUTHORITY_ANCHOR",
                Severity.HIGH,
                "Provider and effect receipts are called externally anchored but are trusted only through mutable properties in the same privileged project.",
                sources.keys(),
                ["same-project Script Property used as provider/effect authority anchor"],
                "Verify stable evidence references through an independently operated, pinned HTTPS verifier and require a challenge-bound response.",
            )
        )

    if external_verifier:
        verifier_hardened = bool(
            re.search(r"followRedirects\s*:\s*false", combined_source, re.I)
            and re.search(r"HOST_MISMATCH|expectedHost|VERIFIER_HOST", combined_source, re.I)
            and re.search(r"challenge", combined_source, re.I)
        )
        if not verifier_hardened:
            findings.append(
                _finding(
                    "EXTERNAL_VERIFIER_NOT_PINNED",
                    Severity.HIGH,
                    "An external admission verifier is referenced without complete host, redirect and challenge binding.",
                    sources.keys(),
                    ["external verifier present without pinned-host/no-redirect/challenge controls"],
                    "Require HTTPS host pinning, redirect rejection, one-time challenge echo and exact receipt/permit/request hash binding.",
                )
            )

    for symbol, locations in sorted(declarations.items()):
        if len(locations) <= 1:
            continue
        if symbol in CRITICAL_GLOBALS:
            findings.append(
                _finding(
                    "DUPLICATE_GLOBAL_HANDLER",
                    Severity.CRITICAL,
                    f"Global Apps Script symbol {symbol} is declared in multiple files.",
                    locations,
                    [f"{symbol} declared {len(locations)} times"],
                    "Expose one global router per Apps Script project and namespace all internal handlers.",
                )
            )

    for symbol in MUTATOR_GLOBALS:
        locations = declarations.get(symbol, [])
        if len(locations) <= 1:
            continue
        profiles = []
        for location in locations:
            body = _function_body(sources[location], symbol) or ""
            strong = bool(_HMAC.search(body) and _NONCE.search(sources[location]))
            profiles.append((location, strong))
        if any(strong for _, strong in profiles) and any(
            not strong for _, strong in profiles
        ):
            findings.append(
                _finding(
                    "MIXED_AUTH_MUTATOR_SHADOWING",
                    Severity.CRITICAL,
                    f"Duplicate {symbol} implementations use unequal authentication strength.",
                    [location for location, _ in profiles],
                    [f"{location}: signed={strong}" for location, strong in profiles],
                    "Quarantine the weaker mutator and retain one signed, backup-first, hash-readback transaction engine under a unique namespace.",
                )
            )

    legacy_seen = sorted(observed_numbers.intersection(legacy))
    mutation_files = [
        name for name, text in sources.items() if _MUTATION_SURFACE.search(text)
    ]
    legacy_default_files: list[str] = []
    legacy_defaults: list[str] = []
    for number in legacy_seen:
        binding = re.compile(
            rf"\b(?:CLOUD_PROJECT_NUMBER|TARGET_PROJECT_NUMBER|PROJECT_NUMBER)\b"
            rf"\s*[:=]\s*['\"]{re.escape(number)}['\"]",
            re.IGNORECASE,
        )
        for name, text in sources.items():
            if binding.search(text):
                legacy_default_files.append(name)
                legacy_defaults.append(number)
    if legacy_default_files and mutation_files:
        findings.append(
            _finding(
                "LEGACY_PROJECT_MUTATION_DEFAULT",
                Severity.CRITICAL,
                "Effectful API/source/deployment routes use a legacy transport or blocked consumer project as a default target.",
                sorted(set(mutation_files + legacy_default_files)),
                [
                    f"legacy_or_consumer_default={number}"
                    for number in sorted(set(legacy_defaults))
                ],
                "Keep those lineages transport/consumer-only. Require exact target, consumer, token, principal and semantic readback proof before canonical mutation.",
            )
        )

    deduplicated: list[Finding] = []
    seen_keys: set[tuple[str, tuple[str, ...], tuple[str, ...]]] = set()
    for finding in findings:
        key = (finding.code, finding.files, finding.evidence)
        if key not in seen_keys:
            seen_keys.add(key)
            deduplicated.append(finding)

    severity_rank = {
        Severity.CRITICAL: 0,
        Severity.HIGH: 1,
        Severity.MEDIUM: 2,
        Severity.INFO: 3,
    }
    deduplicated.sort(
        key=lambda item: (severity_rank[item.severity], item.code, item.files)
    )
    critical = sum(item.severity == Severity.CRITICAL for item in deduplicated)
    high = sum(item.severity == Severity.HIGH for item in deduplicated)
    status = (
        "SECURITY_HOLD"
        if critical
        else "HARDENING_REQUIRED"
        if high
        else "SOURCE_REVIEW_PASS"
    )

    declared_hash = parsed.wrapper_metadata.get("sourceSha256")
    candidate_hashes = _project_source_hash_candidates(files)
    integrity = {
        "raw_input_sha256": parsed.raw_sha256,
        "declared_source_sha256": declared_hash,
        "declared_matches_raw_input": declared_hash == parsed.raw_sha256,
        "declared_matches_supported_project_canonicalization": (
            declared_hash in candidate_hashes if isinstance(declared_hash, str) else None
        ),
        "declared_hash_verification_state": (
            "VERIFIED_BY_SUPPORTED_CANONICALIZATION"
            if isinstance(declared_hash, str) and declared_hash in candidate_hashes
            else "ALGORITHM_UNSPECIFIED_UNVERIFIED"
            if declared_hash
            else "NOT_DECLARED"
        ),
        "note": (
            "A non-match does not prove corruption because the producing hash "
            "algorithm/canonicalization is not included in the supplied backup."
        ),
    }

    plan = (
        "Preserve the supplied backup unchanged as the rollback/evidence anchor.",
        "Split minimum-scope signed ingress from the owner-only privileged admin plane.",
        "Expose exactly one doGet/doPost router per project and namespace every internal function.",
        "Replace static/default approvals with HMAC(action + target + body hash + timestamp + nonce); reject missing auth and replay.",
        "Remove raw approval/token material from Sheets, logs and receipts; retain only hashes and opaque references.",
        "Separate canonical target, OAuth consumer and legacy transport lineages; no authority inheritance.",
        "Retain one signed, backup-first code manager and rename/quarantine weaker duplicate mutators.",
        "Require action-specific provider-semantic readback and rollback before any effect is promoted to DONE.",
    )
    report = AuditReport(
        source_kind=parsed.kind,
        status=status,
        canonical_target_project_number=str(canonical_project_number),
        observed_project_numbers=tuple(sorted(observed_numbers)),
        files=files,
        findings=tuple(deduplicated),
        integrity=integrity,
        restructure_plan=plan,
    )
    return report.to_dict()


def validate_apps_script_source(source: str) -> str:
    """Backward-compatible gate used by existing Airlock tests and callers."""

    report = audit_apps_script_source(source)
    blocking = [
        item
        for item in report["findings"]
        if item["severity"] in {Severity.CRITICAL.value, Severity.HIGH.value}
    ]
    if blocking:
        codes = {item["code"] for item in blocking}
        if "DEFAULT_APPROVAL_BYPASS" in codes:
            message = (
                "Caller authorization must not fall back to a configured "
                "approval value"
            )
        elif "STATIC_APPROVAL_SECRET" in codes:
            message = (
                "Authorization material must not be hardcoded in Apps Script source"
            )
        elif codes.intersection({"PUBLIC_PRIVILEGED_WEBAPP", "PUBLIC_UNSIGNED_POST"}):
            message = (
                "Privileged doPost handler must not use public ANYONE web-app access"
            )
        else:
            message = (
                "Apps Script authorization gate blocked source: "
                + ", ".join(sorted(codes)[:8])
            )
        raise AppsScriptSecurityError(message)
    return source


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Apps Script source or fleet backup JSON")
    parser.add_argument("--json", action="store_true", help="print audit receipt")
    parser.add_argument(
        "--canonical-project-number",
        default=DEFAULT_CANONICAL_PROJECT_NUMBER,
    )
    parser.add_argument(
        "--legacy-project-number",
        action="append",
        dest="legacy_projects",
        default=None,
    )
    args = parser.parse_args()

    text = Path(args.source).read_text(encoding="utf-8")
    report = audit_apps_script_source(
        text,
        canonical_project_number=args.canonical_project_number,
        legacy_project_numbers=(
            args.legacy_projects
            if args.legacy_projects is not None
            else DEFAULT_LEGACY_PROJECT_NUMBERS
        ),
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["status"] == "SOURCE_REVIEW_PASS" else 1
    validate_apps_script_source(text)
    print("APPS_SCRIPT_AUTHORIZATION_SOURCE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

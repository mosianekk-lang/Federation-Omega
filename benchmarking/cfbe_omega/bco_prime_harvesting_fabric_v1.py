"""Authorized, provenance-preserving BCO-Prime capability harvesting fabric.

The fabric scans only a configured local root.  It emits structured metadata,
never raw harvested content, and keeps generated candidates quarantined for
shadow qualification.  It has no network or provider executor.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA = "BCO_PRIME_HARVESTING_FABRIC_V1"
VERSION = "1.0.0"
DEFAULT_MAX_FILE_BYTES = 1024 * 1024
DEFAULT_MAX_FILES = 1000
ALLOWED_SUFFIXES = frozenset({".py", ".json", ".jsonl", ".md", ".txt", ".csv"})
COMPATIBLE_LICENSES = frozenset({"MIT", "Apache-2.0", "BSD-3-Clause", "Proprietary-Authorized"})
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|token|password|secret)\s*([:=])\s*([\"']?)([^\s,;\"']{4,})([\"']?)"
)
_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL)
_SPDX = re.compile(r"SPDX-License-Identifier:\s*([A-Za-z0-9.\-+]+)")
_FORBIDDEN_EFFECT_KEYS = {
    "external_effect",
    "provider_effect",
    "provider_effect_authorized",
    "authority_expansion",
    "network",
    "path_escape",
    "host_execution",
}
_NORMALIZED_FORBIDDEN_EFFECT_KEYS = {
    re.sub(r"[^a-z0-9]", "", key.lower()) for key in _FORBIDDEN_EFFECT_KEYS
}


class HarvestContractError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise HarvestContractError(f"invalid {field}")
    return value


def _safe_relative(root: Path, path: Path) -> tuple[Path, str]:
    if path.is_symlink():
        raise HarvestContractError("symbolic links are not harvestable")
    resolved_root = root.resolve()
    resolved = path.resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise HarvestContractError("path traversal rejected")
    return resolved, resolved.relative_to(resolved_root).as_posix()


def redact_secrets(text: str) -> tuple[str, int]:
    count = 0

    def replace_assignment(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return f"{match.group(1)}{match.group(2)}[REDACTED]"

    redacted = _SECRET_ASSIGNMENT.sub(replace_assignment, text)
    private_keys = len(_PRIVATE_KEY.findall(redacted))
    if private_keys:
        count += private_keys
        redacted = _PRIVATE_KEY.sub("[REDACTED_PRIVATE_KEY]", redacted)
    return redacted, count


def detect_license(text: str) -> dict[str, Any]:
    match = _SPDX.search(text[:16384])
    identifier = match.group(1) if match else "UNKNOWN"
    if identifier == "UNKNOWN":
        lowered = text[:16384].lower()
        if "permission is hereby granted, free of charge" in lowered:
            identifier = "MIT"
        elif "apache license" in lowered and "version 2.0" in lowered:
            identifier = "Apache-2.0"
    compatible = identifier in COMPATIBLE_LICENSES
    return {
        "identifier": identifier,
        "status": "COMPATIBLE" if compatible else "UNKNOWN_OR_INCOMPATIBLE",
        "compatible": compatible,
    }


@dataclass(frozen=True)
class CapabilityDNA:
    dna_id: str
    symbol: str
    purpose: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    algorithm_pattern: str
    dependencies: tuple[str, ...]
    controls: tuple[str, ...]
    proof: tuple[str, ...]
    failure_modes: tuple[str, ...]
    portability: str
    provenance: Mapping[str, Any]
    license: Mapping[str, Any]
    content_id: str
    occurrence_id: str
    confidence: float
    integration_bindings: tuple[str, ...]
    authority_state: str
    quarantine_state: str


def _python_symbols(text: str, relative: str) -> tuple[list[dict[str, Any]], tuple[str, ...]]:
    try:
        tree = ast.parse(text, filename=relative)
    except SyntaxError as exc:
        raise HarvestContractError(f"malformed Python: {relative}:{exc.lineno}") from exc
    dependencies: set[str] = set()
    symbols: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            dependencies.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            dependencies.add(node.module)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            args = tuple(arg.arg for arg in node.args.args)
            outputs = (ast.unparse(node.returns),) if node.returns is not None else ()
            symbols.append({"symbol": node.name, "inputs": args, "outputs": outputs, "kind": "function"})
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            symbols.append({"symbol": node.name, "inputs": (), "outputs": (), "kind": "class"})
    if not symbols:
        symbols.append({"symbol": Path(relative).stem, "inputs": (), "outputs": (), "kind": "module"})
    return symbols[:100], tuple(sorted(dependencies))


def _generic_symbols(text: str, relative: str, suffix: str) -> list[dict[str, Any]]:
    if suffix == ".json":
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise HarvestContractError(f"malformed JSON: {relative}") from exc
        keys = sorted(value)[:50] if isinstance(value, dict) else []
        return [{"symbol": key, "inputs": (), "outputs": (), "kind": "schema-key"} for key in keys] or [
            {"symbol": Path(relative).stem, "inputs": (), "outputs": (), "kind": "json-artifact"}
        ]
    if suffix == ".jsonl":
        for index, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                raise HarvestContractError(f"malformed JSONL: {relative}:{index}") from exc
        return [{"symbol": Path(relative).stem, "inputs": (), "outputs": (), "kind": "jsonl-ledger"}]
    if suffix == ".md":
        headings = [line.lstrip("#").strip() for line in text.splitlines() if line.startswith("#")]
        return [
            {"symbol": heading[:120], "inputs": (), "outputs": (), "kind": "document-section"}
            for heading in headings[:50]
        ] or [{"symbol": Path(relative).stem, "inputs": (), "outputs": (), "kind": "document"}]
    return [{"symbol": Path(relative).stem, "inputs": (), "outputs": (), "kind": "artifact"}]


def _pattern(symbol: str, kind: str, relative: str) -> str:
    lowered = f"{symbol} {relative}".lower()
    if "test" in lowered:
        return "TEST_OR_BENCHMARK"
    if any(word in lowered for word in ("validate", "verify", "gate", "guard")):
        return "VALIDATION_OR_GOVERNANCE"
    if any(word in lowered for word in ("retry", "recover", "rollback", "checkpoint")):
        return "RESILIENCE_OR_RECOVERY"
    if any(word in lowered for word in ("audit", "evidence", "forensic")):
        return "EVIDENCE_ANALYSIS"
    return kind.upper().replace("-", "_")


def _controls(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    controls = [
        label
        for label, indicators in {
            "AUTHORITY_GATE": ("authority", "permission"),
            "HASH_INTEGRITY": ("sha256", "hash"),
            "RETRY_CONTROL": ("retry", "backoff"),
            "ROLLBACK": ("rollback", "restore"),
            "REDACTION": ("redact", "secret"),
            "TEST_PROOF": ("unittest", "pytest", "assert"),
        }.items()
        if any(indicator in lowered for indicator in indicators)
    ]
    return tuple(sorted(controls))


class CapabilityRadar:
    def __init__(
        self,
        root: Path,
        authorized_source_ids: Iterable[str],
        *,
        max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
        max_files: int = DEFAULT_MAX_FILES,
        allowed_suffixes: Iterable[str] = ALLOWED_SUFFIXES,
    ) -> None:
        self.root = root.resolve()
        if not self.root.is_dir():
            raise HarvestContractError("radar root must be an existing directory")
        self.authorized_source_ids = frozenset(_identifier(item, "source_id") for item in authorized_source_ids)
        if not isinstance(max_file_bytes, int) or not 1 <= max_file_bytes <= 16 * 1024 * 1024:
            raise HarvestContractError("invalid max_file_bytes")
        if not isinstance(max_files, int) or not 1 <= max_files <= 100_000:
            raise HarvestContractError("invalid max_files")
        self.max_file_bytes = max_file_bytes
        self.max_files = max_files
        self.allowed_suffixes = frozenset(allowed_suffixes)

    def scan(self, source_id: str, tenant_id: str, matter_id: str) -> dict[str, Any]:
        source_id = _identifier(source_id, "source_id")
        tenant_id = _identifier(tenant_id, "tenant_id")
        matter_id = _identifier(matter_id, "matter_id")
        if source_id not in self.authorized_source_ids:
            raise HarvestContractError("source authority denied")
        candidates = sorted(path for path in self.root.rglob("*") if path.is_file() or path.is_symlink())
        if len(candidates) > self.max_files:
            raise HarvestContractError("file count limit exceeded")
        records: list[dict[str, Any]] = []
        rejects: list[dict[str, str]] = []
        occurrence_by_content: dict[str, set[str]] = {}
        for path in candidates:
            try:
                resolved, relative = _safe_relative(self.root, path)
                suffix = resolved.suffix.lower()
                if suffix not in self.allowed_suffixes:
                    raise HarvestContractError(f"unsupported file type: {suffix or '<none>'}")
                size = resolved.stat().st_size
                if size > self.max_file_bytes:
                    raise HarvestContractError("file size limit exceeded")
                raw = resolved.read_bytes()
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise HarvestContractError("non-UTF-8 input rejected") from exc
                redacted, secret_count = redact_secrets(text)
                content_id = hashlib.sha256(redacted.encode("utf-8")).hexdigest()
                occurrence_id = digest(
                    {"source_id": source_id, "tenant_id": tenant_id, "matter_id": matter_id, "relative_path": relative}
                )
                license_info = detect_license(redacted)
                if suffix == ".py":
                    symbols, dependencies = _python_symbols(redacted, relative)
                else:
                    symbols = _generic_symbols(redacted, relative, suffix)
                    dependencies = ()
                controls = _controls(redacted)
                portability = "PYTHON_STDLIB" if suffix == ".py" and all(dep.split(".")[0] in sys.stdlib_module_names for dep in dependencies) else "SOURCE_BOUND"
                for symbol in symbols:
                    dna_id = digest({"occurrence_id": occurrence_id, "symbol": symbol["symbol"], "kind": symbol["kind"]})
                    record = CapabilityDNA(
                        dna_id=dna_id,
                        symbol=symbol["symbol"],
                        purpose=f"Harvested {symbol['kind']} candidate from {relative}",
                        inputs=tuple(symbol["inputs"]),
                        outputs=tuple(symbol["outputs"]),
                        algorithm_pattern=_pattern(symbol["symbol"], symbol["kind"], relative),
                        dependencies=dependencies,
                        controls=controls,
                        proof=(f"content-sha256:{content_id}", f"secret-redactions:{secret_count}"),
                        failure_modes=("SOURCE_CHANGE", "DEPENDENCY_ABSENCE", "LICENCE_INCOMPATIBILITY"),
                        portability=portability,
                        provenance={
                            "source_id": source_id,
                            "tenant_id": tenant_id,
                            "matter_id": matter_id,
                            "relative_path": relative,
                            "size_bytes": size,
                        },
                        license=license_info,
                        content_id=content_id,
                        occurrence_id=occurrence_id,
                        confidence=0.9 if suffix in {".py", ".json", ".jsonl"} else 0.75,
                        integration_bindings=(f"{relative}:{symbol['symbol']}",),
                        authority_state="AUTHORIZED",
                        quarantine_state="SHADOW_ONLY" if license_info["compatible"] else "LICENCE_HOLD",
                    )
                    records.append(asdict(record))
                occurrence_by_content.setdefault(content_id, set()).add(occurrence_id)
            except (OSError, HarvestContractError) as exc:
                relative = path.relative_to(self.root).as_posix() if self.root in path.resolve(strict=False).parents else path.name
                rejects.append({"relative_path": relative, "reason": str(exc)})
        duplicate_contents = sorted(content for content, occurrences in occurrence_by_content.items() if len(occurrences) > 1)
        result = {
            "schema": "BCO_PRIME_CAPABILITY_RADAR_RESULT_V1",
            "source_id": source_id,
            "tenant_id": tenant_id,
            "matter_id": matter_id,
            "record_count": len(records),
            "occurrence_count": sum(len(items) for items in occurrence_by_content.values()),
            "unique_content_count": len(occurrence_by_content),
            "duplicate_content_ids": duplicate_contents,
            "records": sorted(records, key=lambda item: item["dna_id"]),
            "rejects": rejects,
            "raw_content_emitted": False,
            "providerEffectAuthorized": False,
            "manualUserTasks": [],
            "ownerActionRequired": False,
        }
        result["result_sha256"] = digest(result)
        return result


def build_opportunity_graph(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    symbol_to_id: dict[str, str] = {}
    for raw in records:
        dna_id = str(raw.get("dna_id", ""))
        if not re.fullmatch(r"[0-9a-f]{64}", dna_id):
            raise HarvestContractError("invalid dna_id")
        if dna_id in nodes:
            raise HarvestContractError("duplicate dna_id")
        symbol = str(raw.get("symbol", ""))
        symbol_to_id[symbol] = dna_id
        license_info = raw.get("license", {})
        controls = raw.get("controls", [])
        value = min(1.0, 0.35 + 0.05 * len(controls) + 0.2 * float(raw.get("confidence", 0)))
        risk = 0.2 if license_info.get("compatible") else 0.9
        nodes[dna_id] = {
            "dna_id": dna_id,
            "symbol": symbol,
            "value": round(value, 4),
            "risk": risk,
            "reversible": True,
            "authority_state": raw.get("authority_state"),
            "license": license_info,
            "dependencies": list(raw.get("dependencies", [])),
            "content_id": raw.get("content_id"),
        }
    edges: list[dict[str, str]] = []
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in nodes}
    for node_id, node in nodes.items():
        for dependency in node["dependencies"]:
            target = symbol_to_id.get(str(dependency))
            if target and target != node_id:
                adjacency[node_id].add(target)
                edges.append({"from": node_id, "to": target, "type": "DEPENDS_ON"})
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise HarvestContractError("dependency cycle detected")
        if node_id in visited:
            return
        visiting.add(node_id)
        for target in sorted(adjacency[node_id]):
            visit(target)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in sorted(nodes):
        visit(node_id)
    ranked = sorted(nodes.values(), key=lambda item: (-(item["value"] - item["risk"]), item["dna_id"]))
    result = {
        "schema": "BCO_PRIME_OPPORTUNITY_GRAPH_V1",
        "nodes": [nodes[key] for key in sorted(nodes)],
        "edges": sorted(edges, key=lambda item: (item["from"], item["to"])),
        "ranked_candidates": [item["dna_id"] for item in ranked],
        "acyclic": True,
        "manualUserTasks": [],
        "ownerActionRequired": False,
    }
    result["graph_sha256"] = digest(result)
    return result


def compile_candidate(graph: Mapping[str, Any], selected_ids: Sequence[str]) -> dict[str, Any]:
    nodes = {str(item["dna_id"]): dict(item) for item in graph.get("nodes", [])}
    if not selected_ids:
        raise HarvestContractError("at least one candidate is required")
    selected: list[dict[str, Any]] = []
    for dna_id in selected_ids:
        if dna_id not in nodes:
            raise HarvestContractError(f"unknown candidate: {dna_id}")
        node = nodes[dna_id]
        if node.get("authority_state") != "AUTHORIZED":
            raise HarvestContractError("candidate authority denied")
        if not node.get("license", {}).get("compatible"):
            raise HarvestContractError("candidate licence is not compatible")
        selected.append(node)
    result = {
        "schema": "BCO_PRIME_COMPILED_CAPABILITY_CANDIDATE_V1",
        "candidate_id": "candidate-" + digest(sorted(selected_ids))[:24],
        "selected_dna_ids": sorted(selected_ids),
        "normalized_interface": {
            "input": "JSON_MAPPING",
            "output": "JSON_MAPPING_WITH_PROOF_RECEIPT",
            "external_effects": "DENIED",
        },
        "dependency_manifest": sorted({dep for node in selected for dep in node.get("dependencies", [])}),
        "threat_model": ["UNTRUSTED_INPUT", "LICENCE_DRIFT", "DEPENDENCY_DRIFT", "SHADOW_ESCAPE", "FALSE_PROMOTION"],
        "generated_tests": ["schema_validation", "authority_denial", "licence_denial", "deterministic_replay", "shadow_escape_denial", "rollback"],
        "shadow_package": {"format": "DECLARATIVE_JSON", "executable": False, "quarantined": True},
        "promotion_recommendation": "SHADOW_QUALIFICATION_REQUIRED",
        "stablePromotionAuthorized": False,
        "providerEffectAuthorized": False,
        "manualUserTasks": [],
        "ownerActionRequired": False,
    }
    result["candidate_sha256"] = digest(result)
    return result


def _contains_escape(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized_key = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if normalized_key in _NORMALIZED_FORBIDDEN_EFFECT_KEYS and item not in (None, False, 0, [], {}):
                return True
            if _contains_escape(item):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_escape(item) for item in value)
    return False


def qualify_shadow_candidate(
    candidate: Mapping[str, Any],
    paired_cases: Sequence[Mapping[str, Any]],
    *,
    rollback_available: bool,
    independent_verifier_pass: bool,
) -> dict[str, Any]:
    reasons: list[str] = []
    if _contains_escape(candidate):
        reasons.append("SHADOW_ESCAPE_REJECTED")
    if candidate.get("shadow_package", {}).get("quarantined") is not True:
        reasons.append("QUARANTINE_REQUIRED")
    if len(paired_cases) < 30:
        reasons.append("THIRTY_PAIRED_CASES_REQUIRED")
    baseline = 0.0
    proposed = 0.0
    hard_regressions = 0
    for index, case in enumerate(paired_cases):
        before = case.get("baseline_quality")
        after = case.get("candidate_quality")
        if not isinstance(before, (int, float)) or not isinstance(after, (int, float)):
            raise HarvestContractError(f"case {index} quality values must be numeric")
        if not 0 <= before <= 1 or not 0 <= after <= 1:
            raise HarvestContractError(f"case {index} quality values out of range")
        baseline += float(before)
        proposed += float(after)
        if case.get("hard_regression") is True or case.get("passed") is not True:
            hard_regressions += 1
    divisor = len(paired_cases) or 1
    uplift = proposed / divisor - baseline / divisor
    if hard_regressions:
        reasons.append("HARD_REGRESSION")
    if uplift < 0.03:
        reasons.append("MINIMUM_QUALITY_UPLIFT_NOT_MET")
    if not rollback_available:
        reasons.append("ROLLBACK_REQUIRED")
    if not independent_verifier_pass:
        reasons.append("INDEPENDENT_VERIFIER_REQUIRED")
    accepted = not reasons
    result = {
        "schema": "BCO_PRIME_SHADOW_QUALIFICATION_V1",
        "candidate_id": candidate.get("candidate_id"),
        "paired_cases": len(paired_cases),
        "quality_uplift": round(uplift, 6),
        "hard_regressions": hard_regressions,
        "state": "SHADOW_PROVEN" if accepted else "HOLD",
        "shadowProven": accepted,
        "stablePromotionAuthorized": False,
        "providerEffectAuthorized": False,
        "reasons": reasons or ["DECLARATIVE_SHADOW_CANDIDATE_ONLY"],
        "rollbackAvailable": rollback_available,
        "manualUserTasks": [],
        "ownerActionRequired": False,
    }
    result["receipt_sha256"] = digest(result)
    return result


def manifest() -> dict[str, Any]:
    result = {
        "schema": SCHEMA,
        "version": VERSION,
        "allowed_suffixes": sorted(ALLOWED_SUFFIXES),
        "max_file_bytes_default": DEFAULT_MAX_FILE_BYTES,
        "max_files_default": DEFAULT_MAX_FILES,
        "network_crawler": False,
        "raw_content_emitted": False,
        "generated_code_execution": False,
        "stablePromotionAuthorized": False,
        "providerEffectAuthorized": False,
        "manualUserTasks": [],
        "ownerActionRequired": False,
    }
    result["manifest_sha256"] = digest(result)
    return result


__all__ = [
    "CapabilityDNA",
    "CapabilityRadar",
    "HarvestContractError",
    "build_opportunity_graph",
    "compile_candidate",
    "detect_license",
    "manifest",
    "qualify_shadow_candidate",
    "redact_secrets",
]

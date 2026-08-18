from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from importlib.resources import files
from typing import Any, Mapping


class AdapterState(str, Enum):
    SOURCE_READY_PROVIDER_DISABLED = "SOURCE_READY_PROVIDER_DISABLED"


class ToolRisk(str, Enum):
    READ_ONLY = "READ_ONLY"
    EFFECTFUL = "EFFECTFUL"


class AuthorityLane(str, Enum):
    INVENTORY_READ = "INVENTORY_READ"
    APPS_SCRIPT_CHANGE = "APPS_SCRIPT_CHANGE"
    API_ENABLEMENT = "API_ENABLEMENT"
    CANARY = "CANARY"
    DEPLOYMENT = "DEPLOYMENT"
    PROMOTION = "PROMOTION"


class AdapterContractError(ValueError):
    pass


class ProviderRouteDisabled(RuntimeError):
    pass


@dataclass(frozen=True)
class EvidenceEnvelope:
    payload: Mapping[str, Any]
    observed_at: float
    proof_ref: str


@dataclass(frozen=True)
class GateResult:
    valid: bool
    reasons: tuple[str, ...]
    details: Mapping[str, Any]

    def public(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "reasons": list(self.reasons),
            "details": dict(self.details),
        }


_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SHA256_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_REVISION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,252}$")
_SECRET_FIELD = re.compile(r"(?:token|secret|credential|password|private[_-]?key)", re.IGNORECASE)


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def semantic_sha256(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def _load_contract() -> dict[str, Any]:
    raw = files("jarvis").joinpath("resources", "gcp_admin_mcp_adapter_v1.json").read_text(
        encoding="utf-8"
    )
    contract = json.loads(raw)
    if contract.get("schema") != "JARVIS-GCP-ADMIN-MCP-ADAPTER-1":
        raise AdapterContractError("ADAPTER_CONTRACT_SCHEMA_INVALID")
    if contract.get("adapterState") != AdapterState.SOURCE_READY_PROVIDER_DISABLED.value:
        raise AdapterContractError("ADAPTER_CONTRACT_STATE_INVALID")
    tools = contract.get("tools")
    if not isinstance(tools, list) or len(tools) != 17:
        raise AdapterContractError("ADAPTER_TOOL_COUNT_INVALID")
    names = [item.get("name") for item in tools if isinstance(item, dict)]
    if len(set(names)) != 17 or set(names) != set(contract.get("exactToolNames", [])):
        raise AdapterContractError("ADAPTER_TOOL_NAMES_INVALID")
    forbidden = set(contract.get("forbiddenToolNames", []))
    if forbidden & set(names):
        raise AdapterContractError("ADAPTER_FORBIDDEN_TOOL_EXPOSED")
    risks = [item.get("risk") for item in tools]
    if risks.count(ToolRisk.READ_ONLY.value) != 14 or risks.count(ToolRisk.EFFECTFUL.value) != 3:
        raise AdapterContractError("ADAPTER_TOOL_RISK_COUNTS_INVALID")
    return contract


CONTRACT = _load_contract()
TOOL_SPECS = {item["name"]: item for item in CONTRACT["tools"]}


def capability_snapshot() -> dict[str, Any]:
    source = CONTRACT["sourceBindings"]
    return {
        "id": "gcp_admin_mcp",
        "state": AdapterState.SOURCE_READY_PROVIDER_DISABLED.value,
        "serverVersion": CONTRACT["serverVersion"],
        "toolCount": len(TOOL_SPECS),
        "readOnlyToolCount": sum(
            spec["risk"] == ToolRisk.READ_ONLY.value for spec in TOOL_SPECS.values()
        ),
        "effectfulToolCount": sum(
            spec["risk"] == ToolRisk.EFFECTFUL.value for spec in TOOL_SPECS.values()
        ),
        "sourceProof": {
            "mcpHead": source["mcpHead"],
            "mcpServiceTree": source["mcpServiceTree"],
            "jarvisBaseHead": source["jarvisBaseHead"],
        },
        "providerExecutionAllowed": False,
    }


def _is_datetime(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _validate_value(field: Mapping[str, Any], value: Any, path: str) -> list[str]:
    kind = field.get("kind")
    reasons: list[str] = []
    valid_type = {
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
    }.get(kind, False)
    if not valid_type:
        return [f"ARGUMENT_TYPE_INVALID:{path}"]
    if kind == "string":
        if not value or len(value) > int(field.get("maxLength", 4096)):
            reasons.append(f"ARGUMENT_VALUE_INVALID:{path}")
        pattern = field.get("pattern")
        if pattern and not re.fullmatch(pattern, value):
            reasons.append(f"ARGUMENT_PATTERN_INVALID:{path}")
        if field.get("format") == "date-time" and not _is_datetime(value):
            reasons.append(f"ARGUMENT_DATETIME_INVALID:{path}")
    elif kind == "integer":
        minimum = field.get("minimum")
        maximum = field.get("maximum")
        if minimum is not None and value < minimum:
            reasons.append(f"ARGUMENT_RANGE_INVALID:{path}")
        if maximum is not None and value > maximum:
            reasons.append(f"ARGUMENT_RANGE_INVALID:{path}")
    elif kind == "object":
        nested = field.get("fields")
        if isinstance(nested, list):
            reasons.extend(_validate_fields(nested, value, path))
    elif kind == "array":
        minimum = field.get("minItems")
        maximum = field.get("maxItems")
        if minimum is not None and len(value) < minimum:
            reasons.append(f"ARGUMENT_RANGE_INVALID:{path}")
        if maximum is not None and len(value) > maximum:
            reasons.append(f"ARGUMENT_RANGE_INVALID:{path}")
    return reasons


def _validate_fields(
    fields: list[Mapping[str, Any]], values: Mapping[str, Any], prefix: str = ""
) -> list[str]:
    reasons: list[str] = []
    by_name = {str(field["name"]): field for field in fields}
    for name in sorted(set(values) - set(by_name)):
        path = f"{prefix}.{name}" if prefix else name
        reasons.append(f"ARGUMENT_UNKNOWN:{path}")
        if _SECRET_FIELD.search(name):
            reasons.append(f"SECRET_INPUT_PROHIBITED:{path}")
    for name, field in by_name.items():
        path = f"{prefix}.{name}" if prefix else name
        if field.get("required") and name not in values:
            reasons.append(f"ARGUMENT_REQUIRED:{path}")
            continue
        if name not in values:
            continue
        if _SECRET_FIELD.search(name):
            reasons.append(f"SECRET_INPUT_PROHIBITED:{path}")
        reasons.extend(_validate_value(field, values[name], path))
    return reasons


def validate_tool_arguments(tool_name: str, arguments: Mapping[str, Any] | None) -> GateResult:
    spec = TOOL_SPECS.get(tool_name)
    if spec is None:
        return GateResult(False, ("TOOL_NOT_ALLOWLISTED",), {"tool": tool_name})
    values = arguments if isinstance(arguments, Mapping) else {}
    reasons = _validate_fields(spec["fields"], values)
    if spec["risk"] == ToolRisk.EFFECTFUL.value:
        reasons.append("EFFECTFUL_TOOL_DISABLED")
    return GateResult(
        not reasons,
        tuple(dict.fromkeys(reasons)),
        {
            "tool": tool_name,
            "risk": spec["risk"],
            "lane": spec["lane"],
            "argumentsHash": semantic_sha256(values),
            "argumentsPersisted": False,
        },
    )


def plan(tool_name: str, arguments: Mapping[str, Any] | None) -> dict[str, Any]:
    gate = validate_tool_arguments(tool_name, arguments)
    spec = TOOL_SPECS.get(tool_name)
    reasons = list(gate.reasons)
    if "PROVIDER_ROUTE_FEATURE_DISABLED" not in reasons:
        reasons.append("PROVIDER_ROUTE_FEATURE_DISABLED")
    return {
        "adapterState": AdapterState.SOURCE_READY_PROVIDER_DISABLED.value,
        "serverVersion": CONTRACT["serverVersion"],
        "tool": tool_name,
        "risk": spec["risk"] if spec else "UNKNOWN",
        "authorityLane": spec["lane"] if spec else "UNKNOWN",
        "schemaValid": gate.valid,
        "executionAllowed": False,
        "effectState": "NO_EFFECTS_EXECUTED",
        "argumentsHash": gate.details.get("argumentsHash"),
        "argumentsPersisted": False,
        "reasons": reasons,
        "nextBestAutomatedPathway": CONTRACT["nextBestAutomatedPathway"],
    }


def invoke(tool_name: str, arguments: Mapping[str, Any] | None) -> None:
    _ = plan(tool_name, arguments)
    raise ProviderRouteDisabled("GCP_ADMIN_MCP_PROVIDER_ROUTE_DISABLED")


def _freshness(envelope: EvidenceEnvelope, now: float | None = None) -> list[str]:
    current = time.time() if now is None else float(now)
    reasons: list[str] = []
    if not envelope.proof_ref.strip():
        reasons.append("PROOF_REF_REQUIRED")
    if envelope.observed_at > current + 30:
        reasons.append("PROOF_TIME_IN_FUTURE")
    age = current - envelope.observed_at
    if age < -30 or age > int(CONTRACT["proofGates"]["maxAgeSeconds"]):
        reasons.append("PROOF_STALE")
    return reasons


def _equals(payload: Mapping[str, Any], expected: Mapping[str, Any], reasons: list[str], prefix: str) -> None:
    for key, value in expected.items():
        if payload.get(key) != value:
            reasons.append(f"{prefix}_MISMATCH:{key}")


def validate_global_wif_receipt(
    envelope: EvidenceEnvelope, now: float | None = None
) -> GateResult:
    payload = envelope.payload
    expected = CONTRACT["proofGates"]["globalWifReceipt"]
    reasons = _freshness(envelope, now)
    _equals(payload, expected["exact"], reasons, "GLOBAL_WIF")
    for key in expected["requiredTrue"]:
        if payload.get(key) is not True:
            reasons.append(f"GLOBAL_WIF_TRUE_REQUIRED:{key}")
    for key in expected["requiredEmptyArrays"]:
        if payload.get(key) != []:
            reasons.append(f"GLOBAL_WIF_EMPTY_REQUIRED:{key}")
    return GateResult(not reasons, tuple(reasons), {"proofRef": envelope.proof_ref})


def validate_mcp_wif_receipt(
    envelope: EvidenceEnvelope, now: float | None = None
) -> GateResult:
    payload = envelope.payload
    expected = CONTRACT["proofGates"]["mcpWifReceipt"]
    reasons = _freshness(envelope, now)
    _equals(payload, expected["exact"], reasons, "MCP_WIF")
    hashes = payload.get("evidenceHashes")
    if not isinstance(hashes, Mapping):
        reasons.append("MCP_WIF_EVIDENCE_HASHES_REQUIRED")
    else:
        if set(hashes) != set(expected["evidenceHashKeys"]):
            reasons.append("MCP_WIF_EVIDENCE_HASH_KEYS_INVALID")
        for key, value in hashes.items():
            if not isinstance(value, str) or not _HEX64.fullmatch(value):
                reasons.append(f"MCP_WIF_EVIDENCE_HASH_INVALID:{key}")
    return GateResult(not reasons, tuple(reasons), {"proofRef": envelope.proof_ref})


def validate_audit_record(record: Mapping[str, Any], expected_action: str) -> list[str]:
    reasons: list[str] = []
    audit_id = record.get("auditId")
    if not isinstance(audit_id, str) or not audit_id:
        reasons.append("AUDIT_ID_REQUIRED")
    if not _is_datetime(record.get("timestamp")):
        reasons.append("AUDIT_TIMESTAMP_INVALID")
    if record.get("action") != expected_action:
        reasons.append("AUDIT_ACTION_MISMATCH")
    if not isinstance(record.get("inputHash"), str) or not _HEX64.fullmatch(record["inputHash"]):
        reasons.append("AUDIT_INPUT_HASH_INVALID")
    if record.get("status") != "DONE":
        reasons.append("AUDIT_STATUS_NOT_DONE")
    return reasons


def _validate_join(join: Mapping[str, Any], mode: str) -> list[str]:
    target = CONTRACT["target"]
    reasons: list[str] = []
    exact = {
        "attestationMode": mode,
        "projectId": target["projectId"],
        "projectNumber": target["projectNumber"],
        "region": target["region"],
        "service": target["service"],
    }
    _equals(join, exact, reasons, "LINEAGE")
    revision = join.get("revision")
    if not isinstance(revision, str) or not _REVISION.fullmatch(revision):
        reasons.append("LINEAGE_REVISION_INVALID")
    digest = join.get("imageDigest")
    if not isinstance(digest, str) or not _SHA256_DIGEST.fullmatch(digest):
        reasons.append("LINEAGE_IMAGE_DIGEST_INVALID")
    artifact_uri = join.get("artifactUri")
    if not isinstance(artifact_uri, str) or not digest or not artifact_uri.endswith(f"@{digest}"):
        reasons.append("LINEAGE_ARTIFACT_URI_INVALID")
    if join.get("buildStatus") != "SUCCESS":
        reasons.append("LINEAGE_BUILD_NOT_SUCCESS")
    for key in ("sourceHash", "sourceVerificationHash", "iamPolicyHash"):
        value = join.get(key)
        if not isinstance(value, str) or not _HEX64.fullmatch(value):
            reasons.append(f"LINEAGE_HASH_INVALID:{key}")
    if not isinstance(join.get("source"), Mapping) or not join["source"]:
        reasons.append("LINEAGE_SOURCE_REQUIRED")
    if not isinstance(join.get("sourceVerification"), Mapping) or not join["sourceVerification"]:
        reasons.append("LINEAGE_SOURCE_VERIFICATION_REQUIRED")
    if join.get("iamPrivate") is not True:
        reasons.append("LINEAGE_PRIVATE_IAM_REQUIRED")
    if join.get("publicIamMembers") != []:
        reasons.append("LINEAGE_PUBLIC_IAM_PROHIBITED")
    traffic = join.get("traffic")
    if not isinstance(traffic, list) or not traffic:
        reasons.append("LINEAGE_TRAFFIC_REQUIRED")
    else:
        total = 0
        target_seen = False
        for row in traffic:
            if not isinstance(row, Mapping):
                reasons.append("LINEAGE_TRAFFIC_SCHEMA_INVALID")
                continue
            percent = row.get("percent")
            if not isinstance(percent, int) or isinstance(percent, bool) or percent < 0 or percent > 100:
                reasons.append("LINEAGE_TRAFFIC_PERCENT_INVALID")
                continue
            total += percent
            if row.get("revision") == revision and percent > 0:
                target_seen = True
        if total != 100:
            reasons.append("LINEAGE_TRAFFIC_TOTAL_INVALID")
        if not target_seen:
            reasons.append("LINEAGE_TARGET_REVISION_NOT_IN_TRAFFIC")
    return reasons


def _validate_comparison(comparison: Mapping[str, Any], mode: str) -> list[str]:
    reasons: list[str] = []
    if comparison.get("identifiersMatch") is not True:
        reasons.append("LINEAGE_IDENTIFIERS_MISMATCH")
    if comparison.get("issues") != []:
        reasons.append("LINEAGE_ISSUES_PRESENT")
    if comparison.get("contradictions") != []:
        reasons.append("LINEAGE_CONTRADICTIONS_PRESENT")
    first = comparison.get("pass1")
    second = comparison.get("pass2")
    if not isinstance(first, Mapping) or not isinstance(second, Mapping):
        return reasons + ["LINEAGE_TWO_PASSES_REQUIRED"]
    for label, item in (("pass1", first), ("pass2", second)):
        if not _is_datetime(item.get("capturedAt")):
            reasons.append(f"LINEAGE_CAPTURE_TIME_INVALID:{label}")
        if item.get("issues") != [] or item.get("contradictions") != []:
            reasons.append(f"LINEAGE_PASS_NOT_CLEAN:{label}")
        join = item.get("join")
        if not isinstance(join, Mapping):
            reasons.append(f"LINEAGE_JOIN_REQUIRED:{label}")
        else:
            reasons.extend(_validate_join(join, mode))
    if isinstance(first.get("join"), Mapping) and isinstance(second.get("join"), Mapping):
        first_hash = semantic_sha256(first["join"])
        second_hash = semantic_sha256(second["join"])
        if first_hash != second_hash:
            reasons.append("LINEAGE_JOIN_DRIFT")
        if comparison.get("pass1JoinHash") != first_hash:
            reasons.append("LINEAGE_PASS1_HASH_MISMATCH")
        if comparison.get("pass2JoinHash") != second_hash:
            reasons.append("LINEAGE_PASS2_HASH_MISMATCH")
    return reasons


def validate_lineage_attestation(
    envelope: EvidenceEnvelope, now: float | None = None, *, require_rollback: bool = False
) -> GateResult:
    record = envelope.payload
    reasons = _freshness(envelope, now)
    reasons.extend(validate_audit_record(record, "gcp_deployment_lineage_attest"))
    result = record.get("result")
    if not isinstance(result, Mapping):
        reasons.append("LINEAGE_RESULT_REQUIRED")
        return GateResult(False, tuple(reasons), {"proofRef": envelope.proof_ref})
    if result.get("state") != "ATTESTED":
        reasons.append("LINEAGE_STATE_NOT_ATTESTED")
    if result.get("proofBoundary") != "provider_identifiers_matched_across_two_independent_reads":
        reasons.append("LINEAGE_PROOF_BOUNDARY_INVALID")
    current = result.get("current")
    if not isinstance(current, Mapping):
        reasons.append("LINEAGE_CURRENT_REQUIRED")
    else:
        reasons.extend(_validate_comparison(current, "SERVING"))
    if require_rollback:
        rollback = result.get("rollback")
        if not isinstance(rollback, Mapping):
            reasons.append("ROLLBACK_LINEAGE_REQUIRED")
        else:
            reasons.extend(_validate_comparison(rollback, "ROLLBACK"))
    return GateResult(not reasons, tuple(dict.fromkeys(reasons)), {"proofRef": envelope.proof_ref})


def health_is_deployment_proof(payload: Mapping[str, Any]) -> GateResult:
    if payload.get("proofBoundary") == "transport_liveness_only":
        return GateResult(False, ("HEALTH_IS_LIVENESS_ONLY",), {})
    return GateResult(False, ("STRUCTURED_LINEAGE_ATTESTATION_REQUIRED",), {})


def readiness(
    *,
    global_wif: EvidenceEnvelope | None = None,
    mcp_wif: EvidenceEnvelope | None = None,
    lineage: EvidenceEnvelope | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    gates = {
        "globalWif": validate_global_wif_receipt(global_wif, now).public()
        if global_wif
        else GateResult(False, ("GLOBAL_WIF_RECEIPT_REQUIRED",), {}).public(),
        "mcpWif": validate_mcp_wif_receipt(mcp_wif, now).public()
        if mcp_wif
        else GateResult(False, ("MCP_WIF_RECEIPT_REQUIRED",), {}).public(),
        "lineage": validate_lineage_attestation(lineage, now).public()
        if lineage
        else GateResult(False, ("LINEAGE_ATTESTATION_REQUIRED",), {}).public(),
    }
    evidence_complete = all(item["valid"] for item in gates.values())
    return {
        "adapterState": AdapterState.SOURCE_READY_PROVIDER_DISABLED.value,
        "evidenceComplete": evidence_complete,
        "inventoryReadLane": "ELIGIBLE_BUT_FEATURE_DISABLED" if evidence_complete else "BLOCKED",
        "canaryLane": "DISABLED_SEPARATE_AUTHORITY_REQUIRED",
        "deploymentLane": "DISABLED_SEPARATE_AUTHORITY_REQUIRED",
        "promotionLane": "DISABLED_ROLLBACK_AND_OWNER_AUTHORITY_REQUIRED",
        "executionAllowed": False,
        "gates": gates,
        "nextBestAutomatedPathway": CONTRACT["nextBestAutomatedPathway"],
    }

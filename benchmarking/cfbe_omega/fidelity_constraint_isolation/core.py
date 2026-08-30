from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from enum import StrEnum
import hashlib
import json
import math
from typing import Any, Mapping, Sequence

from evidenceops.caseforge.capability_decision import (
    BlockerKind,
    CapabilityDecisionRequest,
    CapabilityResolutionGate,
    CapabilityScope,
    CapabilityState,
    RouteAttempt,
    TerminalClaim,
)


SCHEMA = "CFBE-OMEGA-FIDELITY-CONSTRAINT-ISOLATION-RESULT-V1"
AUTHORITY_RANK = {f"A{rank}": rank for rank in range(6)}


class FidelityError(ValueError):
    """Raised when a fidelity contract or isolation input is invalid."""


class FidelityMode(StrEnum):
    EXACT = "EXACT"
    EXACT_OR_ADDITIVE = "EXACT_OR_ADDITIVE"
    PROTECTED_INVARIANTS = "PROTECTED_INVARIANTS"


class InvariantKind(StrEnum):
    LITERAL = "LITERAL"
    JSON_POINTER = "JSON_POINTER"
    PYTHON_SYMBOL = "PYTHON_SYMBOL"


class MaturityState(StrEnum):
    DESIGNED = "DESIGNED"
    SOURCE_IMPLEMENTED = "SOURCE_IMPLEMENTED"
    DETERMINISTIC_TESTED = "DETERMINISTIC_TESTED"
    REGISTERED = "REGISTERED"
    AUTHORIZED = "AUTHORIZED"
    PROVIDER_READY = "PROVIDER_READY"
    PROVIDER_DEPLOYED = "PROVIDER_DEPLOYED"
    READBACK_PROVEN = "READBACK_PROVEN"


MATURITY_RANK = {
    state: rank
    for rank, state in enumerate(
        (
            MaturityState.DESIGNED,
            MaturityState.SOURCE_IMPLEMENTED,
            MaturityState.DETERMINISTIC_TESTED,
            MaturityState.REGISTERED,
            MaturityState.AUTHORIZED,
            MaturityState.PROVIDER_READY,
            MaturityState.PROVIDER_DEPLOYED,
            MaturityState.READBACK_PROVEN,
        )
    )
}


@dataclass(frozen=True)
class ProtectedInvariant:
    invariant_id: str
    kind: InvariantKind
    selector: str
    minimum_occurrences: int = 1

    def validate(self) -> "ProtectedInvariant":
        _require_identifier(self.invariant_id, "protected invariant id")
        if not isinstance(self.kind, InvariantKind):
            raise FidelityError("protected invariant kind is invalid")
        if not isinstance(self.selector, str) or not self.selector:
            raise FidelityError(f"selector is required for invariant {self.invariant_id}")
        if isinstance(self.minimum_occurrences, bool) or not isinstance(
            self.minimum_occurrences, int
        ):
            raise FidelityError("minimum_occurrences must be an integer")
        if self.minimum_occurrences < 1:
            raise FidelityError("minimum_occurrences must be at least one")
        return self


@dataclass(frozen=True)
class CanonicalSource:
    source_id: str
    version: str
    media_type: str
    content: str
    fidelity_mode: FidelityMode
    protected_invariants: tuple[ProtectedInvariant, ...] = ()
    expected_sha256: str = ""

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()

    def validate(self) -> "CanonicalSource":
        _require_identifier(self.source_id, "canonical source_id")
        _require_identifier(self.version, "canonical version")
        _require_identifier(self.media_type, "canonical media_type")
        if not isinstance(self.content, str) or not self.content:
            raise FidelityError("canonical content must not be empty")
        if not isinstance(self.fidelity_mode, FidelityMode):
            raise FidelityError("canonical fidelity_mode is invalid")
        if not isinstance(self.expected_sha256, str):
            raise FidelityError("expected_sha256 must be a string")
        if self.expected_sha256:
            _require_sha256(self.expected_sha256, "expected_sha256")
            if self.sha256 != self.expected_sha256:
                raise FidelityError("canonical content does not match expected_sha256")
        parsed_json: Any | None = None
        parsed_python: ast.AST | None = None
        invariant_ids: set[str] = set()
        if self.media_type == "application/json":
            try:
                parsed_json = json.loads(self.content)
            except json.JSONDecodeError as exc:
                raise FidelityError("canonical JSON content is invalid") from exc
        for invariant in self.protected_invariants:
            if not isinstance(invariant, ProtectedInvariant):
                raise FidelityError("protected invariants must use ProtectedInvariant")
            invariant.validate()
            if invariant.invariant_id in invariant_ids:
                raise FidelityError(f"duplicate protected invariant: {invariant.invariant_id}")
            invariant_ids.add(invariant.invariant_id)
            if invariant.kind is InvariantKind.LITERAL:
                if self.content.count(invariant.selector) < invariant.minimum_occurrences:
                    raise FidelityError(
                        f"canonical source violates its own invariant {invariant.invariant_id}"
                    )
            elif invariant.kind is InvariantKind.JSON_POINTER:
                if parsed_json is None:
                    try:
                        parsed_json = json.loads(self.content)
                    except json.JSONDecodeError as exc:
                        raise FidelityError("canonical JSON content is invalid") from exc
                try:
                    _json_pointer(parsed_json, invariant.selector)
                except KeyError as exc:
                    raise FidelityError(
                        f"canonical JSON selector missing for invariant {invariant.invariant_id}"
                    ) from exc
            elif invariant.kind is InvariantKind.PYTHON_SYMBOL:
                if parsed_python is None:
                    try:
                        parsed_python = ast.parse(self.content)
                    except SyntaxError as exc:
                        raise FidelityError("canonical Python content is invalid") from exc
                try:
                    _find_python_symbol(parsed_python, invariant.selector)
                except KeyError as exc:
                    raise FidelityError(
                        f"canonical Python symbol missing for invariant {invariant.invariant_id}"
                    ) from exc
        if self.fidelity_mode is FidelityMode.PROTECTED_INVARIANTS and not self.protected_invariants:
            raise FidelityError("PROTECTED_INVARIANTS mode requires at least one invariant")
        return self


@dataclass(frozen=True)
class FidelityViolation:
    invariant_id: str
    code: str
    detail: str


@dataclass(frozen=True)
class FidelityDecision:
    accepted: bool
    verdict: str
    mode: FidelityMode
    canonical_sha256: str
    candidate_sha256: str
    violations: tuple[FidelityViolation, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "verdict": self.verdict,
            "mode": self.mode.value,
            "canonicalSha256": self.canonical_sha256,
            "candidateSha256": self.candidate_sha256,
            "violations": [asdict(violation) for violation in self.violations],
        }


@dataclass(frozen=True)
class MaturityEvidence:
    source_ref: str = ""
    test_ref: str = ""
    registration_ref: str = ""
    authorization_ref: str = ""
    readiness_ref: str = ""
    deployment_ref: str = ""
    readback_ref: str = ""
    rollback_ref: str = ""

    def validate(self, state: MaturityState) -> "MaturityEvidence":
        if not isinstance(state, MaturityState):
            raise FidelityError("maturity state is invalid")
        for name, value in asdict(self).items():
            if not isinstance(value, str):
                raise FidelityError(f"{name} must be a string")
        required: list[tuple[str, str]] = []
        rank = MATURITY_RANK[state]
        if rank >= MATURITY_RANK[MaturityState.SOURCE_IMPLEMENTED]:
            required.append(("source_ref", self.source_ref))
        if rank >= MATURITY_RANK[MaturityState.DETERMINISTIC_TESTED]:
            required.extend((("test_ref", self.test_ref), ("rollback_ref", self.rollback_ref)))
        if rank >= MATURITY_RANK[MaturityState.REGISTERED]:
            required.append(("registration_ref", self.registration_ref))
        if rank >= MATURITY_RANK[MaturityState.AUTHORIZED]:
            required.append(("authorization_ref", self.authorization_ref))
        if rank >= MATURITY_RANK[MaturityState.PROVIDER_READY]:
            required.append(("readiness_ref", self.readiness_ref))
        if rank >= MATURITY_RANK[MaturityState.PROVIDER_DEPLOYED]:
            required.append(("deployment_ref", self.deployment_ref))
        if rank >= MATURITY_RANK[MaturityState.READBACK_PROVEN]:
            required.append(("readback_ref", self.readback_ref))
        missing = [name for name, value in required if not value.strip()]
        if missing:
            raise FidelityError(
                f"{state.value} maturity lacks required evidence: {','.join(missing)}"
            )
        return self

    def public_dict(self) -> dict[str, str]:
        return {
            "sourceRef": self.source_ref,
            "testRef": self.test_ref,
            "registrationRef": self.registration_ref,
            "authorizationRef": self.authorization_ref,
            "readinessRef": self.readiness_ref,
            "deploymentRef": self.deployment_ref,
            "readbackRef": self.readback_ref,
            "rollbackRef": self.rollback_ref,
        }


@dataclass(frozen=True)
class CapabilityAttestation:
    capability_id: str
    maturity: MaturityState
    evidence: MaturityEvidence

    def validate(self) -> "CapabilityAttestation":
        _require_identifier(self.capability_id, "capability_id")
        if not isinstance(self.evidence, MaturityEvidence):
            raise FidelityError("capability evidence must use MaturityEvidence")
        self.evidence.validate(self.maturity)
        return self


@dataclass(frozen=True)
class PlatformProfile:
    platform_id: str
    exact_scope: str
    discovery_ref: str
    capabilities: tuple[CapabilityAttestation, ...] = ()

    def validate(self) -> "PlatformProfile":
        _require_identifier(self.platform_id, "platform_id")
        if not isinstance(self.exact_scope, str) or not self.exact_scope.strip():
            raise FidelityError("platform exact_scope is required")
        if not isinstance(self.discovery_ref, str) or not self.discovery_ref.strip():
            raise FidelityError("platform discovery_ref is required")
        seen: set[str] = set()
        for capability in self.capabilities:
            capability.validate()
            if capability.capability_id in seen:
                raise FidelityError(f"duplicate platform capability: {capability.capability_id}")
            seen.add(capability.capability_id)
        return self


@dataclass(frozen=True)
class CapabilityRequirement:
    capability_id: str
    description: str
    platform_hard_limit: bool = False
    boundary_evidence_ref: str = ""

    def validate(self) -> "CapabilityRequirement":
        _require_identifier(self.capability_id, "capability_id")
        if not isinstance(self.description, str) or not self.description.strip():
            raise FidelityError(f"description required for {self.capability_id}")
        if not isinstance(self.platform_hard_limit, bool):
            raise FidelityError("platform_hard_limit must be a boolean")
        if not isinstance(self.boundary_evidence_ref, str):
            raise FidelityError("boundary_evidence_ref must be a string")
        if self.platform_hard_limit and not self.boundary_evidence_ref.strip():
            raise FidelityError("platform hard limit requires boundary evidence")
        return self


@dataclass(frozen=True)
class AdapterRoute:
    adapter_id: str
    provides: tuple[str, ...]
    maturity: MaturityState
    evidence: MaturityEvidence
    authority_ceiling: str = "A1"
    recurring_cost: float = 0.0
    user_burden: float = 0.0
    external_effect_required: bool = False
    preserves_canonical_source: bool = True
    fidelity_evidence_ref: str = ""
    priority: int = 100

    def validate(self) -> "AdapterRoute":
        _require_identifier(self.adapter_id, "adapter_id")
        if not self.provides:
            raise FidelityError(f"adapter {self.adapter_id} provides no capabilities")
        for capability_id in self.provides:
            _require_identifier(capability_id, "adapter capability_id")
        if not isinstance(self.maturity, MaturityState):
            raise FidelityError("adapter maturity state is invalid")
        if not isinstance(self.authority_ceiling, str) or self.authority_ceiling not in AUTHORITY_RANK:
            raise FidelityError(f"unknown authority class: {self.authority_ceiling}")
        if isinstance(self.recurring_cost, bool) or isinstance(self.user_burden, bool):
            raise FidelityError("adapter cost and user burden must be numbers")
        if not isinstance(self.recurring_cost, (int, float)) or not isinstance(
            self.user_burden, (int, float)
        ):
            raise FidelityError("adapter cost and user burden must be numbers")
        if self.recurring_cost < 0 or self.user_burden < 0:
            raise FidelityError("adapter cost and user burden must be non-negative")
        if not math.isfinite(self.recurring_cost) or not math.isfinite(self.user_burden):
            raise FidelityError("adapter cost and user burden must be finite")
        if not isinstance(self.external_effect_required, bool) or not isinstance(
            self.preserves_canonical_source, bool
        ):
            raise FidelityError("adapter effect and preservation fields must be booleans")
        if not isinstance(self.fidelity_evidence_ref, str):
            raise FidelityError("fidelity_evidence_ref must be a string")
        if isinstance(self.priority, bool) or not isinstance(self.priority, int):
            raise FidelityError("adapter priority must be an integer")
        if not isinstance(self.evidence, MaturityEvidence):
            raise FidelityError("adapter evidence must use MaturityEvidence")
        self.evidence.validate(self.maturity)
        return self


@dataclass(frozen=True)
class IsolationPolicy:
    available_authority: str = "A1"
    max_recurring_cost: float = 0.0
    max_user_burden: float = 0.0
    allow_external_effects: bool = False

    def validate(self) -> "IsolationPolicy":
        if not isinstance(self.available_authority, str) or self.available_authority not in AUTHORITY_RANK:
            raise FidelityError(f"unknown authority class: {self.available_authority}")
        if isinstance(self.max_recurring_cost, bool) or isinstance(self.max_user_burden, bool):
            raise FidelityError("policy limits must be numbers")
        if not isinstance(self.max_recurring_cost, (int, float)) or not isinstance(
            self.max_user_burden, (int, float)
        ):
            raise FidelityError("policy limits must be numbers")
        if self.max_recurring_cost < 0 or self.max_user_burden < 0:
            raise FidelityError("policy limits must be non-negative")
        if not math.isfinite(self.max_recurring_cost) or not math.isfinite(
            self.max_user_burden
        ):
            raise FidelityError("policy limits must be finite")
        if not isinstance(self.allow_external_effects, bool):
            raise FidelityError("allow_external_effects must be a boolean")
        return self


def _require_identifier(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise FidelityError(f"{name} is required")


def _require_sha256(value: str, name: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise FidelityError(f"{name} must be a lowercase SHA-256")


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _json_subset(baseline: Any, candidate: Any, path: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(baseline, dict):
        if not isinstance(candidate, dict):
            return [f"{path}: expected object"]
        for key, value in baseline.items():
            child = f"{path}.{key}"
            if key not in candidate:
                violations.append(f"{child}: missing")
            else:
                violations.extend(_json_subset(value, candidate[key], child))
        return violations
    if isinstance(baseline, list):
        if not isinstance(candidate, list):
            return [f"{path}: expected array"]
        candidate_index = 0
        for baseline_index, expected in enumerate(baseline):
            matched = False
            while candidate_index < len(candidate):
                if not _json_subset(expected, candidate[candidate_index], path):
                    matched = True
                    candidate_index += 1
                    break
                candidate_index += 1
            if not matched:
                violations.append(f"{path}[{baseline_index}]: ordered element missing or changed")
        return violations
    if type(baseline) is not type(candidate) or baseline != candidate:
        violations.append(f"{path}: canonical value changed")
    return violations


def _line_subsequence(baseline: str, candidate: str) -> bool:
    expected_lines = baseline.splitlines(keepends=True)
    candidate_lines = candidate.splitlines(keepends=True)
    cursor = 0
    for line in candidate_lines:
        if cursor < len(expected_lines) and line == expected_lines[cursor]:
            cursor += 1
    return cursor == len(expected_lines)


def _decode_json_pointer(pointer: str) -> list[str]:
    if not pointer.startswith("/"):
        raise FidelityError("JSON pointer selectors must begin with '/'")
    for index, char in enumerate(pointer):
        if char == "~" and (index + 1 >= len(pointer) or pointer[index + 1] not in "01"):
            raise FidelityError("JSON pointer contains an invalid escape")
    return [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]


def _json_pointer(document: Any, pointer: str) -> Any:
    current = document
    for part in _decode_json_pointer(pointer):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            raise KeyError(pointer)
    return current


def _find_python_symbol(tree: ast.AST, selector: str) -> ast.AST:
    parts = selector.split(".")
    current_nodes: Sequence[ast.stmt] = getattr(tree, "body", ())
    current: ast.AST | None = None
    for part in parts:
        current = next(
            (
                node
                for node in current_nodes
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and node.name == part
            ),
            None,
        )
        if current is None:
            raise KeyError(selector)
        current_nodes = getattr(current, "body", ())
    assert current is not None
    return current


def _invariant_violation(
    canonical: CanonicalSource,
    candidate: str,
    invariant: ProtectedInvariant,
) -> FidelityViolation | None:
    try:
        if invariant.kind is InvariantKind.LITERAL:
            canonical_count = canonical.content.count(invariant.selector)
            required = max(invariant.minimum_occurrences, canonical_count)
            if candidate.count(invariant.selector) < required:
                return FidelityViolation(
                    invariant.invariant_id,
                    "LITERAL_REMOVED_OR_REDUCED",
                    "required canonical literal occurrence was removed or reduced",
                )
            return None
        if invariant.kind is InvariantKind.JSON_POINTER:
            baseline_json = json.loads(canonical.content)
            candidate_json = json.loads(candidate)
            baseline_value = _json_pointer(baseline_json, invariant.selector)
            candidate_value = _json_pointer(candidate_json, invariant.selector)
            if baseline_value != candidate_value:
                return FidelityViolation(
                    invariant.invariant_id,
                    "JSON_POINTER_CHANGED",
                    "protected JSON value changed",
                )
            return None
        if invariant.kind is InvariantKind.PYTHON_SYMBOL:
            baseline_node = _find_python_symbol(ast.parse(canonical.content), invariant.selector)
            candidate_node = _find_python_symbol(ast.parse(candidate), invariant.selector)
            if ast.dump(baseline_node, include_attributes=False) != ast.dump(
                candidate_node, include_attributes=False
            ):
                return FidelityViolation(
                    invariant.invariant_id,
                    "PYTHON_SYMBOL_CHANGED",
                    "protected Python symbol changed structurally",
                )
            return None
    except (json.JSONDecodeError, SyntaxError) as exc:
        return FidelityViolation(
            invariant.invariant_id,
            "CANDIDATE_PARSE_FAILURE",
            f"candidate could not be parsed for {invariant.kind.value}: {exc.__class__.__name__}",
        )
    except KeyError:
        return FidelityViolation(
            invariant.invariant_id,
            "PROTECTED_SELECTOR_MISSING",
            "protected selector is missing from the candidate",
        )
    raise FidelityError(f"unsupported invariant kind: {invariant.kind}")


def evaluate_fidelity(canonical: CanonicalSource, candidate: str) -> FidelityDecision:
    canonical.validate()
    if not isinstance(candidate, str):
        raise FidelityError("candidate content must be a string")
    candidate_sha256 = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
    violations: list[FidelityViolation] = []

    if canonical.fidelity_mode is FidelityMode.EXACT:
        if candidate != canonical.content:
            violations.append(
                FidelityViolation("canonical-source", "EXACT_MISMATCH", "candidate is not byte-exact")
            )
    elif canonical.fidelity_mode is FidelityMode.EXACT_OR_ADDITIVE:
        if canonical.media_type == "application/json":
            try:
                baseline_json = json.loads(canonical.content)
                candidate_json = json.loads(candidate)
                for detail in _json_subset(baseline_json, candidate_json):
                    violations.append(
                        FidelityViolation("canonical-source", "CANONICAL_VALUE_CHANGED", detail)
                    )
            except json.JSONDecodeError as exc:
                violations.append(
                    FidelityViolation(
                        "canonical-source",
                        "CANDIDATE_PARSE_FAILURE",
                        f"JSON parse failed: {exc.__class__.__name__}",
                    )
                )
        elif not _line_subsequence(canonical.content, candidate):
            violations.append(
                FidelityViolation(
                    "canonical-source",
                    "NON_ADDITIVE_TEXT_CHANGE",
                    "canonical lines were removed, modified, or reordered",
                )
            )
    elif canonical.fidelity_mode is FidelityMode.PROTECTED_INVARIANTS:
        for invariant in canonical.protected_invariants:
            violation = _invariant_violation(canonical, candidate, invariant)
            if violation is not None:
                violations.append(violation)
    else:
        raise FidelityError(f"unsupported fidelity mode: {canonical.fidelity_mode}")

    accepted = not violations
    return FidelityDecision(
        accepted=accepted,
        verdict="ACCEPT_ZERO_DILUTION" if accepted else "REJECT_DILUTION",
        mode=canonical.fidelity_mode,
        canonical_sha256=canonical.sha256,
        candidate_sha256=candidate_sha256,
        violations=tuple(violations),
    )


def _adapter_rejection_reasons(
    adapter: AdapterRoute,
    needed: set[str],
    policy: IsolationPolicy,
) -> list[str]:
    reasons: list[str] = []
    if not needed.intersection(adapter.provides):
        reasons.append("NO_REQUIRED_CAPABILITY")
    if MATURITY_RANK[adapter.maturity] < MATURITY_RANK[MaturityState.DETERMINISTIC_TESTED]:
        reasons.append("INSUFFICIENT_MATURITY")
    if AUTHORITY_RANK[adapter.authority_ceiling] > AUTHORITY_RANK[policy.available_authority]:
        reasons.append("AUTHORITY_EXCEEDS_POLICY")
    if adapter.recurring_cost > policy.max_recurring_cost:
        reasons.append("RECURRING_COST_EXCEEDS_POLICY")
    if adapter.user_burden > policy.max_user_burden:
        reasons.append("USER_BURDEN_EXCEEDS_POLICY")
    if adapter.external_effect_required and not policy.allow_external_effects:
        reasons.append("EXTERNAL_EFFECT_NOT_AUTHORIZED")
    if not adapter.preserves_canonical_source:
        reasons.append("CANONICAL_PRESERVATION_UNPROVEN")
    if not adapter.fidelity_evidence_ref.strip():
        reasons.append("FIDELITY_EVIDENCE_REQUIRED")
    return reasons


def _stable_build_trigger(
    canonical_sha256: str,
    platform_id: str,
    capability_id: str,
) -> dict[str, Any]:
    digest = hashlib.sha256(
        f"{canonical_sha256}:{platform_id}:{capability_id}".encode("utf-8")
    ).hexdigest()
    return {
        "buildId": f"AO-CRA-CFBE-{digest[:16].upper()}",
        "state": "UNRESOLVED_ENGINEERING_BUILD",
        "gap": (
            f"The exact {platform_id} capability route for {capability_id} is not "
            "admissible under current evidence and policy."
        ),
        "desiredCapability": capability_id,
        "owningEngine": "ALPHA_TO_OMEGA_AUTONOMOUS_SOLUTION_FOUNDRY",
        "dependencies": [
            "current platform capability discovery",
            "canonical-preservation evidence",
            "typed authority and external-effect approval",
        ],
        "workaround": (
            "Preserve the canonical source and continue only through already-admitted "
            "capabilities; no hidden substitution is treated as closure."
        ),
        "implementationTasks": [
            "discover materially distinct native and adapter routes",
            "build the smallest reversible fidelity-preserving adapter",
            "run deterministic failure and rollback courts",
            "obtain exact-scope authorization and provider readback",
        ],
        "securityPrivacyLimits": [
            "no secret values in source or receipts",
            "no authority expansion or trust transfer",
            "no external effect without explicit authorization",
            "no canonical-source weakening",
        ],
        "tests": [
            "canonical fidelity court",
            "authority cost burden and external-effect court",
            "failure and rollback court",
            "provider semantic readback court",
        ],
        "acceptanceCriteria": [
            "ACCEPT_ZERO_DILUTION",
            "deterministic tests pass",
            "route is within policy",
            "provider semantic readback is independently verified",
        ],
        "nextExecutableAction": (
            "Run a bounded reuse-first route discovery and adapter experiment at A1_INTERNAL."
        ),
        "capabilityChangeTrigger": (
            f"Re-evaluate when {platform_id} discovery, permission, schema, or route "
            f"evidence changes for {capability_id}."
        ),
        "closureProof": (
            "Hash-bound implementation, deterministic tests, exact authorization, "
            "deployment receipt, semantic readback, and rollback proof."
        ),
        "canonicalBinding": canonical_sha256,
    }


def _boundary_language(platform: PlatformProfile, requirement: CapabilityRequirement) -> dict[str, Any]:
    blocker = BlockerKind.PLATFORM_HARD_LIMIT if requirement.platform_hard_limit else None
    decision = CapabilityResolutionGate().evaluate(
        CapabilityDecisionRequest(
            objective=requirement.description,
            claim=TerminalClaim.CANNOT,
            scope=CapabilityScope.PLATFORM_GLOBAL,
            state=CapabilityState.TOOL_SCHEMA_KNOWN,
            current_discovery_ref=(
                requirement.boundary_evidence_ref
                if requirement.platform_hard_limit
                else platform.discovery_ref
            ),
            route_attempts=(
                RouteAttempt(
                    route_id=f"{platform.platform_id}:{requirement.capability_id}:native",
                    blocker=blocker,
                    evidence_ref=platform.discovery_ref,
                ),
            ),
            blocker=blocker,
            equivalent_routes_checked=requirement.platform_hard_limit,
            exact_platform_scope=requirement.platform_hard_limit,
        )
    )
    return {
        "allowedLanguage": decision.allowed_language,
        "reasonCodes": list(decision.reason_codes),
        "scope": platform.exact_scope,
        "classification": (
            "PROVEN_PLATFORM_HARD_LIMIT"
            if requirement.platform_hard_limit
            else "UNRESOLVED_CAPABILITY"
        ),
        "boundaryEvidenceRef": requirement.boundary_evidence_ref,
    }


def isolate_constraints(
    canonical: CanonicalSource,
    candidate: str,
    platform: PlatformProfile,
    requirements: Sequence[CapabilityRequirement],
    adapters: Sequence[AdapterRoute] = (),
    policy: IsolationPolicy = IsolationPolicy(),
) -> dict[str, Any]:
    fidelity = evaluate_fidelity(canonical, candidate)
    platform.validate()
    policy.validate()
    if not requirements:
        raise FidelityError("at least one capability requirement is required")
    requirement_ids: set[str] = set()
    for requirement in requirements:
        requirement.validate()
        if requirement.capability_id in requirement_ids:
            raise FidelityError(f"duplicate requirement: {requirement.capability_id}")
        requirement_ids.add(requirement.capability_id)
    adapter_ids: set[str] = set()
    for adapter in adapters:
        adapter.validate()
        if adapter.adapter_id in adapter_ids:
            raise FidelityError(f"duplicate adapter: {adapter.adapter_id}")
        adapter_ids.add(adapter.adapter_id)

    decisions: list[dict[str, Any]] = []
    adapter_ledger: list[dict[str, Any]] = []
    build_triggers: list[dict[str, Any]] = []
    selected_adapters: list[AdapterRoute] = []

    if fidelity.accepted:
        native = {item.capability_id: item for item in platform.capabilities}
        unresolved: dict[str, CapabilityRequirement] = {}
        for requirement in requirements:
            attestation = native.get(requirement.capability_id)
            if attestation and MATURITY_RANK[attestation.maturity] >= MATURITY_RANK[
                MaturityState.DETERMINISTIC_TESTED
            ]:
                decisions.append(
                    {
                        "requirementId": requirement.capability_id,
                        "state": "NATIVE_ROUTE",
                        "selectedRoute": f"native:{platform.platform_id}",
                        "maturityState": attestation.maturity.value,
                        "evidence": attestation.evidence.public_dict(),
                    }
                )
            else:
                unresolved[requirement.capability_id] = requirement

        needed = set(unresolved)
        eligible: list[AdapterRoute] = []
        for adapter in sorted(adapters, key=lambda item: item.adapter_id):
            reasons = _adapter_rejection_reasons(adapter, needed, policy)
            adapter_ledger.append(
                {
                    "adapterId": adapter.adapter_id,
                    "status": "ELIGIBLE" if not reasons else "REJECTED",
                    "reasonCodes": reasons,
                    "provides": sorted(adapter.provides),
                    "maturityState": adapter.maturity.value,
                }
            )
            if not reasons:
                eligible.append(adapter)

        recurring_cost = 0.0
        user_burden = 0.0
        remaining_eligible = list(eligible)
        while needed and remaining_eligible:
            feasible: list[AdapterRoute] = []
            for adapter in remaining_eligible:
                if recurring_cost + adapter.recurring_cost > policy.max_recurring_cost:
                    _append_reason_once(
                        adapter_ledger,
                        adapter.adapter_id,
                        "CUMULATIVE_COST_EXCEEDS_POLICY",
                    )
                    continue
                if user_burden + adapter.user_burden > policy.max_user_burden:
                    _append_reason_once(
                        adapter_ledger,
                        adapter.adapter_id,
                        "CUMULATIVE_BURDEN_EXCEEDS_POLICY",
                    )
                    continue
                if needed.intersection(adapter.provides):
                    feasible.append(adapter)
            if not feasible:
                break
            feasible.sort(
                key=lambda adapter: (
                    -len(needed.intersection(adapter.provides)),
                    -MATURITY_RANK[adapter.maturity],
                    adapter.recurring_cost,
                    adapter.user_burden,
                    adapter.priority,
                    adapter.adapter_id,
                )
            )
            adapter = feasible[0]
            remaining_eligible.remove(adapter)
            covered = needed.intersection(adapter.provides)
            selected_adapters.append(adapter)
            recurring_cost += adapter.recurring_cost
            user_burden += adapter.user_burden
            needed.difference_update(covered)
            for capability_id in sorted(covered):
                decisions.append(
                    {
                        "requirementId": capability_id,
                        "state": "ADAPTER_ROUTE",
                        "selectedRoute": f"adapter:{adapter.adapter_id}",
                        "maturityState": adapter.maturity.value,
                        "evidence": adapter.evidence.public_dict(),
                        "fidelityEvidenceRef": adapter.fidelity_evidence_ref,
                    }
                )
            _set_adapter_selected(adapter_ledger, adapter.adapter_id)
        for item in adapter_ledger:
            if item["status"] == "ELIGIBLE":
                item["status"] = "ELIGIBLE_NOT_SELECTED"

        for capability_id in sorted(needed):
            requirement = unresolved[capability_id]
            decisions.append(
                {
                    "requirementId": capability_id,
                    "state": "PLATFORM_BOUNDARY",
                    "selectedRoute": "none",
                    "maturityState": MaturityState.DESIGNED.value,
                    "boundary": _boundary_language(platform, requirement),
                }
            )
            build_triggers.append(
                _stable_build_trigger(canonical.sha256, platform.platform_id, capability_id)
            )

    decisions.sort(key=lambda item: item["requirementId"])
    if not fidelity.accepted:
        result_state = "REJECT_DILUTION"
    elif build_triggers:
        result_state = "PLATFORM_BOUNDARY"
    else:
        all_proven = all(
            item["maturityState"] == MaturityState.READBACK_PROVEN.value for item in decisions
        )
        result_state = "ROUTE_READY_PROVEN" if all_proven else "ROUTE_READY_LOCAL"

    result: dict[str, Any] = {
        "schema": SCHEMA,
        "resultState": result_state,
        "executionState": "NOT_EXECUTED",
        "canonicalSource": {
            "sourceId": canonical.source_id,
            "version": canonical.version,
            "mediaType": canonical.media_type,
            "sha256": canonical.sha256,
        },
        "candidateSha256": fidelity.candidate_sha256,
        "fidelity": fidelity.to_dict(),
        "platform": {
            "platformId": platform.platform_id,
            "exactScope": platform.exact_scope,
            "discoveryRef": platform.discovery_ref,
        },
        "requirementDecisions": decisions,
        "adapterLedger": adapter_ledger,
        "selectedAdapters": [adapter.adapter_id for adapter in selected_adapters],
        "buildTriggers": build_triggers,
        "truthBoundary": {
            "canonicalPreserved": fidelity.accepted,
            "providerMutationPerformed": False,
            "runtimeExecutionClaimed": False,
            "platformConstraintsRemovedFromCanonicalSource": False,
            "statement": (
                "Canonical fidelity is evaluated independently from platform capability. "
                "Unresolved platform requirements remain explicit build triggers."
            ),
        },
    }
    result["receiptSha256"] = hashlib.sha256(_canonical_json(result).encode("utf-8")).hexdigest()
    return result


def _append_reason_once(ledger: list[dict[str, Any]], adapter_id: str, reason: str) -> None:
    for item in ledger:
        if item["adapterId"] == adapter_id:
            item["status"] = "REJECTED"
            if reason not in item["reasonCodes"]:
                item["reasonCodes"].append(reason)
            return


def _set_adapter_selected(ledger: list[dict[str, Any]], adapter_id: str) -> None:
    for item in ledger:
        if item["adapterId"] == adapter_id:
            item["status"] = "SELECTED"
            return


def _evidence_from_payload(payload: Mapping[str, Any]) -> MaturityEvidence:
    return MaturityEvidence(
        source_ref=_required_string(payload.get("sourceRef", ""), "sourceRef"),
        test_ref=_required_string(payload.get("testRef", ""), "testRef"),
        registration_ref=_required_string(
            payload.get("registrationRef", ""), "registrationRef"
        ),
        authorization_ref=_required_string(
            payload.get("authorizationRef", ""), "authorizationRef"
        ),
        readiness_ref=_required_string(payload.get("readinessRef", ""), "readinessRef"),
        deployment_ref=_required_string(
            payload.get("deploymentRef", ""), "deploymentRef"
        ),
        readback_ref=_required_string(payload.get("readbackRef", ""), "readbackRef"),
        rollback_ref=_required_string(payload.get("rollbackRef", ""), "rollbackRef"),
    )


def isolate_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise FidelityError("input must be a JSON object")
    source_payload = _mapping(payload.get("canonicalSource"), "canonicalSource")
    invariant_payloads = source_payload.get("protectedInvariants", [])
    if not isinstance(invariant_payloads, list):
        raise FidelityError("protectedInvariants must be an array")
    canonical = CanonicalSource(
        source_id=_required_string(source_payload.get("sourceId", ""), "sourceId"),
        version=_required_string(source_payload.get("version", ""), "version"),
        media_type=_required_string(source_payload.get("mediaType", ""), "mediaType"),
        content=_required_string(source_payload.get("content"), "canonicalSource.content"),
        fidelity_mode=_enum(FidelityMode, source_payload.get("fidelityMode"), "fidelityMode"),
        protected_invariants=tuple(
            ProtectedInvariant(
                invariant_id=_required_string(
                    _mapping(item, "protectedInvariant").get("invariantId", ""),
                    "invariantId",
                ),
                kind=_enum(
                    InvariantKind,
                    _mapping(item, "protectedInvariant").get("kind"),
                    "invariant kind",
                ),
                selector=_required_string(
                    _mapping(item, "protectedInvariant").get("selector", ""), "selector"
                ),
                minimum_occurrences=int(
                    _integer(
                        _mapping(item, "protectedInvariant").get("minimumOccurrences", 1),
                        "minimumOccurrences",
                    )
                ),
            )
            for item in invariant_payloads
        ),
        expected_sha256=_required_string(
            source_payload.get("expectedSha256", ""), "expectedSha256"
        ),
    )
    platform_payload = _mapping(payload.get("platformProfile"), "platformProfile")
    capability_payloads = platform_payload.get("capabilities", [])
    if not isinstance(capability_payloads, list):
        raise FidelityError("platform capabilities must be an array")
    platform = PlatformProfile(
        platform_id=_required_string(platform_payload.get("platformId", ""), "platformId"),
        exact_scope=_required_string(platform_payload.get("exactScope", ""), "exactScope"),
        discovery_ref=_required_string(
            platform_payload.get("discoveryRef", ""), "discoveryRef"
        ),
        capabilities=tuple(
            CapabilityAttestation(
                capability_id=_required_string(
                    _mapping(item, "platform capability").get("capabilityId", ""),
                    "capabilityId",
                ),
                maturity=_enum(
                    MaturityState,
                    _mapping(item, "platform capability").get("maturityState"),
                    "maturityState",
                ),
                evidence=_evidence_from_payload(
                    _mapping(_mapping(item, "platform capability").get("evidence", {}), "evidence")
                ),
            )
            for item in capability_payloads
        ),
    )
    requirement_payloads = payload.get("requirements", [])
    if not isinstance(requirement_payloads, list):
        raise FidelityError("requirements must be an array")
    requirements = tuple(
        CapabilityRequirement(
            capability_id=_required_string(
                _mapping(item, "requirement").get("capabilityId", ""), "capabilityId"
            ),
            description=_required_string(
                _mapping(item, "requirement").get("description", ""), "description"
            ),
            platform_hard_limit=_boolean(
                _mapping(item, "requirement").get("platformHardLimit", False),
                "platformHardLimit",
            ),
            boundary_evidence_ref=_required_string(
                _mapping(item, "requirement").get("boundaryEvidenceRef", ""),
                "boundaryEvidenceRef",
            ),
        )
        for item in requirement_payloads
    )
    adapter_payloads = payload.get("adapterRoutes", [])
    if not isinstance(adapter_payloads, list):
        raise FidelityError("adapterRoutes must be an array")
    adapters: list[AdapterRoute] = []
    for item in adapter_payloads:
        adapter_payload = _mapping(item, "adapter route")
        provides = adapter_payload.get("provides", [])
        if not isinstance(provides, list) or not all(isinstance(value, str) for value in provides):
            raise FidelityError("adapter provides must be an array of strings")
        adapters.append(
            AdapterRoute(
                adapter_id=_required_string(adapter_payload.get("adapterId", ""), "adapterId"),
                provides=tuple(provides),
                maturity=_enum(
                    MaturityState, adapter_payload.get("maturityState"), "maturityState"
                ),
                evidence=_evidence_from_payload(
                    _mapping(adapter_payload.get("evidence", {}), "evidence")
                ),
                authority_ceiling=_required_string(
                    adapter_payload.get("authorityCeiling", "A1"), "authorityCeiling"
                ),
                recurring_cost=_number(
                    adapter_payload.get("recurringCost", 0.0), "recurringCost"
                ),
                user_burden=_number(
                    adapter_payload.get("userBurden", 0.0), "userBurden"
                ),
                external_effect_required=_boolean(
                    adapter_payload.get("externalEffectRequired", False),
                    "externalEffectRequired",
                ),
                preserves_canonical_source=_boolean(
                    adapter_payload.get("preservesCanonicalSource", True),
                    "preservesCanonicalSource",
                ),
                fidelity_evidence_ref=_required_string(
                    adapter_payload.get("fidelityEvidenceRef", ""), "fidelityEvidenceRef"
                ),
                priority=_integer(adapter_payload.get("priority", 100), "priority"),
            )
        )
    policy_payload = _mapping(payload.get("policy", {}), "policy")
    policy = IsolationPolicy(
        available_authority=_required_string(
            policy_payload.get("availableAuthority", "A1"), "availableAuthority"
        ),
        max_recurring_cost=_number(
            policy_payload.get("maxRecurringCost", 0.0), "maxRecurringCost"
        ),
        max_user_burden=_number(
            policy_payload.get("maxUserBurden", 0.0), "maxUserBurden"
        ),
        allow_external_effects=_boolean(
            policy_payload.get("allowExternalEffects", False), "allowExternalEffects"
        ),
    )
    return isolate_constraints(
        canonical=canonical,
        candidate=_required_string(payload.get("candidateContent"), "candidateContent"),
        platform=platform,
        requirements=requirements,
        adapters=tuple(adapters),
        policy=policy,
    )


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise FidelityError(f"{name} must be an object")
    return value


def _required_string(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise FidelityError(f"{name} must be a string")
    return value


def _boolean(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise FidelityError(f"{name} must be a boolean")
    return value


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FidelityError(f"{name} must be a number")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise FidelityError(f"{name} must be finite")
    return numeric


def _integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise FidelityError(f"{name} must be an integer")
    return value


def _enum(enum_type: type[StrEnum], value: Any, name: str) -> Any:
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        allowed = ",".join(item.value for item in enum_type)
        raise FidelityError(f"{name} must be one of: {allowed}") from exc


__all__ = [
    "AdapterRoute",
    "CanonicalSource",
    "CapabilityAttestation",
    "CapabilityRequirement",
    "FidelityDecision",
    "FidelityError",
    "FidelityMode",
    "InvariantKind",
    "IsolationPolicy",
    "MaturityEvidence",
    "MaturityState",
    "PlatformProfile",
    "ProtectedInvariant",
    "SCHEMA",
    "evaluate_fidelity",
    "isolate_constraints",
    "isolate_payload",
]

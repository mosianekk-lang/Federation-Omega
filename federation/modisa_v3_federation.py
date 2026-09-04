"""Additive, authority-safe MODISA v3 capability propagation for Federation Omega.

The compiler turns one content-addressed capability manifest and a receiver
profile into a complete per-capability adoption plan.  It never executes a
provider action, copies credentials, or promotes source evidence into runtime
proof.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from pathlib import Path
from typing import Any


class ManifestError(ValueError):
    """Raised when a propagation manifest violates a Federation invariant."""


class Authority(IntEnum):
    A0 = 0
    A1 = 1
    A2 = 2
    A3 = 3


class Disposition(StrEnum):
    ADOPT = "ADOPT"
    ADAPT = "ADAPT"
    ALREADY_PRESENT = "ALREADY_PRESENT"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    HELD = "HELD"
    REJECTED = "REJECTED"


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ReceiverProfile:
    receiver_id: str
    domains: frozenset[str]
    runtimes: frozenset[str]
    authority_ceiling: Authority = Authority.A1
    existing_capabilities: frozenset[str] = frozenset()
    privacy_ceiling: str = "INTERNAL"

    def __post_init__(self) -> None:
        if not self.receiver_id.strip():
            raise ManifestError("receiver_id is required")
        if not self.domains:
            raise ManifestError("receiver domains are required")


class ModisaFederationCompiler:
    """Validate and compile a complete, non-dilutive receiver projection."""

    SCHEMA = "FEDOMEGA-MODISA-V3-PROPAGATION-1"

    def __init__(self, manifest: dict[str, Any]) -> None:
        self.manifest = manifest
        self._validate()

    @classmethod
    def from_path(cls, path: Path | str) -> ModisaFederationCompiler:
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def _validate(self) -> None:
        if self.manifest.get("schema") != self.SCHEMA:
            raise ManifestError("unsupported MODISA Federation schema")
        if self.manifest.get("propagation_mode") != "ADDITIVE_POINTER_PLUS_RECEIVER_ADAPTER":
            raise ManifestError("propagation must be additive")
        truth = self.manifest.get("truth_boundary", {})
        for invariant in (
            "credentials_inherited",
            "effect_authority_inherited",
            "provider_runtime_claimed",
            "hidden_chat_access_claimed",
        ):
            if truth.get(invariant) is not False:
                raise ManifestError(f"truth boundary must explicitly disable {invariant}")
        source = self.manifest.get("source", {})
        digest = source.get("tree_sha256", "")
        if not isinstance(digest, str) or not digest.startswith("sha256:") or len(digest) != 71:
            raise ManifestError("source tree requires a complete SHA-256")
        capabilities = self.manifest.get("capabilities")
        if not isinstance(capabilities, list) or not capabilities:
            raise ManifestError("capabilities are required")
        ids = [item.get("id") for item in capabilities]
        if any(not isinstance(item, str) or not item for item in ids):
            raise ManifestError("every capability requires an id")
        if len(ids) != len(set(ids)):
            raise ManifestError("duplicate capability id")
        known = set(ids)
        for item in capabilities:
            if item.get("authority") not in Authority.__members__:
                raise ManifestError(f"invalid authority for {item['id']}")
            if not item.get("proof_requirements"):
                raise ManifestError(f"proof requirements missing for {item['id']}")
            missing = set(item.get("dependencies", ())) - known
            if missing:
                raise ManifestError(f"unknown dependencies for {item['id']}: {sorted(missing)}")
            if item["id"] in item.get("dependencies", ()):
                raise ManifestError(f"self dependency for {item['id']}")
        expected_count = self.manifest.get("capability_count")
        if expected_count != len(capabilities):
            raise ManifestError("capability count mismatch")
        self._assert_acyclic()

    def _assert_acyclic(self) -> None:
        graph = {item["id"]: tuple(item.get("dependencies", ())) for item in self.manifest["capabilities"]}
        active: set[str] = set()
        complete: set[str] = set()

        def visit(capability_id: str) -> None:
            if capability_id in complete:
                return
            if capability_id in active:
                raise ManifestError("capability dependency cycle")
            active.add(capability_id)
            for dependency in graph[capability_id]:
                visit(dependency)
            active.remove(capability_id)
            complete.add(capability_id)

        for capability_id in graph:
            visit(capability_id)

    @property
    def manifest_sha256(self) -> str:
        return _digest(self.manifest)

    def verify_source_tree(self, repository_root: Path | str) -> dict[str, Any]:
        root = Path(repository_root)
        source_root = root / self.manifest["source"]["root"]
        if not source_root.is_dir():
            raise ManifestError("MODISA source root is missing")
        paths = sorted(path for path in source_root.rglob("*") if path.is_file())
        if any(path.is_symlink() for path in paths):
            raise ManifestError("source tree may not contain symlinks")
        material = b"".join(
            hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii")
            + b"  "
            + path.relative_to(root).as_posix().encode("utf-8")
            + b"\n"
            for path in paths
        )
        observed = "sha256:" + hashlib.sha256(material).hexdigest()
        expected = self.manifest["source"]["tree_sha256"]
        if observed != expected:
            raise ManifestError("MODISA source tree hash mismatch")
        if len(paths) != self.manifest["source"]["file_count"]:
            raise ManifestError("MODISA source file count mismatch")
        return {
            "state": "SOURCE_TREE_VERIFIED",
            "file_count": len(paths),
            "tree_sha256": observed,
            "provider_effect": False,
        }

    def compile(self, receiver: ReceiverProfile) -> dict[str, Any]:
        decisions: list[dict[str, Any]] = []
        for capability in self.manifest["capabilities"]:
            capability_id = capability["id"]
            required_domains = frozenset(capability.get("domains", ()))
            required_runtimes = frozenset(capability.get("runtimes", ()))
            required_authority = Authority[capability["authority"]]
            universal = bool(capability.get("universal"))
            if capability_id in receiver.existing_capabilities:
                disposition = Disposition.ALREADY_PRESENT
                reason = "receiver reports an existing equivalent; regression proof is still required"
            elif not universal and required_domains.isdisjoint(receiver.domains):
                disposition = Disposition.NOT_APPLICABLE
                reason = "capability domain is outside the receiver role"
            elif required_authority > receiver.authority_ceiling:
                disposition = Disposition.HELD
                reason = "receiver authority ceiling is lower than the capability requirement"
            elif not required_runtimes.issubset(receiver.runtimes):
                disposition = Disposition.ADAPT
                reason = "receiver-native runtime adapter and semantic equivalence proof are required"
            else:
                disposition = Disposition.ADOPT
                reason = "receiver can consume the capability contract without authority expansion"
            decisions.append(
                {
                    "capability_id": capability_id,
                    "disposition": disposition.value,
                    "reason": reason,
                    "source_modules": capability["source_modules"],
                    "dependencies": capability.get("dependencies", []),
                    "proof_requirements": capability["proof_requirements"],
                    "effect_authority_inherited": False,
                    "credentials_inherited": False,
                }
            )
        counts = {state.value: 0 for state in Disposition}
        for decision in decisions:
            counts[decision["disposition"]] += 1
        body = {
            "schema": "FEDOMEGA-MODISA-V3-RECEIVER-PLAN-1",
            "manifest_sha256": self.manifest_sha256,
            "source_tree_sha256": self.manifest["source"]["tree_sha256"],
            "receiver_id": receiver.receiver_id,
            "receiver_authority_ceiling": receiver.authority_ceiling.name,
            "privacy_ceiling": receiver.privacy_ceiling,
            "capability_count": len(decisions),
            "complete_coverage": len(decisions) == self.manifest["capability_count"],
            "counts": counts,
            "decisions": decisions,
            "runtime_promotion": "RECEIVER_NATIVE_TEST_READBACK_ROLLBACK_REQUIRED",
            "effect_authority_inherited": False,
            "credentials_inherited": False,
        }
        return {**body, "plan_sha256": _digest(body)}

    @staticmethod
    def verify_plan(plan: dict[str, Any]) -> None:
        claimed = plan.get("plan_sha256")
        body = {key: value for key, value in plan.items() if key != "plan_sha256"}
        if claimed != _digest(body):
            raise ManifestError("receiver plan hash mismatch")
        decisions = plan.get("decisions", [])
        if plan.get("capability_count") != len(decisions) or not plan.get("complete_coverage"):
            raise ManifestError("receiver plan is incomplete")
        if plan.get("effect_authority_inherited") or plan.get("credentials_inherited"):
            raise ManifestError("receiver plan transfers prohibited authority")
        ids = [item.get("capability_id") for item in decisions]
        if len(ids) != len(set(ids)):
            raise ManifestError("receiver plan duplicates a capability")

    def compile_fleet(self, receivers: list[ReceiverProfile]) -> dict[str, Any]:
        ids = [receiver.receiver_id for receiver in receivers]
        if len(ids) != len(set(ids)):
            raise ManifestError("duplicate receiver id")
        plans = [self.compile(receiver) for receiver in receivers]
        for plan in plans:
            self.verify_plan(plan)
        body = {
            "schema": "FEDOMEGA-MODISA-V3-FLEET-PLAN-1",
            "manifest_sha256": self.manifest_sha256,
            "source_tree_sha256": self.manifest["source"]["tree_sha256"],
            "receiver_count": len(plans),
            "capability_receiver_pairs": sum(plan["capability_count"] for plan in plans),
            "plans": plans,
            "propagation_state": "SOURCE_REGISTERED_RECEIVER_ACTIVATION_PROOF_REQUIRED",
            "provider_effect": False,
        }
        return {**body, "fleet_sha256": _digest(body)}

    def receiver_profiles(self) -> list[ReceiverProfile]:
        profiles = self.manifest.get("receiver_profiles")
        if not isinstance(profiles, list) or not profiles:
            raise ManifestError("receiver profiles are required")
        return [
            ReceiverProfile(
                receiver_id=item["receiver_id"],
                domains=frozenset(item["domains"]),
                runtimes=frozenset(item["runtimes"]),
                authority_ceiling=Authority[item.get("authority_ceiling", "A1")],
                existing_capabilities=frozenset(item.get("existing_capabilities", ())),
                privacy_ceiling=item.get("privacy_ceiling", "INTERNAL"),
            )
            for item in profiles
        ]

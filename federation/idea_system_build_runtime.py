from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Protocol, Sequence

from alpha_omega_v30.capability_market import CapabilityRegistry
from alpha_omega_v30.sandbox_fleet import OperationalSandbox, SandboxTask
from federation.idea_to_system_compiler import (
    CapabilityRecord,
    IdeaSystemPlan,
    compile_idea_to_system,
)

_SCHEMA = "FEDERATION-IDEA-SYSTEM-BUILD-RUNTIME-V1"
_STABLE_EVIDENCE = frozenset({
    "VERIFIED",
    "VERIFIED_CURRENT",
    "CURRENT_STABLE",
    "SOURCE_VERIFIED",
    "OPERATIONAL_VERIFIED",
    "ALREADY_STRONG",
})


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _tag(value: str) -> str:
    out = []
    last_sep = False
    for ch in str(value).upper():
        if ch.isalnum():
            out.append(ch)
            last_sep = False
        elif not last_sep:
            out.append("_")
            last_sep = True
    return "".join(out).strip("_")


def _safe_path(raw: str) -> str:
    path = PurePosixPath(raw)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ValueError(f"unsafe workspace path: {raw}")
    return str(path)


@dataclass(frozen=True, slots=True)
class CapabilityQualification:
    fingerprint: str
    evidence_state: str
    proof_refs: tuple[str, ...] = ()

    @property
    def reusable(self) -> bool:
        return _tag(self.evidence_state) in _STABLE_EVIDENCE


class CapabilityRegistryDiscovery:
    """Read-only adapter from the existing Alpha-Omega capability market.

    Registry presence never implies maturity. A fingerprint must be explicitly
    qualified before Idea->System may treat it as reusable.
    """

    def __init__(
        self,
        registry: CapabilityRegistry,
        *,
        qualifications: Sequence[CapabilityQualification] = (),
        aliases: Mapping[str, Sequence[str]] | None = None,
    ) -> None:
        self.registry = registry
        self.qualifications = {item.fingerprint: item for item in qualifications}
        self.aliases = {
            str(key): tuple(_tag(value) for value in values)
            for key, values in dict(aliases or {}).items()
        }

    def _raw_records(self) -> tuple[dict[str, Any], ...]:
        path = Path(self.registry.path)
        if not path.exists():
            return ()
        return tuple(
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )

    def records(self) -> tuple[CapabilityRecord, ...]:
        result: list[CapabilityRecord] = []
        for record in self._raw_records():
            spec = dict(record["spec"])
            fingerprint = str(record["fingerprint"])
            qualification = self.qualifications.get(fingerprint)
            tags = {
                _tag(spec.get("capability_id", "")),
                *(_tag(item) for item in spec.get("interfaces", ())),
                *self.aliases.get(str(spec.get("capability_id", "")), ()),
            }
            tags.discard("")
            result.append(
                CapabilityRecord(
                    capability_id=str(spec["capability_id"]),
                    name=str(spec["purpose"]),
                    tags=tuple(sorted(tags)),
                    evidence_state=qualification.evidence_state if qualification else "CANDIDATE",
                    reusable=bool(qualification and qualification.reusable),
                    provider_live=False,
                    cost_class="UNKNOWN",
                )
            )
        return tuple(sorted(result, key=lambda item: item.capability_id))

    def snapshot(self) -> dict[str, Any]:
        records = self.records()
        return {
            "schema": "FEDERATION-CAPABILITY-DISCOVERY-SNAPSHOT-V1",
            "record_count": len(records),
            "qualified_reusable_count": sum(1 for item in records if item.reusable),
            "capability_ids": [item.capability_id for item in records],
            "registry_state": self.registry.verify(),
            "truth_boundary": {
                "registry_presence_is_runtime_proof": False,
                "qualification_is_provider_authority": False,
                "discovery_grants_effect_authority": False,
            },
        }


@dataclass(frozen=True, slots=True)
class BuildCandidate:
    candidate_id: str
    files: Mapping[str, str]
    validation_command: tuple[str, ...]
    export_paths: tuple[str, ...] = ()
    rationale: str = ""

    def normalized_files(self) -> dict[str, str]:
        if not self.candidate_id.strip():
            raise ValueError("candidate_id is required")
        if not self.validation_command:
            raise ValueError("validation_command is required")
        result: dict[str, str] = {}
        for raw, content in dict(self.files).items():
            path = _safe_path(raw)
            if path in result:
                raise ValueError(f"duplicate workspace path: {path}")
            result[path] = str(content)
        if not result:
            raise ValueError("candidate files are required")
        for path in self.export_paths:
            _safe_path(path)
        return dict(sorted(result.items()))

    @property
    def digest(self) -> str:
        return _digest({
            "candidate_id": self.candidate_id,
            "files": self.normalized_files(),
            "validation_command": list(self.validation_command),
            "export_paths": list(self.export_paths),
            "rationale": self.rationale,
        })


class BuildGenerator(Protocol):
    def propose(
        self,
        plan: IdeaSystemPlan,
        current_files: Mapping[str, str],
        failure_receipt: Mapping[str, Any] | None,
    ) -> BuildCandidate:
        ...


class PersistentWorkspace:
    """Append-only logical workspace over disposable execution sandboxes."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _append(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        events = self._events()
        previous_hash = events[-1]["event_hash"] if events else "GENESIS"
        event = {"previous_hash": previous_hash, "payload": dict(payload)}
        event["event_hash"] = _digest(event)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
        readback = self._events()[-1]
        if readback != event:
            raise IOError("workspace event readback mismatch")
        return event

    def verify(self) -> dict[str, Any]:
        previous = "GENESIS"
        staged: set[str] = set()
        promoted: set[str] = set()
        current: str | None = None
        count = 0
        for event in self._events():
            claimed = event.get("event_hash")
            unsigned = {"previous_hash": event.get("previous_hash"), "payload": event.get("payload")}
            if event.get("previous_hash") != previous or _digest(unsigned) != claimed:
                return {"valid": False, "events": count, "head": previous, "current_revision": current}
            payload = dict(event["payload"])
            kind = payload.get("kind")
            revision_id = str(payload.get("revision_id") or "")
            if kind == "STAGE":
                if (
                    not revision_id
                    or revision_id in staged
                    or payload.get("parent_revision") != current
                ):
                    return {"valid": False, "events": count, "head": previous, "current_revision": current}
                staged.add(revision_id)
            elif kind == "PROMOTE":
                if revision_id not in staged or revision_id in promoted:
                    return {"valid": False, "events": count, "head": previous, "current_revision": current}
                promoted.add(revision_id)
                current = revision_id
            else:
                return {"valid": False, "events": count, "head": previous, "current_revision": current}
            previous = str(claimed)
            count += 1
        return {"valid": True, "events": count, "head": previous, "current_revision": current}

    def current_revision(self) -> str | None:
        return self.verify()["current_revision"]

    def current_files(self) -> dict[str, str]:
        current = self.current_revision()
        if current is None:
            return {}
        staged_files: dict[str, str] | None = None
        artifact_overrides: dict[str, str] = {}
        for event in self._events():
            payload = dict(event["payload"])
            if payload.get("kind") == "STAGE" and payload.get("revision_id") == current:
                staged_files = dict(payload["files"])
            elif payload.get("kind") == "PROMOTE" and payload.get("revision_id") == current:
                artifact_overrides = dict(payload.get("artifact_text", {}))
        if staged_files is None:
            raise IOError("promoted workspace revision has no stage event")
        staged_files.update(artifact_overrides)
        return dict(sorted(staged_files.items()))

    def stage(self, *, plan_digest: str, candidate: BuildCandidate, parent_revision: str | None) -> str:
        files = candidate.normalized_files()
        revision_id = "WS-" + _digest({
            "plan_digest": plan_digest,
            "candidate_digest": candidate.digest,
            "parent_revision": parent_revision,
            "files": files,
        })[:20].upper()
        self._append({
            "kind": "STAGE",
            "revision_id": revision_id,
            "parent_revision": parent_revision,
            "plan_digest": plan_digest,
            "candidate_digest": candidate.digest,
            "files": files,
        })
        state = self.verify()
        if not state["valid"]:
            raise IOError("workspace stage verification failed")
        return revision_id

    def promote(self, *, revision_id: str, sandbox_receipt: Mapping[str, Any]) -> dict[str, Any]:
        if sandbox_receipt.get("status") != "PASS":
            raise ValueError("only a passing sandbox candidate may be promoted")
        artifact_text: dict[str, str] = {}
        for raw_path, artifact in dict(sandbox_receipt.get("artifacts", {})).items():
            path = _safe_path(raw_path)
            text = dict(artifact).get("text")
            if text is not None:
                artifact_text[path] = str(text)
        event = self._append({
            "kind": "PROMOTE",
            "revision_id": revision_id,
            "sandbox_result_hash": sandbox_receipt.get("result_hash"),
            "sandbox_ledger_entry_hash": sandbox_receipt.get("ledger_entry_hash"),
            "artifact_text": dict(sorted(artifact_text.items())),
        })
        state = self.verify()
        if not state["valid"] or state["current_revision"] != revision_id:
            raise IOError("workspace promotion readback mismatch")
        return event


@dataclass(frozen=True, slots=True)
class BuildRuntimeReceipt:
    plan_digest: str
    attempts: int
    candidate_digests: tuple[str, ...]
    final_status: str
    promoted_revision: str | None
    workspace_state: Mapping[str, Any]
    discovery_snapshot: Mapping[str, Any]
    sandbox_receipts: tuple[Mapping[str, Any], ...]
    provider_effect_authorized: bool = False
    external_effects: int = 0

    def canonical_mapping(self) -> dict[str, Any]:
        return {
            "schema": _SCHEMA,
            "plan_digest": self.plan_digest,
            "attempts": self.attempts,
            "candidate_digests": list(self.candidate_digests),
            "final_status": self.final_status,
            "promoted_revision": self.promoted_revision,
            "workspace_state": dict(self.workspace_state),
            "discovery_snapshot": dict(self.discovery_snapshot),
            "sandbox_receipts": [dict(item) for item in self.sandbox_receipts],
            "provider_effect_authorized": self.provider_effect_authorized,
            "external_effects": self.external_effects,
            "truth_boundary": {
                "logical_workspace_is_vm_or_container_persistence": False,
                "source_build_is_deployment": False,
                "local_generation_grants_provider_authority": False,
                "sandbox_success_is_user_value_proof": False,
            },
        }

    @property
    def digest(self) -> str:
        return _digest(self.canonical_mapping())


class IdeaSystemBuildRuntime:
    def __init__(
        self,
        discovery: CapabilityRegistryDiscovery,
        workspace: PersistentWorkspace,
        sandbox: OperationalSandbox,
    ) -> None:
        self.discovery = discovery
        self.workspace = workspace
        self.sandbox = sandbox

    def plan(self, idea: str, *, source_frontier: str, domain_hint: str | None = None) -> IdeaSystemPlan:
        return compile_idea_to_system(
            idea,
            self.discovery.records(),
            source_frontier=source_frontier,
            domain_hint=domain_hint,
        )

    def build(self, plan: IdeaSystemPlan, generator: BuildGenerator, *, max_attempts: int = 2) -> BuildRuntimeReceipt:
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        current_files = self.workspace.current_files()
        seen: set[str] = set()
        candidate_digests: list[str] = []
        sandbox_receipts: list[Mapping[str, Any]] = []
        failure: Mapping[str, Any] | None = None
        promoted_revision: str | None = None
        final_status = "FAILED"

        for attempt in range(1, max_attempts + 1):
            candidate = generator.propose(plan, current_files, failure)
            digest = candidate.digest
            if digest in seen:
                final_status = "UNCHANGED_RETRY_BLOCKED"
                break
            seen.add(digest)
            candidate_digests.append(digest)

            merged = dict(current_files)
            merged.update(candidate.normalized_files())
            staged = BuildCandidate(
                candidate_id=candidate.candidate_id,
                files=merged,
                validation_command=candidate.validation_command,
                export_paths=candidate.export_paths,
                rationale=candidate.rationale,
            )
            revision_id = self.workspace.stage(
                plan_digest=plan.digest(),
                candidate=staged,
                parent_revision=self.workspace.current_revision(),
            )
            result = self.sandbox.run(
                SandboxTask(
                    task_id=f"{plan.mission_ir.mission_id}-attempt-{attempt}",
                    command=staged.validation_command,
                    input_files=staged.normalized_files(),
                    export_paths=staged.export_paths,
                )
            )
            sandbox_receipts.append(result)
            if all((
                result.get("status") == "PASS",
                result.get("execution_verified") is True,
                result.get("readback_verified") is True,
                result.get("persistence_verified") is True,
                result.get("rollback_verified") is True,
            )):
                self.workspace.promote(revision_id=revision_id, sandbox_receipt=result)
                promoted_revision = revision_id
                current_files = self.workspace.current_files()
                final_status = "VERIFIED_BUILD_CANDIDATE"
                break
            failure = result

        return BuildRuntimeReceipt(
            plan_digest=plan.digest(),
            attempts=len(candidate_digests),
            candidate_digests=tuple(candidate_digests),
            final_status=final_status,
            promoted_revision=promoted_revision,
            workspace_state=self.workspace.verify(),
            discovery_snapshot=self.discovery.snapshot(),
            sandbox_receipts=tuple(sandbox_receipts),
        )


__all__ = [
    "BuildCandidate",
    "BuildGenerator",
    "BuildRuntimeReceipt",
    "CapabilityQualification",
    "CapabilityRegistryDiscovery",
    "IdeaSystemBuildRuntime",
    "PersistentWorkspace",
]

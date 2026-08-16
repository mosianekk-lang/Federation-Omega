from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Tuple


class RestoreConformanceState(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    REPAIR_REQUIRED = "REPAIR_REQUIRED"


@dataclass(frozen=True)
class RestoreAttestation:
    """What a destination session actually restored and resumed.

    This is deliberately provider-neutral. External adapters may persist the attestation
    in Kim Dataverse/Drive, a database, or another governed store. It never grants
    authority; it only reports observed restore state for independent comparison.
    """

    namespace_key: str
    generation_id: str
    handoff_id: str
    destination_session_key: str
    checkpoint_fingerprint: str
    operating_profile_id: str
    governance_capsule_ref: str
    restored_objective: str
    restored_next_action: str
    active_systems: Tuple[str, ...] = field(default_factory=tuple)
    live_bible_ref: str = ""
    playbook_ref: str = ""
    execution_posture: str = ""
    reconcile_not_rebuild: bool = False
    conversation_exhaustion_guard: bool = False
    continuous_write_ahead_checkpoint: bool = False
    empirical_learning: bool = False
    checkpoint_policy: str = ""
    migration_policy: str = ""
    learning_capture_scope: str = ""
    delta_checked: bool = False
    resume_started: bool = False
    observed_state: str = "RESTORED"
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["active_systems"] = list(self.active_systems)
        return payload


@dataclass(frozen=True)
class RestoreFinding:
    drift_class: str
    severity: str
    expected: Any
    observed: Any
    repair: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RestoreAssuranceEngine:
    """Compare intended restore state with destination attestation and emit repair.

    Identity and checkpoint fields remain anchored to the immutable generation. Mutable
    semantic fields (objective, exact next action, required systems and Live Bible
    pointer) may be superseded only by an explicitly supplied, already-verified
    ``current_state_override``. This prevents a correct delta-first restore from being
    misclassified as drift while also preventing a destination from self-authorising its
    own semantic changes.

    Ω4.7 additionally treats conversation-exhaustion protection and empirical-learning
    controls as restore-critical behavioural state. A destination cannot be certified as
    fully conformed if it restores the work but silently drops the guard or playbook policy.
    """

    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    DELTA_MUTABLE_FIELDS = (
        "restored_objective",
        "restored_next_action",
        "required_systems",
        "live_bible_ref",
        "playbook_ref",
    )

    @staticmethod
    def contract(expected_restore: Dict[str, Any]) -> Dict[str, Any]:
        profile = expected_restore.get("operating_profile") or {}
        governance = expected_restore.get("governance") or {}
        contract = {
            "namespace_key": expected_restore.get("namespace_key", ""),
            "generation_id": expected_restore.get("generation_id", ""),
            "handoff_id": expected_restore.get("handoff_id", ""),
            "checkpoint_fingerprint": expected_restore.get("checkpoint_fingerprint", ""),
            "operating_profile_id": profile.get("profile_id", ""),
            "governance_capsule_ref": governance.get("notes", ""),
            "restored_objective": governance.get("objective", ""),
            "restored_next_action": governance.get("exact_next_action", ""),
            "required_systems": list(profile.get("active_systems") or []),
            "live_bible_ref": profile.get("live_bible_ref", ""),
            "playbook_ref": profile.get("playbook_ref", ""),
            "execution_posture": profile.get("execution_posture", ""),
            "reconcile_not_rebuild": bool(profile.get("reconcile_not_rebuild", False)),
            "conversation_exhaustion_guard": bool(
                profile.get("conversation_exhaustion_guard", False)
            ),
            "continuous_write_ahead_checkpoint": bool(
                profile.get("continuous_write_ahead_checkpoint", False)
            ),
            "empirical_learning": bool(profile.get("empirical_learning", False)),
            "checkpoint_policy": profile.get("checkpoint_policy", ""),
            "migration_policy": profile.get("migration_policy", ""),
            "learning_capture_scope": profile.get("learning_capture_scope", ""),
            "delta_check_required": True,
            "resume_required_when_unlocked": not bool(
                expected_restore.get("consequential_action_locked", False)
                or expected_restore.get("preview_required", False)
            ),
            "semantic_source": "IMMUTABLE_GENERATION",
        }
        override = expected_restore.get("current_state_override") or {}
        if override:
            if not bool(override.get("verified", False)):
                raise ValueError(
                    "current_state_override must be independently verified before assurance use"
                )
            for name in RestoreAssuranceEngine.DELTA_MUTABLE_FIELDS:
                if name in override:
                    value = override[name]
                    contract[name] = list(value) if name == "required_systems" else value
            contract["semantic_source"] = str(
                override.get("source", "VERIFIED_CURRENT_CANONICAL_DELTA")
            )
            contract["semantic_source_ref"] = str(override.get("source_ref", ""))
        return contract

    @classmethod
    def assess(
        cls,
        expected_restore: Dict[str, Any],
        observed: RestoreAttestation,
    ) -> Dict[str, Any]:
        expected = cls.contract(expected_restore)
        findings: List[RestoreFinding] = []

        def exact(name: str, obs: Any, repair: str, severity: str = cls.CRITICAL) -> None:
            exp = expected.get(name)
            if exp != obs:
                findings.append(
                    RestoreFinding(name.upper() + "_DRIFT", severity, exp, obs, repair)
                )

        exact(
            "namespace_key",
            observed.namespace_key,
            "Resolve the exact namespace; do not use recency or semantic guessing.",
        )
        exact(
            "generation_id",
            observed.generation_id,
            "Reload the exact active verified generation before continuing.",
        )
        exact(
            "handoff_id",
            observed.handoff_id,
            "Rebind to the handoff referenced by the verified generation.",
        )
        exact(
            "checkpoint_fingerprint",
            observed.checkpoint_fingerprint,
            "Re-read the checkpoint and reject stale or mismatched state.",
        )
        exact(
            "operating_profile_id",
            observed.operating_profile_id,
            "Reapply the generation-bound Operating Profile.",
        )
        exact(
            "restored_objective",
            observed.restored_objective,
            "Restore the currently verified objective; do not invent or backslide from a valid post-checkpoint delta.",
        )
        exact(
            "restored_next_action",
            observed.restored_next_action,
            "Restore the currently verified exact next action; reconcile rather than invent a new plan.",
        )
        exact(
            "execution_posture",
            observed.execution_posture,
            "Reapply EXECUTE→VERIFY→READBACK or the bound profile posture.",
        )
        exact(
            "reconcile_not_rebuild",
            observed.reconcile_not_rebuild,
            "Stop broad reconstruction and run delta-first reconciliation.",
        )
        exact(
            "conversation_exhaustion_guard",
            observed.conversation_exhaustion_guard,
            "Reactivate the Conversation Exhaustion Guard before resuming substantive work.",
        )
        exact(
            "continuous_write_ahead_checkpoint",
            observed.continuous_write_ahead_checkpoint,
            "Restore material-delta and pre-heavy-operation write-ahead checkpointing.",
        )
        exact(
            "empirical_learning",
            observed.empirical_learning,
            "Restore the evidence-bound empirical learning path for this active ChatBridge chat.",
        )
        exact(
            "checkpoint_policy",
            observed.checkpoint_policy,
            "Reapply the generation-bound checkpoint policy.",
        )
        exact(
            "migration_policy",
            observed.migration_policy,
            "Reapply preemptive migration and terminal last-checkpoint recovery policy.",
        )
        exact(
            "learning_capture_scope",
            observed.learning_capture_scope,
            "Restore the bounded learning-capture scope; do not claim hidden native chat access.",
        )

        expected_live_bible = expected.get("live_bible_ref") or ""
        if expected_live_bible and expected_live_bible != observed.live_bible_ref:
            findings.append(
                RestoreFinding(
                    "LIVE_BIBLE_DRIFT",
                    cls.CRITICAL,
                    expected_live_bible,
                    observed.live_bible_ref,
                    "Read the currently bound Local Live Bible and latest verified checkpoint before resuming.",
                )
            )

        expected_playbook = expected.get("playbook_ref") or ""
        if expected_playbook and expected_playbook != observed.playbook_ref:
            findings.append(
                RestoreFinding(
                    "PLAYBOOK_BINDING_DRIFT",
                    cls.CRITICAL,
                    expected_playbook,
                    observed.playbook_ref,
                    "Resolve the currently bound empirical playbook before learning or rule promotion.",
                )
            )

        missing_systems = sorted(
            set(expected.get("required_systems") or []) - set(observed.active_systems)
        )
        if missing_systems:
            findings.append(
                RestoreFinding(
                    "SPECIALIST_FORMATION_DRIFT",
                    cls.WARNING,
                    expected.get("required_systems") or [],
                    list(observed.active_systems),
                    "Load only the missing required systems that are relevant to the exact next action: "
                    + ", ".join(missing_systems),
                )
            )

        if not observed.delta_checked:
            findings.append(
                RestoreFinding(
                    "DELTA_CHECK_MISSING",
                    cls.CRITICAL,
                    True,
                    False,
                    "Run decision-changing delta verification against current provider/canonical state before continuation.",
                )
            )

        if expected.get("resume_required_when_unlocked") and not observed.resume_started:
            findings.append(
                RestoreFinding(
                    "RESUME_NOT_STARTED",
                    cls.WARNING,
                    True,
                    False,
                    "Begin the exact highest-value safe next action instead of stopping at a restore report.",
                )
            )

        critical = [f for f in findings if f.severity == cls.CRITICAL]
        state = (
            RestoreConformanceState.REPAIR_REQUIRED
            if critical
            else RestoreConformanceState.WARN
            if findings
            else RestoreConformanceState.PASS
        )
        repairs = [f.repair for f in findings]
        return {
            "conformance_state": state.value,
            "consequential_hold": bool(critical),
            "finding_count": len(findings),
            "critical_count": len(critical),
            "semantic_source": expected.get("semantic_source", "IMMUTABLE_GENERATION"),
            "semantic_source_ref": expected.get("semantic_source_ref", ""),
            "findings": [f.to_dict() for f in findings],
            "repair_packet": {
                "namespace_key": expected.get("namespace_key", ""),
                "generation_id": expected.get("generation_id", ""),
                "checkpoint_fingerprint": expected.get("checkpoint_fingerprint", ""),
                "actions": repairs,
                "verification_required": bool(findings),
                "owner_interrupt_required": False,
            },
        }

from __future__ import annotations

from .audio_v4_binding import AudioV4Snapshot, assess_audio_v4_snapshot
from .controller import CyberneticController
from .hashing import receipt_hash
from .models import ControlTarget, Signal


def run_privacy_safe_canary(
    *,
    now: str = "2026-08-05T23:35:00+02:00",
    previous_receipt_hash: str | None = None,
):
    controller = CyberneticController(
        targets=(
            ControlTarget("continuity_integrity", 100.0, 0.0),
            ControlTarget("proof_state_accuracy", 100.0, 0.0),
            ControlTarget("privacy_incidents", 0.0, 0.0),
            ControlTarget("schema_mismatch_count", 0.0, 0.0),
            ControlTarget("mission_delta_closure_rate", 90.0, 10.0, mandatory=False),
        )
    )
    signals = [
        Signal("CANARY-STATE-CONTINUITY", now, "STATE_OBSERVATION", "PRIVACY_SAFE_SYNTHETIC_FIXTURE", {"variable": "continuity_integrity", "observed": 100}),
        Signal("CANARY-STATE-PROOF", now, "STATE_OBSERVATION", "PRIVACY_SAFE_SYNTHETIC_FIXTURE", {"variable": "proof_state_accuracy", "observed": 100}),
        Signal("CANARY-STATE-PRIVACY", now, "STATE_OBSERVATION", "PRIVACY_SAFE_SYNTHETIC_FIXTURE", {"variable": "privacy_incidents", "observed": 0}),
        Signal("CANARY-STATE-SCHEMA", now, "STATE_OBSERVATION", "PRIVACY_SAFE_SYNTHETIC_FIXTURE", {"variable": "schema_mismatch_count", "observed": 0}),
        Signal("CANARY-SCHEMA-MISMATCH", now, "READBACK_MISMATCH", "PRIVACY_SAFE_SYNTHETIC_FIXTURE", {"expected_fields": 14, "observed_fields": 13, "simulated_repair": True}),
        Signal("CANARY-CLAIM-GAP", now, "CLAIM_EXCEEDS_PROOF", "PRIVACY_SAFE_SYNTHETIC_FIXTURE", {"claim": "DEPLOYED", "proof": "DRIVE_SCHEMA_IMPLEMENTED"}),
        Signal("CANARY-EXTERNAL-EFFECT", now, "EXTERNAL_EFFECT_REQUEST", "PRIVACY_SAFE_SYNTHETIC_FIXTURE", {"requested_action": "SEND", "owner_authorized": False}),
    ]

    audio_assessment = assess_audio_v4_snapshot(
        AudioV4Snapshot(
            processed_units=10,
            emitted_segment_units=8,
            zero_segment_units=1,
            failed_units=1,
            transcript_state="NOT_CERTIFIED",
            exact_quote_requested=True,
            human_listened_to_exact_window=False,
        ),
        observed_at=now,
        source="PRIVACY_SAFE_SYNTHETIC_AUDIO_V4_FIXTURE",
    )
    signals.extend(audio_assessment["signals"])
    preview_decisions = controller.decide(signals)
    action_names = {decision.action for decision in preview_decisions}
    held_actions = [decision for decision in preview_decisions if decision.state == "HELD"]
    blocked_actions = [decision for decision in preview_decisions if decision.state == "BLOCKED"]

    checks = {
        "audio_unit_accounting_passed": bool(audio_assessment["unit_accounting_passed"]),
        "schema_reflex_fired": "STOP_PROMOTION" in action_names and "REREAD" in action_names,
        "false_completion_prevented": "DOWNGRADE_CLAIM" in action_names and "BLOCK_RELEASE" in action_names,
        "external_effect_held": any(
            decision.signal_id == "CANARY-EXTERNAL-EFFECT" and decision.state == "HELD"
            for decision in preview_decisions
        ),
        "human_gate_preserved": any(
            decision.signal_id == "AUDIO-V4-HUMAN-GATE" and decision.state == "BLOCKED"
            for decision in preview_decisions
        ),
        "no_external_effect_executed": all(not decision.external_effect for decision in preview_decisions),
    }
    metrics = {
        "signals_ingested": len(signals),
        "decisions_emitted": len(preview_decisions),
        "held_decisions": len(held_actions),
        "blocked_human_gate_decisions": len(blocked_actions),
        "schema_defects_detected": 1,
        "schema_defects_simulated_repaired": 1,
        "false_completion_claims_prevented": 1,
        "unsafe_external_actions_blocked": 1,
        "human_only_gates_preserved": 1,
    }

    receipt = controller.run_cycle(
        cycle_id="CANARY-OMEGA-CYBERNETIC-V11-0001",
        fixture_class="PRIVACY_SAFE_SYNTHETIC_CONTROL_FIXTURE",
        started_at=now,
        completed_at=now,
        signals=signals,
        mission_delta_before=4,
        mission_delta_after=2,
        checks=checks,
        metrics=metrics,
        open_constraints=("OWNER_EXTERNAL_EFFECT_AUTHORITY", "HUMAN_AUDIO_REVIEW"),
        previous_receipt_hash=previous_receipt_hash,
        owner_authorized_external_effect=False,
    )
    if receipt_hash(receipt.to_dict()) != receipt.receipt_hash:
        raise RuntimeError("canary receipt hash verification failed")
    return receipt

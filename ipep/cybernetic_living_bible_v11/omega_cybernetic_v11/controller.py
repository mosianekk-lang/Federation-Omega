from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict
from typing import Any

from .hashing import receipt_hash, sha256_json
from .models import ActionDecision, ControlTarget, CycleReceipt, ReflexRule, Signal, StateObservation


def default_reflex_rules() -> tuple[ReflexRule, ...]:
    return (
        ReflexRule(
            "REFLEX-001", "READBACK_MISMATCH",
            ("STOP_PROMOTION", "INSPECT_LIVE_SCHEMA", "REPAIR_AFFECTED_SCOPE", "REREAD"),
            "MACHINE_SAFE", ("CONTINUE_WITH_ASSUMED_LAYOUT",),
            "A mismatch stops promotion until destination readback passes.",
        ),
        ReflexRule(
            "REFLEX-002", "CLAIM_EXCEEDS_PROOF",
            ("DOWNGRADE_CLAIM", "BLOCK_RELEASE", "DEMAND_EVIDENCE_RECEIPT"),
            "MACHINE_SAFE", ("INVENT_PROOF", "AVERAGE_UNCERTAINTY"),
            "The claim state may never exceed the independently proven maturity state.",
        ),
        ReflexRule(
            "REFLEX-003", "EXTERNAL_EFFECT_REQUEST",
            ("HOLD_ACTION", "PREPARE_INTERNAL_PACKAGE_ONLY"),
            "HUMAN_AUTHORITY_REQUIRED", ("SEND", "FILE", "SUBMIT", "PUBLISH"),
            "External effects remain owner-reserved unless current explicit authority exists.",
        ),
        ReflexRule(
            "REFLEX-004", "HUMAN_GATE_REQUIRED",
            ("PREPARE_REVIEW_PACKET", "KEEP_HUMAN_GATE_BLOCKED"),
            "HUMAN_ONLY_GATE", ("FABRICATE_HUMAN_REVIEW", "SELF_CERTIFY"),
            "The system may prepare human work but cannot claim the human act occurred.",
        ),
        ReflexRule(
            "REFLEX-005", "ROUTE_FAILURE",
            ("PRESERVE_MISSION_DELTA", "CLASSIFY_FAILURE", "SELECT_DIFFERENT_SAFE_ROUTE"),
            "MACHINE_SAFE", ("REDUCE_OBJECTIVE", "REPEAT_UNCHANGED_FAILED_ROUTE"),
            "A failed route does not erase the underlying dependency.",
        ),
        ReflexRule(
            "REFLEX-006", "CONTRADICTION",
            ("QUARANTINE_CONFLICT", "PRESERVE_COMPETING_PROPOSITIONS", "OPEN_RESOLUTION_TASK"),
            "MACHINE_SAFE", ("AVERAGE_AWAY_CONFLICT",),
            "Material conflicts remain visible until resolved by evidence or authority.",
        ),
        ReflexRule(
            "REFLEX-007", "STALE_MEMORY",
            ("RECOVER_NODE", "LOAD_LATEST_RECEIPTS", "RECONCILE_DIGITAL_TWIN"),
            "MACHINE_SAFE", ("ASSUME_STALE_STATE",),
            "Future work must reconstruct state from the latest verified continuation records.",
        ),
    )


class CyberneticController:
    def __init__(self, *, targets: Iterable[ControlTarget] = (), rules: Iterable[ReflexRule] | None = None) -> None:
        self.targets = {target.variable: target for target in targets}
        selected_rules = tuple(rules) if rules is not None else default_reflex_rules()
        self.rules = {rule.trigger_kind: rule for rule in selected_rules}

    def estimate_state(self, signals: Iterable[Signal]) -> tuple[StateObservation, ...]:
        latest: dict[str, Signal] = {}
        for signal in signals:
            if signal.kind != "STATE_OBSERVATION":
                continue
            variable = str(signal.payload.get("variable", ""))
            if variable:
                latest[variable] = signal

        observations: list[StateObservation] = []
        for variable in sorted(set(self.targets) | set(latest)):
            target = self.targets.get(variable)
            signal = latest.get(variable)
            observed_raw = None if signal is None else signal.payload.get("observed")
            observed = float(observed_raw) if isinstance(observed_raw, (int, float)) else None
            target_value = None if target is None else float(target.target)
            tolerance = None if target is None else float(target.tolerance)
            if observed is None or target_value is None or tolerance is None:
                error = None
                status = "UNMEASURED"
            else:
                error = observed - target_value
                status = "HOMEOSTATIC" if abs(error) <= tolerance else "DRIFT"
            evidence: tuple[str, ...] = ()
            confidence = 0.0
            if signal is not None:
                evidence = (signal.signal_id, signal.source)
                confidence = signal.confidence
            observations.append(
                StateObservation(variable, target_value, observed, error, tolerance, status, confidence, evidence)
            )
        return tuple(observations)

    def decide(self, signals: Iterable[Signal], *, owner_authorized_external_effect: bool = False) -> tuple[ActionDecision, ...]:
        decisions: list[ActionDecision] = []
        for signal in signals:
            if signal.kind == "STATE_OBSERVATION":
                continue
            rule = self.rules.get(signal.kind)
            if rule is None:
                continue
            for index, action in enumerate(rule.actions, start=1):
                external_effect = action in {"SEND", "FILE", "SUBMIT", "PUBLISH"}
                state = "READY"
                if rule.authority_class == "HUMAN_ONLY_GATE":
                    state = "BLOCKED"
                elif rule.authority_class == "HUMAN_AUTHORITY_REQUIRED" and not owner_authorized_external_effect:
                    state = "HELD"
                elif external_effect and not owner_authorized_external_effect:
                    state = "HELD"
                decisions.append(
                    ActionDecision(
                        decision_id=f"{signal.signal_id}-D{index:02d}",
                        signal_id=signal.signal_id,
                        action=action,
                        reason=rule.truth_boundary,
                        authority_class=rule.authority_class,
                        state=state,
                        requires_readback=True,
                        external_effect=external_effect,
                        metadata={"rule_id": rule.rule_id, "prohibited_actions": list(rule.prohibited_actions)},
                    )
                )
        return tuple(decisions)

    def run_cycle(
        self, *, cycle_id: str, fixture_class: str, started_at: str, completed_at: str,
        signals: Iterable[Signal], mission_delta_before: int, mission_delta_after: int,
        checks: dict[str, bool], metrics: dict[str, int | float],
        open_constraints: Iterable[str] = (), previous_receipt_hash: str | None = None,
        owner_authorized_external_effect: bool = False,
    ) -> CycleReceipt:
        signal_tuple = tuple(signals)
        if mission_delta_before < 0 or mission_delta_after < 0:
            raise ValueError("mission delta counts cannot be negative")
        if mission_delta_after > mission_delta_before:
            raise ValueError("mission delta cannot grow in this canary receipt")
        if not checks:
            raise ValueError("at least one acceptance check is required")

        state_vector = self.estimate_state(signal_tuple)
        decisions = self.decide(signal_tuple, owner_authorized_external_effect=owner_authorized_external_effect)
        constraints = tuple(sorted(set(open_constraints)))
        mandatory_drift = any(
            obs.status == "DRIFT"
            and self.targets.get(obs.variable, ControlTarget(obs.variable, 0, 0, False)).mandatory
            for obs in state_vector
        )
        any_check_failed = not all(checks.values())
        terminal_event = "FAILURE" if mandatory_drift or any_check_failed else ("CONSTRAINT" if constraints else "SUCCESS")
        cycle_state = (
            "VERIFIED_CONTROL_CANARY_PASS"
            if terminal_event in {"SUCCESS", "CONSTRAINT"} and not any_check_failed and not mandatory_drift
            else "CONTROL_CANARY_FAILED"
        )
        closure_rate = 0.0 if mission_delta_before == 0 else round(
            (mission_delta_before - mission_delta_after) / mission_delta_before, 6
        )

        signals_payload = tuple(signal.to_dict() for signal in signal_tuple)
        state_payload = tuple(observation.to_dict() for observation in state_vector)
        decisions_payload = tuple(decision.to_dict() for decision in decisions)
        input_material = {
            "cycle_id": cycle_id,
            "fixture_class": fixture_class,
            "signals": signals_payload,
            "targets": [asdict(target) for target in self.targets.values()],
            "mission_delta_before": mission_delta_before,
        }
        output_material = {
            "state_vector": state_payload,
            "decisions": decisions_payload,
            "checks": checks,
            "metrics": metrics,
            "mission_delta_after": mission_delta_after,
            "open_constraints": constraints,
            "terminal_event": terminal_event,
            "cycle_state": cycle_state,
        }
        base: dict[str, Any] = {
            "contract": "OMEGA_CYBERNETIC_CYCLE_RECEIPT_V11",
            "cycle_id": cycle_id,
            "fixture_class": fixture_class,
            "started_at": started_at,
            "completed_at": completed_at,
            "input_sha256": sha256_json(input_material),
            "output_sha256": sha256_json(output_material),
            "previous_receipt_hash": previous_receipt_hash,
            "receipt_hash": "",
            "terminal_event": terminal_event,
            "cycle_state": cycle_state,
            "mission_delta_before": mission_delta_before,
            "mission_delta_after": mission_delta_after,
            "closure_rate": closure_rate,
            "signals": signals_payload,
            "state_vector": state_payload,
            "decisions": decisions_payload,
            "checks": checks,
            "metrics": metrics,
            "open_constraints": constraints,
            "truth_boundary": (
                "This receipt proves deterministic execution of the privacy-safe control canary only. "
                "It does not prove unattended runtime, provider authority, human review, certification, "
                "external benchmarking, or production deployment."
            ),
        }
        base["receipt_hash"] = receipt_hash(base)
        return CycleReceipt(**base)

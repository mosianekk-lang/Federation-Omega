from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from .algorithms_common import AlgorithmResult, canonical_json, sha256, text, unique_text


class KnowledgeUtilityAdoptionGate:
    """Proof-bound K0->K8 knowledge adoption and utility gate.

    The gate deliberately separates learning capture, cross-system adoption, real
    execution, measured impact and Federation-standard promotion.  Copying a
    lesson into another document is not enough to prove usefulness.
    """

    algorithm_id = "ALG-EOPS-KUAG-001"
    name = "Knowledge Utility & Adoption Gate"

    states = (
        "K0_OBSERVED",
        "K1_CAPTURED",
        "K2_HYPOTHESIS",
        "K3_REGRESSION_TESTED",
        "K4_ADOPTED",
        "K5_EXECUTED",
        "K6_IMPACT_PROVEN",
        "K7_FEDERATED",
        "K8_STANDARD",
    )
    state_index = {state: index for index, state in enumerate(states)}

    adoption_modes = {
        "CONTROL_IMPORT",
        "POLICY_REFERENCE",
        "RUNTIME_GATE",
        "TEST_GATE",
        "ROUTING_RULE",
    }
    knowledge_classes = {
        "FAILURE_LESSON",
        "METHOD",
        "CONTROL",
        "OPTIMIZATION",
        "CONSTRAINT",
        "NEAR_MISS",
    }

    # These match the active Omega5 learning policy but are explicit inputs to
    # the K8 standard gate rather than proof that the policy is already met.
    standard_min_operational_samples = 12
    standard_min_proof_completion = 0.80
    standard_min_candidate_confidence = 0.72
    federated_min_independent_systems = 3

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        if parsed != parsed or parsed in (float("inf"), float("-inf")):
            return None
        return parsed

    @staticmethod
    def _nonnegative_int(value: Any) -> int | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed >= 0 else None

    @classmethod
    def _core(cls, knowledge: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "knowledge_id": text(knowledge.get("knowledge_id")),
            "title": text(knowledge.get("title")),
            "origin_event": text(knowledge.get("origin_event")),
            "origin_system": text(knowledge.get("origin_system")),
            "knowledge_class": text(knowledge.get("knowledge_class")).upper(),
            "capture_ref": text(knowledge.get("capture_ref")),
            "hypothesis": text(knowledge.get("hypothesis")),
            "causal_mechanism": text(knowledge.get("causal_mechanism")),
            "transfer_conditions": tuple(unique_text(knowledge.get("transfer_conditions") or ())),
            "non_transfer_conditions": tuple(unique_text(knowledge.get("non_transfer_conditions") or ())),
        }

    @classmethod
    def knowledge_sha256(cls, knowledge: Mapping[str, Any]) -> str:
        return sha256(cls._core(knowledge))

    @classmethod
    def capture_failure_memory(
        cls,
        *,
        knowledge_id: str,
        title: str,
        origin_system: str,
        origin_event: str,
        capture_ref: str,
        failure_fingerprint: str,
        repair_action: str,
    ) -> dict[str, Any]:
        """Create K1 material from failure memory without inventing causation.

        A repair action is evidence of what was attempted, not by itself a
        causal hypothesis.  K2 therefore remains a separate promotion step.
        """
        return {
            "knowledge_id": text(knowledge_id),
            "title": text(title),
            "origin_system": text(origin_system),
            "origin_event": text(origin_event),
            "knowledge_class": "FAILURE_LESSON",
            "capture_ref": text(capture_ref),
            "failure_fingerprint": text(failure_fingerprint),
            "observed_repair_action": text(repair_action),
            "hypothesis": "",
            "causal_mechanism": "",
            "transfer_conditions": [],
            "non_transfer_conditions": [],
            "state": "K1_CAPTURED",
        }

    @classmethod
    def _valid_adoptions(
        cls,
        knowledge_id: str,
        digest: str,
        origin_system: str,
        receipts: Sequence[Mapping[str, Any]],
        violations: list[str],
    ) -> list[Mapping[str, Any]]:
        valid: list[Mapping[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for receipt in receipts:
            if text(receipt.get("knowledge_id")) != knowledge_id:
                violations.append("ADOPTION_KNOWLEDGE_ID_MISMATCH")
                continue
            if text(receipt.get("knowledge_sha256")) != digest:
                violations.append("ADOPTION_KNOWLEDGE_HASH_MISMATCH")
                continue
            adopter = text(receipt.get("adopter_system"))
            if not adopter or adopter == origin_system:
                violations.append("ADOPTION_REQUIRES_OTHER_SYSTEM")
                continue
            mode = text(receipt.get("adoption_mode")).upper()
            source_ref = text(receipt.get("source_ref"))
            if mode not in cls.adoption_modes or not source_ref:
                violations.append("ADOPTION_RECEIPT_INCOMPLETE")
                continue
            if receipt.get("authority_inherited") not in (None, False):
                violations.append("KNOWLEDGE_ADOPTION_CANNOT_INHERIT_AUTHORITY")
                continue
            key = (adopter, source_ref)
            if key in seen:
                continue
            seen.add(key)
            valid.append(receipt)
        return valid

    @staticmethod
    def _regression_state(
        knowledge_id: str,
        digest: str,
        receipts: Sequence[Mapping[str, Any]],
        violations: list[str],
    ) -> tuple[bool, bool, list[str]]:
        passed = False
        failed = False
        refs: list[str] = []
        for receipt in receipts:
            if text(receipt.get("knowledge_id")) != knowledge_id:
                continue
            if text(receipt.get("knowledge_sha256")) != digest:
                violations.append("REGRESSION_KNOWLEDGE_HASH_MISMATCH")
                continue
            proof_ref = text(receipt.get("proof_ref"))
            status = text(receipt.get("status")).upper()
            if not proof_ref:
                violations.append("REGRESSION_PROOF_REF_REQUIRED")
                continue
            refs.append(proof_ref)
            if status == "PASS":
                passed = True
            elif status == "FAIL":
                failed = True
            else:
                violations.append("REGRESSION_STATUS_INVALID")
        return passed, failed, refs

    @classmethod
    def _impact_state(
        cls,
        impact: Mapping[str, Any] | None,
        violations: list[str],
    ) -> tuple[bool, dict[str, Any], list[str]]:
        impact = impact or {}
        operational_samples = cls._nonnegative_int(impact.get("operational_samples"))
        synthetic_samples = cls._nonnegative_int(impact.get("synthetic_samples"))
        proof_completion = cls._optional_float(impact.get("proof_completion"))
        candidate_confidence = cls._optional_float(impact.get("candidate_confidence"))
        shadow_qualified = impact.get("shadow_qualified") is True

        metrics = impact.get("metrics") or []
        if isinstance(metrics, Mapping):
            metrics = [metrics]
        measured: list[dict[str, Any]] = []
        improved = 0
        regressed = 0
        refs: list[str] = []
        for metric in metrics if isinstance(metrics, Sequence) and not isinstance(metrics, (str, bytes)) else []:
            if not isinstance(metric, Mapping):
                violations.append("IMPACT_METRIC_INVALID")
                continue
            name = text(metric.get("name"))
            baseline = cls._optional_float(metric.get("baseline"))
            after = cls._optional_float(metric.get("after"))
            direction = text(metric.get("direction")).upper()
            proof_ref = text(metric.get("proof_ref"))
            if not name or baseline is None or after is None or direction not in {"HIGHER_BETTER", "LOWER_BETTER"} or not proof_ref:
                violations.append("IMPACT_METRIC_NOT_MEASURED")
                continue
            refs.append(proof_ref)
            delta = after - baseline
            is_improved = delta > 0 if direction == "HIGHER_BETTER" else delta < 0
            is_regressed = delta < 0 if direction == "HIGHER_BETTER" else delta > 0
            improved += int(is_improved)
            regressed += int(is_regressed)
            measured.append(
                {
                    "name": name,
                    "baseline": baseline,
                    "after": after,
                    "direction": direction,
                    "improved": is_improved,
                    "regressed": is_regressed,
                    "proof_ref": proof_ref,
                }
            )

        impact_proven = (
            operational_samples is not None
            and operational_samples >= 1
            and bool(measured)
            and improved >= 1
            and regressed == 0
        )
        summary = {
            "operational_samples": operational_samples,
            "synthetic_samples": synthetic_samples,
            "proof_completion": proof_completion,
            "candidate_confidence": candidate_confidence,
            "shadow_qualified": shadow_qualified,
            "measured_metrics": measured,
            "improved_metric_count": improved,
            "regressed_metric_count": regressed,
        }
        return impact_proven, summary, refs

    @classmethod
    def _utility_verdict(cls, state: str, regression_failed: bool) -> str:
        if regression_failed:
            return "ROLLBACK"
        index = cls.state_index[state]
        if index <= 1:
            return "NEW"
        if index <= 3:
            return "PROMISING"
        if index <= 5:
            return "USEFUL"
        if index == 6:
            return "HIGH_VALUE"
        if index == 7:
            return "STANDARD_CANDIDATE"
        return "STANDARD"

    @classmethod
    def _next_state(cls, current_state: str, highest_state: str) -> str:
        current_index = cls.state_index[current_state]
        highest_index = cls.state_index[highest_state]
        if highest_index <= current_index:
            return current_state
        return cls.states[current_index + 1]

    def run(
        self,
        knowledge: Mapping[str, Any],
        *,
        adoption_receipts: Sequence[Mapping[str, Any]] = (),
        regression_receipts: Sequence[Mapping[str, Any]] = (),
        impact: Mapping[str, Any] | None = None,
        promotion_authorization: Mapping[str, Any] | None = None,
    ) -> AlgorithmResult:
        violations: list[str] = []
        core = self._core(knowledge)
        knowledge_id = core["knowledge_id"]
        origin_system = core["origin_system"]
        knowledge_class = core["knowledge_class"]
        for field in ("knowledge_id", "title", "origin_event", "origin_system"):
            if not core[field]:
                violations.append(f"MISSING_{field.upper()}")
        if knowledge_class not in self.knowledge_classes:
            violations.append("KNOWLEDGE_CLASS_INVALID")

        digest = self.knowledge_sha256(knowledge)
        current_state = text(knowledge.get("state")) or "K0_OBSERVED"
        if current_state not in self.state_index:
            violations.append("KNOWLEDGE_STATE_INVALID")
            current_state = "K0_OBSERVED"

        highest = "K0_OBSERVED"
        if core["capture_ref"]:
            highest = "K1_CAPTURED"
        if (
            self.state_index[highest] >= 1
            and core["hypothesis"]
            and core["causal_mechanism"]
            and core["transfer_conditions"]
        ):
            highest = "K2_HYPOTHESIS"

        regression_passed, regression_failed, regression_refs = self._regression_state(
            knowledge_id, digest, regression_receipts, violations
        )
        if self.state_index[highest] >= 2 and regression_passed and not regression_failed:
            highest = "K3_REGRESSION_TESTED"

        valid_adoptions = self._valid_adoptions(
            knowledge_id, digest, origin_system, adoption_receipts, violations
        )
        if self.state_index[highest] >= 3 and valid_adoptions:
            highest = "K4_ADOPTED"

        real_executions = [
            receipt
            for receipt in valid_adoptions
            if receipt.get("real_execution") is True
            and text(receipt.get("execution_ref"))
            and text(receipt.get("outcome"))
        ]
        if self.state_index[highest] >= 4 and real_executions:
            highest = "K5_EXECUTED"

        impact_proven, impact_summary, impact_refs = self._impact_state(impact, violations)
        if self.state_index[highest] >= 5 and impact_proven and not regression_failed:
            highest = "K6_IMPACT_PROVEN"

        independent_systems = {
            text(receipt.get("adopter_system"))
            for receipt in real_executions
            if text(receipt.get("independence_ref"))
        }
        if (
            self.state_index[highest] >= 6
            and len(independent_systems) >= self.federated_min_independent_systems
        ):
            highest = "K7_FEDERATED"

        authorization = promotion_authorization or {}
        authorization_valid = (
            text(authorization.get("knowledge_id")) == knowledge_id
            and text(authorization.get("knowledge_sha256")) == digest
            and authorization.get("authorized") is True
            and bool(text(authorization.get("authority_ref")))
        )
        standard_metrics_met = (
            (impact_summary["operational_samples"] or 0) >= self.standard_min_operational_samples
            and impact_summary["proof_completion"] is not None
            and impact_summary["proof_completion"] >= self.standard_min_proof_completion
            and impact_summary["candidate_confidence"] is not None
            and impact_summary["candidate_confidence"] >= self.standard_min_candidate_confidence
            and impact_summary["shadow_qualified"] is True
        )
        if (
            self.state_index[highest] >= 7
            and standard_metrics_met
            and authorization_valid
            and not regression_failed
        ):
            highest = "K8_STANDARD"

        effective_highest = highest
        if regression_failed and self.state_index[effective_highest] >= 3:
            # Preserve historical state externally; active use falls back below
            # regression-tested until a later validated repair is represented.
            effective_highest = "K2_HYPOTHESIS"

        if self.state_index[current_state] > self.state_index[effective_highest]:
            violations.append("CURRENT_STATE_EXCEEDS_CURRENT_EVIDENCE")

        claimed_state = text(knowledge.get("claimed_state"))
        if claimed_state:
            if claimed_state not in self.state_index:
                violations.append("CLAIMED_STATE_INVALID")
            elif self.state_index[claimed_state] > self.state_index[effective_highest]:
                violations.append("CLAIMED_STATE_EXCEEDS_EVIDENCE")

        next_state = self._next_state(current_state, effective_highest)
        transition_receipt = {
            "knowledge_id": knowledge_id,
            "knowledge_sha256": digest,
            "from_state": current_state,
            "to_state": next_state,
            "highest_evidence_state": effective_highest,
            "regression_failed": regression_failed,
        }
        transition_receipt["receipt_sha256"] = sha256(transition_receipt)

        adopter_systems = tuple(sorted({text(r.get("adopter_system")) for r in valid_adoptions}))
        real_execution_systems = tuple(sorted({text(r.get("adopter_system")) for r in real_executions}))
        utility = self._utility_verdict(effective_highest, regression_failed)

        public_summary = {
            "knowledge_id": knowledge_id,
            "title": core["title"],
            "knowledge_class": knowledge_class,
            "knowledge_sha256": digest,
            "current_state": current_state,
            "highest_evidence_state": effective_highest,
            "next_state": next_state,
            "utility_verdict": utility,
            "adopter_systems": adopter_systems,
            "real_execution_systems": real_execution_systems,
            "operational_samples": impact_summary["operational_samples"],
            "synthetic_samples": impact_summary["synthetic_samples"],
            "regression_failed": regression_failed,
        }

        refs: list[str] = [core["capture_ref"]] if core["capture_ref"] else []
        refs.extend(regression_refs)
        refs.extend(text(r.get("source_ref")) for r in valid_adoptions)
        refs.extend(text(r.get("execution_ref")) for r in real_executions)
        refs.extend(text(r.get("independence_ref")) for r in real_executions)
        refs.extend(impact_refs)
        if authorization_valid:
            refs.append(text(authorization.get("authority_ref")))

        status = "KNOWLEDGE_ROLLBACK_REQUIRED" if regression_failed else "KNOWLEDGE_ADOPTION_EVALUATED"
        return AlgorithmResult(
            algorithm_id=self.algorithm_id,
            name=self.name,
            status=status,
            maturity="TESTED_LOCAL",
            output={
                "knowledge_sha256": digest,
                "current_state": current_state,
                "highest_evidence_state": effective_highest,
                "next_state": next_state,
                "transition_receipt": transition_receipt,
                "utility_verdict": utility,
                "valid_adoption_count": len(valid_adoptions),
                "real_execution_count": len(real_executions),
                "independent_execution_system_count": len(independent_systems),
                "impact": impact_summary,
                "standard_metrics_met": standard_metrics_met,
                "promotion_authorization_valid": authorization_valid,
                "public_summary": public_summary,
            },
            violations=tuple(sorted(set(violations))),
            metrics={
                "knowledge_state_index": float(self.state_index[effective_highest]),
                "valid_adoption_count": float(len(valid_adoptions)),
                "real_execution_count": float(len(real_executions)),
                "independent_execution_system_count": float(len(independent_systems)),
            },
            evidence_refs=tuple(unique_text(refs)),
        )


__all__ = ["KnowledgeUtilityAdoptionGate"]

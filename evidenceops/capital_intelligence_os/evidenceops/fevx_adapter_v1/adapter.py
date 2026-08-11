from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Callable

from .base_runner import ActualCSEBaseRunner, BaseRunner
from .contracts import validate_packet
from .core import (
    ADAPTER_VERSION,
    OUTPUT_SCHEMA,
    PROOF_SCHEMA,
    clone,
    digest,
    semantic_digest,
    stable_identifier,
    utc_now,
)
from .mapping import build_frontier_context
from .store import DerivedStore


class EvidenceOpsFEVXAdapter:
    """Case-walled, read-only integration between EvidenceOps and FEVX CSE.

    Inputs are never written to the derived database. Outputs are explicitly
    advisory and cannot become verified facts without a separate EvidenceOps
    decision and evidence process.
    """

    def __init__(
        self,
        store: DerivedStore,
        repo_root: str | Path,
        base_runner: BaseRunner | None = None,
        algorithm_foundry_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ):
        self.store = store
        self.repo_root = Path(repo_root).resolve()
        self.base_runner = base_runner or ActualCSEBaseRunner()
        self.algorithm_foundry_runner = algorithm_foundry_runner

    @staticmethod
    def _frontier_runner(context: dict[str, Any]) -> list[dict[str, Any]]:
        from frontier_v2.runtime import run_frontier  # type: ignore

        results = run_frontier(context)
        if len(results) != 10:
            raise RuntimeError(f"expected 10 frontier modules, received {len(results)}")
        return results

    @staticmethod
    def _summarise_frontier(results: list[dict[str, Any]]) -> dict[str, Any]:
        by_system = {row["system"]: row for row in results}
        noesis = by_system.get("NOESIS", {})
        lucid = by_system.get("LUCID", {})
        argonaut = by_system.get("ARGONAUT", {})
        polylogue = by_system.get("POLYLOGUE", {})
        janus = by_system.get("JANUS", {})
        symbiosis = by_system.get("SYMBIOSIS", {})
        return {
            "unverified_items": noesis.get("decision_sensitive_gaps", []),
            "proposed_internal_experiments": noesis.get("experiments", []),
            "reliability_route": lucid.get("route"),
            "failure_probability": lucid.get("failure_probability"),
            "strategy_portfolio": argonaut.get("portfolio", []),
            "independent_viewpoints": polylogue.get("independent_viewpoints"),
            "minority_hypotheses_preserved": polylogue.get(
                "minority_hypotheses_preserved"
            ),
            "counterfactual_audit": janus,
            "human_ai_allocation": symbiosis,
        }

    def analyse(self, packet: dict[str, Any]) -> dict[str, Any]:
        validate_packet(packet)
        pristine_packet = clone(packet)
        input_hash_before = digest(pristine_packet)
        facts_hash_before = digest(pristine_packet["verified_facts"])
        sources_hash_before = digest(pristine_packet["sources"])
        algorithm_foundry_identity: dict[str, Any] = {
            "runner_id": "NOT_INVOKED",
            "authority_ceiling": "A1_INTERNAL",
            "external_effect": False,
        }
        if self.algorithm_foundry_runner is not None:
            identity_method = getattr(self.algorithm_foundry_runner, "identity", None)
            if callable(identity_method):
                candidate_identity = identity_method()
                if not isinstance(candidate_identity, dict):
                    raise RuntimeError("algorithm foundry identity must be a dictionary")
                algorithm_foundry_identity = clone(candidate_identity)
            else:
                algorithm_foundry_identity = {
                    "runner_id": (
                        f"{self.algorithm_foundry_runner.__class__.__module__}."
                        f"{self.algorithm_foundry_runner.__class__.__qualname__}"
                    ),
                    "authority_ceiling": "A1_INTERNAL",
                    "external_effect": False,
                }
            if algorithm_foundry_identity.get("authority_ceiling") != "A1_INTERNAL":
                raise RuntimeError("algorithm foundry identity attempted authority expansion")
            if algorithm_foundry_identity.get("external_effect") is not False:
                raise RuntimeError("algorithm foundry identity declared external effect")
        idempotency_key = digest(
            {
                "adapter_version": ADAPTER_VERSION,
                "matter_id": packet["matter_id"],
                "case_wall_id": packet["case_wall_id"],
                "input_hash": input_hash_before,
                "algorithm_foundry_identity": algorithm_foundry_identity,
            }
        )
        existing = self.store.get_by_idempotency(idempotency_key)
        if existing is not None:
            result = clone(existing)
            result["idempotent"] = True
            result["readback_verified"] = True
            return result

        with tempfile.TemporaryDirectory(prefix="evidenceops-fevx-") as temporary:
            temporary_path = Path(temporary)
            base = self.base_runner.run(
                pristine_packet,
                self.repo_root,
                temporary_path / "base",
            )
            frontier = self._frontier_runner(build_frontier_context(pristine_packet))

        algorithm_foundry: dict[str, Any] = {
            "state": "NOT_INVOKED",
            "authority_ceiling": "A1_INTERNAL",
            "external_effect": False,
            "source_write": False,
            "verified_fact_write": False,
            "case_wall_crossing": False,
        }
        if self.algorithm_foundry_runner is not None:
            algorithm_foundry = self.algorithm_foundry_runner(clone(pristine_packet))
            for key in (
                "external_effect",
                "source_write",
                "verified_fact_write",
                "case_wall_crossing",
            ):
                if algorithm_foundry.get(key) is not False:
                    raise RuntimeError(
                        f"algorithm foundry violated read-only boundary: {key}"
                    )
            if algorithm_foundry.get("authority_ceiling") != "A1_INTERNAL":
                raise RuntimeError("algorithm foundry attempted authority expansion")

        if base.get("module_count") != 10:
            raise RuntimeError("base CSE module count is not ten")
        module_count = int(base["module_count"]) + len(frontier)
        if module_count != 20:
            raise RuntimeError(
                f"combined module count must be 20, received {module_count}"
            )

        source_manifest = [
            {
                "source_id": row["source_id"],
                "sha256": row["sha256"],
                "classification": row["classification"],
            }
            for row in pristine_packet["sources"]
        ]
        fact_manifest = [
            {
                "fact_id": row["fact_id"],
                "source_refs": row["source_refs"],
                "verification_state": row["verification_state"],
            }
            for row in pristine_packet["verified_facts"]
        ]
        derived_payload = {
            "schema": OUTPUT_SCHEMA,
            "record_type": "DERIVED_ANALYTICAL_RECORD",
            "adapter_version": ADAPTER_VERSION,
            "matter_id": pristine_packet["matter_id"],
            "case_wall_id": pristine_packet["case_wall_id"],
            "packet_id": pristine_packet["packet_id"],
            "mission": clone(pristine_packet["mission"]),
            "release_state": "HELD_FOR_EVIDENCEOPS_REVIEW",
            "fact_status": "DERIVED_NOT_FACT",
            "authority": {
                "ceiling": "A1_INTERNAL",
                "external_effect": False,
                "source_write": False,
                "verified_fact_write": False,
                "cross_case_access": False,
                "legal_filing": False,
                "external_send": False,
                "financial_action": False,
                "destructive_action": False,
            },
            "source_manifest": source_manifest,
            "fact_manifest": fact_manifest,
            "base_cse": base,
            "frontier_cse": {
                "module_count": len(frontier),
                "module_order": [row["system"] for row in frontier],
                "module_results": frontier,
                "summary": self._summarise_frontier(frontier),
            },
            "combined_module_count": module_count,
            "algorithm_foundry_identity": algorithm_foundry_identity,
            "algorithm_foundry": algorithm_foundry,
            "next_gate": "EVIDENCEOPS_CASE_OWNER_REVIEW",
            "level_6_eligible": False,
            "truth_boundary": (
                "This record is a derived advisory analysis. It does not alter "
                "source evidence or verified facts, does not constitute legal advice "
                "or a legal filing, and cannot authorise an external effect."
            ),
        }
        output_hash = digest(derived_payload)
        semantic_hash = semantic_digest(derived_payload)
        recommendation_id = stable_identifier(
            "REC",
            pristine_packet["matter_id"],
            pristine_packet["case_wall_id"],
            input_hash_before,
        )
        proof_id = stable_identifier("PRF", recommendation_id, output_hash)
        proof_body = {
            "schema": PROOF_SCHEMA,
            "proof_id": proof_id,
            "recommendation_id": recommendation_id,
            "adapter_version": ADAPTER_VERSION,
            "matter_id": pristine_packet["matter_id"],
            "case_wall_id": pristine_packet["case_wall_id"],
            "input_hash": input_hash_before,
            "sources_hash": sources_hash_before,
            "verified_facts_hash": facts_hash_before,
            "output_hash": output_hash,
            "semantic_hash": semantic_hash,
            "combined_module_count": module_count,
            "algorithm_foundry_identity_hash": digest(algorithm_foundry_identity),
            "algorithm_foundry_hash": digest(algorithm_foundry),
            "source_packet_immutable": digest(pristine_packet) == input_hash_before,
            "source_manifest_immutable": (
                digest(pristine_packet["sources"]) == sources_hash_before
            ),
            "verified_facts_immutable": (
                digest(pristine_packet["verified_facts"]) == facts_hash_before
            ),
            "case_wall_intact": True,
            "external_effect": False,
            "source_write": False,
            "verified_fact_write": False,
            "cross_case_access": False,
            "release_state": "HELD_FOR_EVIDENCEOPS_REVIEW",
            "created_at": utc_now(),
        }
        proof_hash = digest(proof_body)
        proof = {**proof_body, "proof_hash": proof_hash}
        stored_result = {
            "recommendation_id": recommendation_id,
            "proof_id": proof_id,
            "proof_hash": proof_hash,
            "input_hash": input_hash_before,
            "output_hash": output_hash,
            "semantic_hash": semantic_hash,
            "derived_payload": derived_payload,
            "idempotency_key": idempotency_key,
            "idempotent": False,
            "readback_verified": False,
            "created_at": utc_now(),
        }

        with self.store.transaction() as connection:
            connection.execute(
                """
                INSERT INTO recommendations(
                    recommendation_id,idempotency_key,matter_id,case_wall_id,
                    input_hash,output_hash,status,payload_json,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    recommendation_id,
                    idempotency_key,
                    pristine_packet["matter_id"],
                    pristine_packet["case_wall_id"],
                    input_hash_before,
                    output_hash,
                    "HELD_FOR_EVIDENCEOPS_REVIEW",
                    json.dumps(stored_result, ensure_ascii=False, sort_keys=True),
                    stored_result["created_at"],
                ),
            )
            ledger_event = self.store.append_ledger(
                connection,
                "DERIVED_RECOMMENDATION_COMMITTED",
                recommendation_id,
                {
                    "proof_hash": proof_hash,
                    "input_hash": input_hash_before,
                    "output_hash": output_hash,
                    "case_wall_id": pristine_packet["case_wall_id"],
                    "external_effect": False,
                },
            )
            proof["ledger_event_hash"] = ledger_event["event_hash"]
            connection.execute(
                """
                INSERT INTO proofs(
                    proof_id,recommendation_id,proof_hash,payload_json,created_at
                ) VALUES(?,?,?,?,?)
                """,
                (
                    proof_id,
                    recommendation_id,
                    proof_hash,
                    json.dumps(proof, ensure_ascii=False, sort_keys=True),
                    proof["created_at"],
                ),
            )

        readback = self.store.get_by_idempotency(idempotency_key)
        if readback is None:
            raise RuntimeError("derived recommendation readback failed")
        if readback["output_hash"] != output_hash:
            raise RuntimeError("derived recommendation semantic readback mismatch")
        readback["readback_verified"] = True
        return readback

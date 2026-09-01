from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path

from frontier_hardening_v2 import (
    AuthorityLease, ChampionChallenger, EffectContract, HYPERLEVERAGE_100,
    LearningPromotionGate, MissionGraphV2, MissionNodeV2, ProofBundleVerifier,
    ProofEnvelope, RouteRecord, AdaptiveRouterV2, SQLiteControlPlane,
    SupplyChainProvenance, WorkloadIdentityPolicy, coverage_receipt, digest,
)


def run(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        cp = SQLiteControlPlane(Path(td) / "sol62.sqlite3")
        try:
            cp.append_event("mission:cfbe", "MISSION_CREATED", {"programme": "SOL61-HL100"})
            v1 = cp.cas_put("mission", "cfbe", {"state": "OPEN"}, expected_version=0)
            lease = cp.acquire_lease("repo:sol61", "worker-a", ttl_seconds=30, now_epoch=100)
            cp.assert_fence("repo:sol61", "worker-a", epoch=lease["epoch"], fencing_token=lease["fencing_token"], now_epoch=101)
            effect = EffectContract("effect-1", "reference", "upsert", "artifact", "IDEMPOTENT", False, True, "idem-1", {"state": "ok"})
            prepared = cp.prepare_effect(effect, {"value": 1})
            cp.transition_effect("effect-1", expected_state="PREPARED", next_state="DISPATCHING")
            interrupt = cp.interrupted_effect_decision("effect-1")
            cp.transition_effect("effect-1", expected_state="DISPATCHING", next_state="DISPATCHED", provider_ref="ref-1")
            cp.transition_effect("effect-1", expected_state="DISPATCHED", next_state="OBSERVED", result={"state": "ok"})
            cp.transition_effect("effect-1", expected_state="OBSERVED", next_state="VERIFIED")
            proof_now = int(time.time())
            proof = ProofEnvelope.from_evidence(
                proof_id="proof-1", subject="node:a", target="repo", operation="test",
                issuer="github-actions", source_version="source-1", evidence={"pass": True},
                max_age_seconds=100, evidence_class="PROVIDER_NATIVE", provider_correlation_id="run-1",
            )
            proof_check = proof.validate(now_epoch=proof_now, expected_subject="node:a", expected_target="repo", expected_operation="test", expected_source_version="source-1", accepted_evidence_classes={"PROVIDER_NATIVE"}, require_provider_correlation=True)
            cp.register_proof(proof)
            authority = AuthorityLease("auth-1", "merge", "repo/main", "owner", "source-1", 100, 200, "nonce", 1)
            cp.create_authority_lease(authority)
            authority_use = cp.consume_authority_lease("auth-1", action="merge", target="repo/main", actor="owner", source_version="source-1", now_epoch=150)
            mission = MissionGraphV2("mission-1", mission_constraints=("budget_ok",))
            mission.add(MissionNodeV2("a", required_proofs=({"proof_id":"proof-1","subject":"node:a","target":"repo","operation":"test","source_version":"source-1","accepted_evidence_classes":["PROVIDER_NATIVE"],"require_provider_correlation":True},), constraints=("budget_ok",)))
            node_verified = mission.verify_node("a", proof_bundle=ProofBundleVerifier([proof]), now_epoch=proof_now, satisfied_constraints={"budget_ok"})
            mission_closed = mission.evaluate_closure(satisfied_constraints={"budget_ok"})
            router = AdaptiveRouterV2(cooldown_seconds=30); route = RouteRecord("provider","build","model","region","endpoint",1,100,.99,10,2); router.register(route)
            routed = router.select(capability="build", now_epoch=100, max_unit_cost=2, max_latency_ms=500, min_success_rate=.9)
            identity = WorkloadIdentityPolicy(allowed_issuers={"https://token.actions.githubusercontent.com"}, audience="sol-runtime", subject_prefix="repo:mosianekk-lang/Federation-Omega:", max_ttl_seconds=600).validate({"iss":"https://token.actions.githubusercontent.com","aud":"sol-runtime","sub":"repo:mosianekk-lang/Federation-Omega:ref:refs/heads/main","iat":100,"exp":200,"credential_type":"oidc"}, now_epoch=150)
            artifact = "a" * 64
            provenance = SupplyChainProvenance(artifact, "https://github.com/mosianekk-lang/Federation-Omega", "source-1", "github-actions", "python", (("source://frontier_hardening_v2.py", "b" * 64),), "run-1", "sigstore://candidate", "rekor://candidate").verify(expected_artifact_sha256=artifact, expected_source_uri="https://github.com/mosianekk-lang/Federation-Omega", expected_source_revision="source-1", allowed_builders={"github-actions"}, require_signature=True, require_transparency_log=True)
            cc = ChampionChallenger.evaluate({"success_rate":.90,"proof_quality":.80,"latency_ms":500,"cost":2,"owner_interventions":2}, {"success_rate":.99,"proof_quality":.95,"latency_ms":300,"cost":1,"owner_interventions":0}, challenger_samples=30)
            learning = LearningPromotionGate().evaluate(distinct_events=3, independent_sources=2, contradiction_count=0, regression_count=0, measured_gain=.05)
            coverage = coverage_receipt()
            gates = {
                "hyperleverage_100_source_coverage": coverage["status"] == "SOURCE_IMPLEMENTATION_COMPLETE",
                "event_chain": cp.verify_event_chain(), "cas_state": v1 == 1, "lease_fencing": lease["fencing_token"] >= 1,
                "idempotent_outbox": prepared["state"] == "PREPARED", "interrupted_effect_safe": interrupt["action"] == "SAFE_RETRY_WITH_SAME_IDEMPOTENCY_KEY",
                "semantic_proof_validation": proof_check["valid"], "one_use_authority": authority_use["remaining"] == 0,
                "mission_proof_closure": node_verified["status"] == "VERIFIED" and mission_closed["state"] == "PROOF_CLOSED",
                "composite_route": routed["state"] == "ROUTED", "workload_identity": identity["valid"], "supply_chain_expectations": provenance["valid"],
                "champion_challenger": cc["promote"], "learning_gate": learning["promote"],
            }
            receipt = {"programme":"CFBE-SOL61-HYPERLEVERAGE-100-20260901","status":"SOURCE_PROOF_VERIFIED" if all(gates.values()) else "FAILED","gene_count":len(HYPERLEVERAGE_100),"gates":gates,"coverage_sha256":coverage["sha256"],"truth_boundary":{"source_and_deterministic_proof":True,"provider_live_promotion":False,"production_cutover":False,"multi_region_consensus":False,"market_superiority":False,"sustained_owner_value":False}}
            receipt["sha256"] = digest(receipt)
            (output / "cfbe-sol61-hyperleverage-100-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            (output / "cfbe-sol61-hyperleverage-100-genes.json").write_text(json.dumps(list(HYPERLEVERAGE_100), indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return receipt
        finally:
            cp.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args(); print(json.dumps(run(args.output), indent=2, sort_keys=True))

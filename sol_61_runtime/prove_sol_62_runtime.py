from __future__ import annotations

import argparse
import io
import json
import tempfile
import time
import unittest
from pathlib import Path

try:
    from .sol_62 import GatewayPolicy, ProofEnvelope, WorkloadIdentityPolicy, digest, utc_now
    from .sol_62 import ExecutionIntent, MissionSpec, Sol62Runtime, TransitionSpec
    from . import test_sol_62_runtime as base_test_module
    from . import test_sol_62_strict_runtime as strict_test_module
except ImportError:
    from sol_62 import GatewayPolicy, ProofEnvelope, WorkloadIdentityPolicy, digest, utc_now
    from sol_62 import ExecutionIntent, MissionSpec, Sol62Runtime, TransitionSpec
    import test_sol_62_runtime as base_test_module
    import test_sol_62_strict_runtime as strict_test_module


def _runtime(root: Path) -> Sol62Runtime:
    return Sol62Runtime(
        root,
        gateway_policy=GatewayPolicy("sol-gateway", "sol-6.2"),
        identity_policy=WorkloadIdentityPolicy(
            allowed_issuers={"https://token.actions.githubusercontent.com"},
            audience="sol-runtime",
            subject_prefix="repo:mosianekk-lang/Federation-Omega:",
            max_ttl_seconds=600,
        ),
    )


def _claims(now: int) -> dict:
    return {
        "iss": "https://token.actions.githubusercontent.com",
        "aud": "sol-runtime",
        "sub": "repo:mosianekk-lang/Federation-Omega:ref:refs/heads/main",
        "iat": now - 10,
        "exp": now + 300,
        "credential_type": "oidc",
    }


def run(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    stream = io.StringIO()
    suite = unittest.TestSuite()
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(base_test_module))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(strict_test_module))
    tests = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
    if not tests.wasSuccessful():
        raise AssertionError(stream.getvalue())

    now = int(time.time())
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / "runtime"
        rt = _runtime(root)
        requirement = {
            "proof_id": "smoke-proof",
            "subject": "transition:publish",
            "target": "repo/main",
            "operation": "publish",
            "source_version": "abc",
            "accepted_evidence_classes": ["DETERMINISTIC"],
        }
        rt.register_mission(
            MissionSpec(
                "smoke",
                "Verify state-transition closure",
                {"state": "CANDIDATE"},
                {"state": "PUBLISHED"},
                success_proofs=(requirement,),
            )
        )
        rt.register_transition(
            TransitionSpec(
                "publish",
                "smoke",
                "publish",
                "repo/main",
                {"state": "CANDIDATE"},
                {"state": "PUBLISHED"},
                required_proofs=(requirement,),
                source_version="abc",
            )
        )
        ready = rt.ready_transitions("smoke", satisfied_constraints=set())
        prepared = rt.prepare_execution(
            ExecutionIntent(
                "smoke-effect",
                "publish",
                "github",
                {"artifact": "candidate"},
                "IDEMPOTENT",
                "smoke-idem",
                "proof-worker",
                "abc",
                {"status": "ok"},
                False,
            ),
            gateway_request={
                "runtime_id": "sol-6.2",
                "via_gateway": "sol-gateway",
                "authenticated_principal": "spiffe://sol/proof-worker",
                "policy_version": "6.2",
            },
            identity_claims=_claims(now),
            now_epoch=now,
        )
        fence = rt.acquire_execution_fence("publish", "proof-worker", ttl_seconds=120, now_epoch=now)
        rt.authorize_dispatch(
            "smoke-effect",
            authority_lease_id=None,
            actor="proof-worker",
            source_version="abc",
            now_epoch=now,
            worker="proof-worker",
            lease_epoch=fence["epoch"],
            fencing_token=fence["fencing_token"],
        )
        rt.mark_dispatched("smoke-effect", provider_ref="smoke-provider-run")
        readback = rt.observe_effect("smoke-effect", readback={"status": "ok"})
        evidence = {"status": "ok", "provider_ref": "smoke-provider-run"}
        proof = ProofEnvelope.from_evidence(
            proof_id="smoke-proof",
            subject="transition:publish",
            target="repo/main",
            operation="publish",
            issuer="reference-court",
            source_version="abc",
            evidence=evidence,
            max_age_seconds=600,
            evidence_class="DETERMINISTIC",
        )
        rt.register_verified_proof(
            proof,
            evidence,
            semantic_verifier=lambda p, e: e.get("status") == "ok",
            now_epoch=now,
        )
        committed = rt.verify_effect_and_commit(
            "smoke-effect",
            proof_ids=["smoke-proof"],
            now_epoch=now,
            satisfied_constraints=set(),
        )
        closure = committed["mission_closure"]
        integrity = rt.verify_integrity()
        rt.close()

        resumed = _runtime(root)
        resumed_closure = resumed.evaluate_mission(
            "smoke",
            proof_ids=["smoke-proof"],
            now_epoch=now,
            satisfied_constraints=set(),
        )
        resumed_integrity = resumed.verify_integrity()
        frozen_ready = resumed.ready_transitions("smoke", satisfied_constraints=set())
        resumed.close()

    gates = {
        "adversarial_unit_court": tests.testsRun >= 15 and tests.wasSuccessful(),
        "state_transition_planning": ready == ["publish"],
        "transactional_effect_preparation": prepared["state"] == "PREPARED",
        "fenced_dispatch": fence["fencing_token"] >= 1,
        "provider_readback": readback["match"],
        "proof_gated_commit": committed["state"] == "VERIFIED",
        "observed_reality_closure": closure["state"] == "VERIFIED_REALITY",
        "verified_reality_execution_freeze": frozen_ready == [],
        "event_chain_integrity": integrity["event_chain_valid"],
        "restart_integrity": resumed_integrity["event_chain_valid"],
        "restart_reality_closure": resumed_closure["state"] == "VERIFIED_REALITY",
    }
    receipt = {
        "programme": "SOL-6.2-TRANSACTIONAL-SELF-VERIFYING-RUNTIME",
        "version": "6.2",
        "provider": "github-actions-reference-runtime",
        "generated_at": utc_now(),
        "unit_tests_run": tests.testsRun,
        "gates": gates,
        "truth_boundary": {
            "source_runtime_implemented": True,
            "deterministic_reference_proof": True,
            "transactional_single_shared_filesystem": True,
            "provider_effect_proof_binding_enforced_in_reference_runtime": True,
            "multi_region_consensus": False,
            "provider_live_production_cutover": False,
            "provider_identity_inherited": False,
            "continuous_background_execution": False,
            "market_superiority_claim": False,
        },
    }
    receipt["status"] = "SOL_6_2_REFERENCE_RUNTIME_VERIFIED" if all(gates.values()) else "FAILED"
    receipt["sha256"] = digest(receipt)
    (output / "sol-62-runtime-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if receipt["status"] != "SOL_6_2_REFERENCE_RUNTIME_VERIFIED":
        raise AssertionError(json.dumps(receipt, indent=2, sort_keys=True))
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output), indent=2, sort_keys=True))

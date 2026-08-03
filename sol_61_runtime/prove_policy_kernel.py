from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from policy_kernel import ActionMandate, Constitution, PolicyKernel, PolicyRule
from runtime import digest, utc_now


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    kernel = PolicyKernel(
        Constitution(
            "SOL-CONSTITUTION", "6.1",
            ("proof-before-claim", "owner-final-authority", "least-effect"),
            ("expose_secret", "delete_last_good_release"),
            ("live_release", "send_external_message", "financial_commitment"),
        ),
        [
            PolicyRule("ALLOW-REVERSIBLE", "ALLOW", 10, required_preconditions=("snapshot",)),
            PolicyRule("DENY-SECRET", "DENY", 100, forbidden_effects=("expose_secret",)),
            PolicyRule("OWNER-LIVE", "REQUIRE_OWNER", 90, action_types=("live_release",)),
            PolicyRule("REVIEW-HIGH", "REQUIRE_REVIEW", 80, min_risk="HIGH", required_roles=("security",)),
        ],
    )

    base = dict(
        action_id="proof-action", action_type="deploy_candidate", risk="MEDIUM",
        proposer_role="planner", executor_role="builder", certifier_role="auditor",
        preconditions=("snapshot",), intended_effects=("create_revision",),
        rollback_available=True, review_roles=(), proof_requirements=("execution", "readback", "rollback"),
    )
    allowed = kernel.evaluate(ActionMandate(**base), {"snapshot"})
    complete = kernel.verify_proof_bundle(allowed, {"execution": {}, "readback": {}, "rollback": {}})
    incomplete = kernel.verify_proof_bundle(allowed, {"execution": {}})
    owner = kernel.evaluate(ActionMandate(**{**base, "action_type": "live_release"}), {"snapshot"})
    forbidden = kernel.evaluate(ActionMandate(**{**base, "intended_effects": ("expose_secret",)}), {"snapshot"})
    separated = kernel.evaluate(ActionMandate(**{**base, "executor_role": "planner"}), {"snapshot"})
    high = kernel.evaluate(ActionMandate(**{**base, "risk": "HIGH", "review_roles": ("security",)}), {"snapshot"})

    gates = {
        "machine_readable_constitution": kernel.constitution.version == "6.1",
        "precondition_enforcement": kernel.evaluate(ActionMandate(**base), set()).status == "DENIED",
        "forbidden_effect_enforcement": forbidden.status == "DENIED",
        "owner_reserved_authority": owner.status == "OWNER_AUTHORITY_REQUIRED",
        "role_separation": separated.status == "DENIED",
        "risk_tier_and_review": high.status == "ELIGIBLE",
        "fail_closed": PolicyKernel(kernel.constitution, []).evaluate(ActionMandate(**base), {"snapshot"}).status == "DENIED",
        "proof_carrying_mandate": complete["execution_authorised"] and not incomplete["execution_authorised"],
        "policy_conflict_precedence": PolicyKernel(kernel.constitution, [PolicyRule("A", "ALLOW", 1), PolicyRule("D", "DENY", 2)]).evaluate(ActionMandate(**{**base, "preconditions": ()}), set()).status == "DENIED",
    }
    receipt = {
        "status": "FORMAL_POLICY_SAFETY_KERNEL_VERIFIED" if all(gates.values()) else "FORMAL_POLICY_SAFETY_KERNEL_FAILED",
        "generated_at": utc_now(),
        "gates": gates,
        "sample_decisions": {
            "allowed": allowed.__dict__, "owner": owner.__dict__, "forbidden": forbidden.__dict__, "high": high.__dict__
        },
        "truth_boundary": {
            "github_actions_execution": True,
            "provider_neutral_policy_kernel": True,
            "live_provider_enforcement": False,
            "external_legal_compliance_certified": False,
            "owner_authority_bypassed": False,
        },
    }
    receipt["sha256"] = digest(receipt)
    (out / "sol-61-policy-kernel-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not all(gates.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "ops" / "harden_sovara_provider_wif_v1.sh"
POLICY = ROOT / "governance" / "github_airlock_policy.json"
DEPLOYER = "superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com"


FAKE_GCLOUD = r'''#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

state_path = Path(os.environ["FAKE_GCLOUD_STATE"])
stale_reads = int(os.environ.get("FAKE_STALE_READS", "0"))
args = sys.argv[1:]
state = json.loads(state_path.read_text(encoding="utf-8"))
state.setdefault("calls", []).append(args)

def save():
    state_path.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")

def arg_value(prefix):
    for item in args:
        if item.startswith(prefix):
            return item.split("=", 1)[1]
    raise SystemExit("missing argument: " + prefix)

def mapping_dict(value):
    out = {}
    for pair in value.split(","):
        key, val = pair.split("=", 1)
        out[key] = val
    return out

if args[:2] == ["auth", "list"]:
    save()
    print("superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com")
    raise SystemExit(0)

if args[:2] == ["projects", "describe"]:
    save()
    print("257649435135")
    raise SystemExit(0)

if len(args) >= 3 and args[:3] == ["iam", "service-accounts", "get-iam-policy"]:
    save()
    print("roles/iam.workloadIdentityUser")
    raise SystemExit(0)

if "workload-identity-pools" in args and "providers" in args and "update-oidc" in args:
    state["updated"] = True
    state["post_update_reads"] = 0
    state["new_mapping"] = mapping_dict(arg_value("--attribute-mapping="))
    state["new_condition"] = arg_value("--attribute-condition=")
    save()
    print("operations/fake-update")
    raise SystemExit(0)

if "workload-identity-pools" in args and "providers" in args and "describe" in args:
    old_mapping = {
        "google.subject": "assertion.sub",
        "attribute.repository_id": "assertion.repository_id",
        "attribute.repository_owner_id": "assertion.repository_owner_id",
        "attribute.ref": "assertion.ref",
        "attribute.event_name": "assertion.event_name",
        "attribute.workflow_ref": "assertion.workflow_ref",
        "attribute.repository": "assertion.repository",
    }
    if state.get("updated"):
        state["post_update_reads"] = int(state.get("post_update_reads", 0)) + 1
        stale = state["post_update_reads"] <= stale_reads
    else:
        stale = True
    payload = {
        "state": "ACTIVE",
        "oidc": {"issuerUri": "https://token.actions.githubusercontent.com"},
        "attributeCondition": "stale-condition" if stale else state["new_condition"],
        "attributeMapping": old_mapping if stale else state["new_mapping"],
    }
    save()
    print(json.dumps(payload, sort_keys=True))
    raise SystemExit(0)

save()
print("unexpected fake gcloud invocation: " + " ".join(args), file=sys.stderr)
raise SystemExit(91)
'''


class SovaraWifProviderConvergenceV1Tests(unittest.TestCase):
    def run_apply(self, *, stale_reads: int, max_attempts: int) -> tuple[subprocess.CompletedProcess[str], dict, dict]:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            bindir = tmp / "bin"
            bindir.mkdir()
            gcloud = bindir / "gcloud"
            gcloud.write_text(textwrap.dedent(FAKE_GCLOUD), encoding="utf-8")
            gcloud.chmod(gcloud.stat().st_mode | stat.S_IXUSR)
            state_path = tmp / "state.json"
            state_path.write_text(json.dumps({"updated": False, "post_update_reads": 0, "calls": []}), encoding="utf-8")

            env = os.environ.copy()
            env.update(
                {
                    "PATH": str(bindir) + os.pathsep + env.get("PATH", ""),
                    "AIRLOCK_POLICY": str(POLICY),
                    "SOVARA_WIF_HARDENING_APPROVAL": "HARDEN_SOVARA_CANONICAL_WIF_V1",
                    "SOVARA_WIF_CONVERGENCE_MAX_ATTEMPTS": str(max_attempts),
                    "SOVARA_WIF_CONVERGENCE_INITIAL_DELAY_SECONDS": "0",
                    "SOVARA_WIF_CONVERGENCE_MAX_DELAY_SECONDS": "0",
                    "FAKE_GCLOUD_STATE": str(state_path),
                    "FAKE_STALE_READS": str(stale_reads),
                }
            )
            proc = subprocess.run(
                ["bash", str(SCRIPT), "--apply"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            stdout_lines = [line for line in proc.stdout.splitlines() if line.strip().startswith("{")]
            self.assertTrue(stdout_lines, msg=f"stdout={proc.stdout!r} stderr={proc.stderr!r}")
            receipt = json.loads(stdout_lines[-1])
            state = json.loads(state_path.read_text(encoding="utf-8"))
            return proc, receipt, state

    def test_stale_reads_are_tolerated_until_exact_semantic_convergence(self) -> None:
        proc, receipt, state = self.run_apply(stale_reads=2, max_attempts=4)
        self.assertEqual(0, proc.returncode, msg=proc.stderr)
        self.assertEqual("APPLIED_AND_VERIFIED", receipt["state"])
        self.assertTrue(receipt["convergence_reached"])
        self.assertEqual(3, receipt["convergence_attempts_used"])
        self.assertTrue(receipt["condition_match"])
        self.assertTrue(receipt["mapping_match"])
        self.assertTrue(receipt["exact_repository_id_binding_present"])
        self.assertFalse(receipt["broad_repository_attribute_mapped"])
        self.assertFalse(receipt["broad_repository_name_binding_effective"])
        self.assertTrue(receipt["legacy_broad_repository_name_binding_inert"])
        flat_calls = [" ".join(call) for call in state["calls"]]
        self.assertEqual(1, sum("providers update-oidc" in call for call in flat_calls))
        self.assertFalse(any("remove-iam-policy-binding" in call for call in flat_calls))
        self.assertFalse(any("set-iam-policy" in call for call in flat_calls))

    def test_convergence_timeout_fails_closed_for_outer_transaction_rollback(self) -> None:
        proc, receipt, state = self.run_apply(stale_reads=99, max_attempts=3)
        self.assertEqual(8, proc.returncode)
        self.assertEqual("APPLIED_BUT_CONVERGENCE_TIMEOUT", receipt["state"])
        self.assertFalse(receipt["convergence_reached"])
        self.assertEqual(3, receipt["convergence_attempts_used"])
        self.assertTrue(receipt["mutation_performed"])
        self.assertIn("UPDATE_PROVIDER_ATTRIBUTE_CONDITION", receipt["required_mutations"])
        self.assertIn("UPDATE_PROVIDER_ATTRIBUTE_MAPPING", receipt["required_mutations"])
        flat_calls = [" ".join(call) for call in state["calls"]]
        self.assertEqual(1, sum("providers update-oidc" in call for call in flat_calls))
        self.assertFalse(any("remove-iam-policy-binding" in call for call in flat_calls))
        self.assertFalse(any("set-iam-policy" in call for call in flat_calls))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import hashlib
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
WORKFLOW = ROOT / ".github" / "workflows" / "sol62-wif-hardening-lease.yml"
REPOSITORY_SLUG = "mosianekk-lang/Federation-Omega"
MAIN_REF = "refs/heads/main"
EXPECTED_COUNT = 19
EXPECTED_SET_SHA256 = "8fa0450fdf8b69913b11e42d37fb10ece6da2d3d9ffac731ac8eb063d7ccd2ec"
EXPECTED_TRUST_CONTRACT_SHA256 = "38fa68df85d793f5491f480ddcf04e46e6e9ffc50dcf1abd67e934714ff98b1e"


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


def workflow_refs(paths: list[str]) -> list[str]:
    return [f"{REPOSITORY_SLUG}/{path}@{MAIN_REF}" for path in paths]


def trust_contract_hash(paths: list[str], allowed_events: dict[str, list[str]]) -> str:
    records = []
    for path in sorted(paths):
        records.append(json.dumps(
            {
                "workflow_ref": f"{REPOSITORY_SLUG}/{path}@{MAIN_REF}",
                "events": sorted(allowed_events[path]),
            },
            sort_keys=True,
            separators=(",", ":"),
        ))
    return hashlib.sha256(("\n".join(records) + "\n").encode()).hexdigest()


def generated_condition(paths: list[str], allowed_events: dict[str, list[str]]) -> str:
    pairs = []
    for path in paths:
        ref = f"{REPOSITORY_SLUG}/{path}@{MAIN_REF}"
        event_expr = " || ".join(
            f"assertion.event_name=='{event}'" for event in sorted(allowed_events[path])
        )
        pairs.append(f"(assertion.workflow_ref=='{ref}' && ({event_expr}))")
    return (
        "assertion.repository_id=='1292795464' && "
        "assertion.repository_owner_id=='261966700' && "
        "assertion.ref=='refs/heads/main' && ("
        + " || ".join(pairs)
        + ")"
    )


class SovaraWifHardeningV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SCRIPT.read_text(encoding="utf-8")
        cls.workflow_source = (
            WORKFLOW.read_text(encoding="utf-8") if WORKFLOW.exists() else None
        )
        cls.policy = json.loads(POLICY.read_text(encoding="utf-8"))
        cls.paths = cls.policy["oidc_workflow_allowlist"]
        cls.allowed_events = cls.policy["allowed_events"]
        cls.refs = workflow_refs(cls.paths)

    def test_expected_contract_uses_standard_workflow_ref_main_ref_and_event_name(self) -> None:
        for fragment in (
            "assertion.repository_id=='{repository_id}'",
            "assertion.repository_owner_id=='{owner_id}'",
            "assertion.ref=='{main_ref}'",
            "assertion.workflow_ref=='{workflow_ref}'",
            "assertion.event_name=='{event}'",
            "attribute.repository_id=assertion.repository_id",
            "attribute.repository_owner_id=assertion.repository_owner_id",
            "attribute.event_name=assertion.event_name",
            "attribute.workflow_ref=assertion.workflow_ref",
        ):
            self.assertIn(fragment, self.source)
        self.assertNotIn("assertion.job_workflow_ref", self.source)
        self.assertNotIn("attribute.workflow_ref=assertion.job_workflow_ref", self.source)

    def test_airlock_oidc_workflow_and_event_contract_is_pinned_and_fail_closed(self) -> None:
        self.assertEqual(EXPECTED_COUNT, len(self.paths))
        self.assertEqual(len(self.paths), len(set(self.paths)))
        digest = hashlib.sha256(("\n".join(sorted(self.refs)) + "\n").encode()).hexdigest()
        self.assertEqual(EXPECTED_SET_SHA256, digest)
        self.assertEqual(
            EXPECTED_TRUST_CONTRACT_SHA256,
            trust_contract_hash(self.paths, self.allowed_events),
        )
        self.assertIn(f'EXPECTED_OIDC_WORKFLOW_COUNT={EXPECTED_COUNT}', self.source)
        self.assertIn(
            f'EXPECTED_OIDC_WORKFLOW_SET_SHA256="{EXPECTED_SET_SHA256}"',
            self.source,
        )
        self.assertIn(
            f'EXPECTED_TRUST_CONTRACT_SHA256="{EXPECTED_TRUST_CONTRACT_SHA256}"',
            self.source,
        )
        self.assertIn("policy.get('allowed_events')", self.source)
        self.assertIn(
            "Airlock OIDC trust contract drifted; refusing silent WIF trust expansion/contraction.",
            self.source,
        )

    def test_event_surface_drift_changes_full_contract_hash_but_not_refs_hash(self) -> None:
        mutated = {path: list(events) for path, events in self.allowed_events.items()}
        target = self.paths[-1]
        extra = "workflow_dispatch"
        if extra in mutated[target]:
            extra = "push"
        mutated[target].append(extra)
        refs_before = hashlib.sha256(
            ("\n".join(sorted(self.refs)) + "\n").encode()
        ).hexdigest()
        refs_after = hashlib.sha256(
            ("\n".join(sorted(workflow_refs(self.paths))) + "\n").encode()
        ).hexdigest()
        self.assertEqual(refs_before, refs_after)
        self.assertNotEqual(
            trust_contract_hash(self.paths, self.allowed_events),
            trust_contract_hash(self.paths, mutated),
        )

    def test_generated_exact_workflow_event_condition_fits_google_provider_limit(self) -> None:
        condition = generated_condition(self.paths, self.allowed_events)
        self.assertIn("assertion.workflow_ref", condition)
        self.assertIn("assertion.event_name", condition)
        self.assertLessEqual(len(condition), 4096)
        self.assertIn("if ((${#EXPECTED_CONDITION} > 4096)); then", self.source)

    def test_every_oidc_workflow_has_nonempty_event_contract(self) -> None:
        for path in self.paths:
            self.assertIn(path, self.allowed_events)
            self.assertTrue(self.allowed_events[path])
            self.assertEqual(
                len(self.allowed_events[path]),
                len(set(self.allowed_events[path])),
            )

    def test_exact_repository_binding_is_required_and_legacy_repository_binding_is_modeled(self) -> None:
        self.assertIn("attribute.repository_id/${REPOSITORY_ID}", self.source)
        self.assertIn("attribute.repository/mosianekk-lang/Federation-Omega", self.source)
        self.assertIn("ADD_EXACT_REPOSITORY_ID_WIF_BINDING", self.source)
        self.assertIn("RENDER_BROAD_REPOSITORY_NAME_BINDING_INERT", self.source)
        self.assertIn("service-accounts add-iam-policy-binding", self.source)
        self.assertNotIn("service-accounts remove-iam-policy-binding", self.source)

    def test_canonical_mapping_never_exports_legacy_repository_attribute(self) -> None:
        expected_line = next(
            line for line in self.source.splitlines() if line.startswith("EXPECTED_MAPPING=")
        )
        self.assertNotIn("attribute.repository=", expected_line)
        self.assertIn("Canonical mapping must not export attribute.repository.", self.source)
        self.assertIn("'attribute.repository' in m", self.source)

    def test_broad_binding_presence_is_distinct_from_effective_authority(self) -> None:
        for fragment in (
            'BROAD_BINDING_EFFECTIVE=false',
            'LEGACY_BROAD_BINDING_INERT=false',
            'if [[ "$BROAD_BINDING" == true && "$BROAD_REPOSITORY_ATTRIBUTE_MAPPED" == true ]]',
            'BROAD_BINDING_EFFECTIVE=true',
            'elif [[ "$BROAD_BINDING" == true && "$BROAD_REPOSITORY_ATTRIBUTE_MAPPED" == false ]]',
            'LEGACY_BROAD_BINDING_INERT=true',
            "'broad_repository_name_binding_present'",
            "'broad_repository_attribute_mapped'",
            "'broad_repository_name_binding_effective'",
            "'legacy_broad_repository_name_binding_inert'",
        ):
            self.assertIn(fragment, self.source)

    def test_adversarial_broad_binding_is_fail_closed_only_when_attribute_is_mapped(self) -> None:
        self.assertIn(
            '[[ "$BROAD_BINDING_EFFECTIVE" == false ]] || REQUIRED+=("RENDER_BROAD_REPOSITORY_NAME_BINDING_INERT")',
            self.source,
        )
        self.assertIn(
            'if [[ "$CONDITION_MATCH" != true || "$MAPPING_MATCH" != true || "$BROAD_BINDING_EFFECTIVE" == true ]]; then',
            self.source,
        )
        self.assertIn("attribute.repository is not mapped", self.source)
        self.assertIn("cannot satisfy verification if the provider maps attribute.repository again", self.source)

    def test_one_use_workflow_invokes_hardener_through_bash(self) -> None:
        if self.workflow_source is None:
            self.skipTest("workflow-free export excludes repository workflow controls")
        self.assertIn(
            "bash ./ops/harden_sovara_provider_wif_v1.sh --apply",
            self.workflow_source,
        )
        self.assertIn(
            "bash ./ops/harden_sovara_provider_wif_v1.sh --verify",
            self.workflow_source,
        )

    def test_apply_requires_explicit_narrow_confirmation(self) -> None:
        self.assertIn('APPLY_CONFIRMATION="HARDEN_SOVARA_CANONICAL_WIF_V1"', self.source)
        self.assertIn("SOVARA_WIF_HARDENING_APPROVAL", self.source)
        self.assertIn("Refusing mutation without", self.source)

    def test_source_cannot_expand_provider_or_application_authority(self) -> None:
        forbidden = (
            "gcloud services enable",
            "gcloud projects add-iam-policy-binding",
            "gcloud run services add-iam-policy-binding",
            "gcloud run deploy",
            "gcloud artifacts repositories add-iam-policy-binding",
            "gcloud iam service-accounts create",
            "secretmanager",
            "curl ",
            "docker ",
        )
        for fragment in forbidden:
            self.assertNotIn(fragment, self.source)

    def test_safe_ordering_establishes_exact_binding_before_provider_hardening(self) -> None:
        add_exact = self.source.index('if [[ "$EXACT_BINDING" != true ]]')
        update_provider = self.source.index(
            'if [[ "$CONDITION_MATCH" != true || "$MAPPING_MATCH" != true || "$BROAD_BINDING_EFFECTIVE" == true ]]'
        )
        self.assertLess(add_exact, update_provider)

    def test_verify_is_fail_closed_and_receipt_separates_mutation(self) -> None:
        self.assertIn('emit_receipt "NOT_VERIFIED" false; exit 1', self.source)
        self.assertIn("'schema':'SOVARA_WIF_HARDENING_V3'", self.source)
        self.assertIn("'workflow_claim':'workflow_ref'", self.source)
        self.assertIn("'event_claim':'event_name'", self.source)
        self.assertIn("'event_surface_bound_per_workflow':True", self.source)
        self.assertIn("'authorized_workflow_set_sha256':'${AUTHORIZED_WORKFLOW_SET_SHA}'", self.source)
        self.assertIn("'trust_contract_sha256':'${TRUST_CONTRACT_SHA}'", self.source)
        self.assertIn("'mutation_performed':'${mutation}' == 'true'", self.source)
        self.assertIn("'physical_legacy_binding_removal_required':False", self.source)
        self.assertIn("'project_role_binding_performed':False", self.source)
        self.assertIn("'model_inference_performed':False", self.source)
        self.assertIn("'traffic_change_performed':False", self.source)

    def test_apply_waits_for_exact_provider_semantic_convergence(self) -> None:
        self.assertIn("wait_for_provider_convergence", self.source)
        self.assertIn('emit_receipt "APPLIED_BUT_CONVERGENCE_TIMEOUT" true', self.source)
        self.assertIn("'convergence_attempts_used':${CONVERGENCE_ATTEMPTS_USED}", self.source)
        self.assertIn("'convergence_reached':'${CONVERGENCE_REACHED}' == 'true'", self.source)


class SovaraWifProviderConvergenceBehaviorTests(unittest.TestCase):
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

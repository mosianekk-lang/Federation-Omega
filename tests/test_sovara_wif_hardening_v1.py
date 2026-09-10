from __future__ import annotations

import hashlib
import json
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
        cls.workflow_source = (\n            WORKFLOW.read_text(encoding="utf-8") if WORKFLOW.exists() else None\n        )
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

    def test_exact_repository_id_binding_replaces_broad_repository_name_binding(self) -> None:
        self.assertIn("attribute.repository_id/${REPOSITORY_ID}", self.source)
        self.assertIn("attribute.repository/mosianekk-lang/Federation-Omega", self.source)
        self.assertIn("ADD_EXACT_REPOSITORY_ID_WIF_BINDING", self.source)
        self.assertIn("REMOVE_BROAD_REPOSITORY_NAME_WIF_BINDING", self.source)
        self.assertIn("service-accounts add-iam-policy-binding", self.source)
        self.assertIn("service-accounts remove-iam-policy-binding", self.source)

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

    def test_safe_ordering_establishes_exact_binding_then_hardens_then_removes_broad(self) -> None:
        add_exact = self.source.index('if [[ "$EXACT_BINDING" != true ]]')
        update_provider = self.source.index('if [[ "$CONDITION_MATCH" != true || "$MAPPING_MATCH" != true ]]')
        remove_broad = self.source.index('if [[ "$BROAD_BINDING" == true ]]')
        self.assertLess(add_exact, update_provider)
        self.assertLess(update_provider, remove_broad)

    def test_verify_is_fail_closed_and_receipt_separates_mutation(self) -> None:
        self.assertIn('emit_receipt "NOT_VERIFIED" false; exit 1', self.source)
        self.assertIn("'schema':'SOVARA_WIF_HARDENING_V3'", self.source)
        self.assertIn("'workflow_claim':'workflow_ref'", self.source)
        self.assertIn("'event_claim':'event_name'", self.source)
        self.assertIn("'event_surface_bound_per_workflow':True", self.source)
        self.assertIn("'authorized_workflow_set_sha256':'${AUTHORIZED_WORKFLOW_SET_SHA}'", self.source)
        self.assertIn("'trust_contract_sha256':'${TRUST_CONTRACT_SHA}'", self.source)
        self.assertIn("'mutation_performed':'${mutation}' == 'true'", self.source)
        self.assertIn("'project_role_binding_performed':False", self.source)
        self.assertIn("'model_inference_performed':False", self.source)
        self.assertIn("'traffic_change_performed':False", self.source)


if __name__ == "__main__":
    unittest.main()

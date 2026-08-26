import unittest

from ops.sovara_provider_credential_reference import (
    CredentialReference,
    CredentialReferenceError,
    build_binding_plan,
    choose_openrouter_binding_route,
)


class ProviderCredentialReferenceTests(unittest.TestCase):
    def test_gcp_reference_is_value_free(self):
        plan = build_binding_plan(
            CredentialReference("openrouter", "gcp_secret_name", "sovara-openrouter-runtime"),
            resolution_surface="google_cloud",
        )
        self.assertFalse(plan.value_exposed)
        self.assertFalse(plan.value_persisted)
        self.assertFalse(plan.provider_call_performed)
        self.assertEqual("PROVIDER_CREDENTIAL", plan.destination_alias)
        self.assertIn("EXACT_NONCE_SEMANTIC_READBACK", plan.proof_required)

    def test_script_property_reference_is_symbolic(self):
        plan = build_binding_plan(
            CredentialReference("openrouter", "script_property_name", "SOVARA_ROUTER_CREDENTIAL"),
            resolution_surface="apps_script",
        )
        self.assertEqual("SOVARA_ROUTER_CREDENTIAL", plan.source_locator)
        self.assertEqual("apps_script", plan.resolution_surface)

    def test_drive_document_title_reference_is_value_free(self):
        plan = build_binding_plan(
            CredentialReference("openrouter", "drive_document_title", "SOVARA OpenRouter Credential Reference"),
            resolution_surface="apps_script",
        )
        self.assertEqual("drive_document_title", plan.source_kind)
        self.assertFalse(plan.value_exposed)
        self.assertFalse(plan.value_persisted)
        self.assertFalse(plan.provider_call_performed)

    def test_drive_document_title_rejects_url_or_secret_like_locator(self):
        # Build the synthetic shape at runtime so the public leak scanner never
        # receives a complete credential-looking fixture in repository text.
        synthetic_key_shape = "s" + "k" + "-or-v1-" + "not-a-real-secret-but-secret-like"
        for locator in (
            "https://drive.google.com/private-ref",
            synthetic_key_shape,
            "Bearer not-a-real-token-value",
        ):
            with self.subTest(locator=locator):
                with self.assertRaises(CredentialReferenceError):
                    build_binding_plan(
                        CredentialReference("openrouter", "drive_document_title", locator),
                        resolution_surface="apps_script",
                    )

    def test_environment_reference_rejects_literal_like_value(self):
        with self.assertRaises(CredentialReferenceError):
            build_binding_plan(
                CredentialReference("openrouter", "environment_alias", "literal-value-here"),
                resolution_surface="private_runtime",
            )

    def test_unknown_reference_kind_fails_closed(self):
        with self.assertRaises(CredentialReferenceError):
            build_binding_plan(
                CredentialReference("openrouter", "literal", "SOME_VALUE"),
                resolution_surface="private_runtime",
            )

    def test_google_route_wins_when_admin_is_ready(self):
        decision = choose_openrouter_binding_route(
            google_admin_ready=True,
            apps_script_property_ready=True,
            owner_drive_document_ready=True,
        )
        self.assertEqual("REUSE_OPTIMISE", decision["family"])
        self.assertEqual("google_cloud_secret_reference", decision["route"])

    def test_apps_script_property_route_precedes_drive_document(self):
        decision = choose_openrouter_binding_route(
            google_admin_ready=False,
            apps_script_property_ready=True,
            owner_drive_document_ready=True,
        )
        self.assertEqual("COMPOSE_EXTEND", decision["family"])
        self.assertEqual("apps_script_property_reference", decision["route"])

    def test_owner_drive_document_route_is_available_without_value_transport(self):
        decision = choose_openrouter_binding_route(
            google_admin_ready=False,
            apps_script_property_ready=False,
            owner_drive_document_ready=True,
        )
        self.assertEqual("COMPOSE_EXTEND", decision["family"])
        self.assertEqual("apps_script_owner_drive_document_reference", decision["route"])
        self.assertFalse(decision["provider_call_performed"])

    def test_no_resolver_holds_without_provider_effect(self):
        decision = choose_openrouter_binding_route(
            google_admin_ready=False,
            apps_script_property_ready=False,
        )
        self.assertEqual("REVERSIBLE_EXPERIMENT", decision["family"])
        self.assertFalse(decision["provider_call_performed"])

    def test_fingerprint_is_deterministic(self):
        ref = CredentialReference("openrouter", "gcp_secret_name", "sovara-openrouter-runtime")
        a = build_binding_plan(ref, resolution_surface="google_cloud")
        b = build_binding_plan(ref, resolution_surface="google_cloud")
        self.assertEqual(a.fingerprint, b.fingerprint)


if __name__ == "__main__":
    unittest.main()

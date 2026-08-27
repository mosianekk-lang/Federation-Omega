from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evidenceops.capital_intelligence_os.authority import AuthorityGuard
from evidenceops.capital_intelligence_os.models import (
    ActionDisposition,
    ActionRequest,
    AuthorityLevel,
    Domain,
    InformationClass,
)
from evidenceops.capital_intelligence_os.provider_runtime import (
    PROVIDER_MAX_HTTP_BODY_BYTES,
    PROVIDER_SAFE_ROUTES,
)
from evidenceops.capital_intelligence_os.tenancy import TenantContext
from evidenceops.capital_intelligence_os.vault import (
    DocumentVault,
    MAX_SEARCH_TERMS,
)


class CIOSRC71SecurityAdmissionTests(unittest.TestCase):
    def test_provider_contract_matches_executable_route_and_body_profile(self) -> None:
        contract = json.loads(
            Path("evidenceops/capital_intelligence_os/PROVIDER_RUNTIME_CONTRACT.json").read_text(
                encoding="utf-8"
            )
        )
        declared = {
            tuple(route.split(" ", 1))
            for route in contract["safe_routes"]
        }
        self.assertEqual(set(PROVIDER_SAFE_ROUTES), declared)
        self.assertEqual(
            PROVIDER_MAX_HTTP_BODY_BYTES,
            contract["security"]["request_size_limit_bytes"],
        )
        self.assertFalse(contract["security"]["document_routes_enabled"])
        self.assertFalse(contract["maturity_boundary"]["production_claim"])

    def test_duplicate_content_cannot_downgrade_or_disclose_restricted_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = DocumentVault(Path(tmp) / "vault.sqlite")
            privileged = TenantContext("tenant", "admin", ("admin", "restricted_access"))
            operator = TenantContext("tenant", "operator", ("operator",))
            try:
                vault.ingest(
                    privileged,
                    logical_key="restricted-record",
                    filename="restricted.txt",
                    document_type="restricted schedule",
                    content_type="text/plain",
                    content=b"same classified bytes",
                    information_class=InformationClass.RESTRICTED,
                    source_id="source-restricted",
                )
                with self.assertRaisesRegex(PermissionError, "DOCUMENT_INGESTION_CONFLICT"):
                    vault.ingest(
                        operator,
                        logical_key="public-cover",
                        filename="public.txt",
                        document_type="public note",
                        content_type="text/plain",
                        content=b"same classified bytes",
                        information_class=InformationClass.PUBLIC,
                        source_id="source-public",
                    )
            finally:
                vault.close()

    def test_search_query_term_budget_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = DocumentVault(Path(tmp) / "vault.sqlite")
            ctx = TenantContext("tenant", "operator", ("operator",))
            try:
                query = " ".join(f"term{index}" for index in range(MAX_SEARCH_TERMS + 1))
                with self.assertRaisesRegex(ValueError, "too many terms"):
                    vault.search(ctx, query)
            finally:
                vault.close()

    def test_caller_flags_cannot_disguise_order_execution(self) -> None:
        decision = AuthorityGuard().evaluate(
            ActionRequest(
                "PLACE_ORDER",
                Domain.PUBLIC_MARKETS,
                Domain.PUBLIC_MARKETS,
                InformationClass.PUBLIC,
                external_effect=False,
                financial_effect=False,
                destructive=False,
                reversible=True,
                requested_authority=AuthorityLevel.A1_ASSISTED,
            )
        )
        self.assertEqual(ActionDisposition.DENY, decision.disposition)


if __name__ == "__main__":
    unittest.main()

import unittest

from evidenceops.capital_intelligence_os.quant_evidence_bridge import project_quant_evidence
from federation.capital_execution.venues.luno_account_observer import LunoCredentialReference, LunoReadOnlyAccountObserver


class LunoCIOSIntegrationV1Tests(unittest.TestCase):
    def test_quant_projection_does_not_inherit_execution_authority(self):
        evidence = project_quant_evidence({
            "strategy_id": "s1",
            "instrument_id": "XBTZAR",
            "evidence_ref": "receipt:1",
            "research_state": "RESEARCH_ADMITTED",
            "source_code_sha256": "a" * 64,
            "report_id": "r1",
            "provider_effect": False,
            "financial_effect": False,
            "metrics": {
                "total_return_pct": 20.0,
                "benchmark_return_pct": 10.0,
                "maximum_drawdown_pct": 12.0,
                "sharpe_ratio": 1.2,
                "sample_trades": 20,
                "robustness_score": 0.8,
                "regime_fit": 0.7,
                "liquidity_quality": 0.8,
            },
        })
        self.assertEqual(evidence.strategy_id, "s1")
        self.assertFalse(evidence.metadata["authority_inherited"])

    def test_quant_projection_rejects_financial_authority_smuggling(self):
        with self.assertRaises(PermissionError):
            project_quant_evidence({
                "strategy_id": "s1",
                "instrument_id": "XBTZAR",
                "evidence_ref": "receipt:1",
                "research_state": "RESEARCH_ADMITTED",
                "provider_effect": True,
                "financial_effect": False,
                "metrics": {
                    "total_return_pct": 20.0,
                    "benchmark_return_pct": 10.0,
                    "maximum_drawdown_pct": 12.0,
                    "sharpe_ratio": 1.2,
                    "sample_trades": 20,
                    "robustness_score": 0.8,
                    "regime_fit": 0.7,
                    "liquidity_quality": 0.8,
                },
            })

    def test_luno_account_observer_is_get_only_and_reference_bound(self):
        observed = {}

        def resolve(reference):
            self.assertEqual(reference, "secret://luno-observer")
            return "key-id", "secret-value"

        def transport(path, params, key_id, secret):
            observed["path"] = path
            observed["params"] = dict(params)
            self.assertEqual(key_id, "key-id")
            self.assertEqual(secret, "secret-value")
            return {"balance": [{"asset": "ZAR", "balance": "100.00", "reserved": "0"}]}

        observer = LunoReadOnlyAccountObserver(
            LunoCredentialReference("secret://luno-observer", ("Perm_R_Balance",)),
            resolve,
            transport,
        )
        result = observer.balances(assets=("ZAR",))
        self.assertEqual(result["balance"][0]["asset"], "ZAR")
        self.assertEqual(observed["path"], "/api/1/balance")
        with self.assertRaises(PermissionError):
            observer.create_order(pair="XBTZAR")
        with self.assertRaises(PermissionError):
            observer.withdraw(currency="ZAR")
        with self.assertRaises(PermissionError):
            observer.transfer(amount="1")

    def test_luno_observer_rejects_write_permission_expectation(self):
        with self.assertRaises(PermissionError):
            LunoCredentialReference("secret://luno", ("Perm_W_Orders",)).validate()


if __name__ == "__main__":
    unittest.main()

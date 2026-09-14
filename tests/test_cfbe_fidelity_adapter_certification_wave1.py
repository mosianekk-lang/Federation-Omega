from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from benchmarking.cfbe_omega.fidelity_adapter_certification import (
    CertificationError,
    load_profiles,
    run_certification,
)
from benchmarking.cfbe_omega.fidelity_adapter_certification.verify import (
    VerificationError,
    verify_scorecard,
)


EXPECTED = ("github", "google-drive", "gmail", "canva")


def observations(config: dict) -> dict:
    return {
        "schema": "CFBE-OMEGA-FIDELITY-ADAPTER-DISCOVERY-OBSERVATION-V1",
        "observedAt": "2026-08-30T23:40:21Z",
        "sourceHead": "a" * 40,
        "externalEffects": 0,
        "providerWrites": 0,
        "manualUserTasks": [],
        "platforms": [
            {
                "platformId": profile["platformId"],
                "connectorContractSha256": profile["connectorContractSha256"],
                "readCanaryState": (
                    "PASS_WITH_ROUTE_VARIANCE"
                    if profile["platformId"] == "github"
                    else "PASS"
                ),
                "proofRefs": [f"{profile['platformId']}:read-canary:public-safe"],
            }
            for profile in config["platforms"]
        ],
    }


class FidelityAdapterCertificationWave1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_profiles()

    def test_profile_portfolio_is_exact_and_symmetric(self) -> None:
        self.assertEqual(EXPECTED, tuple(item["platformId"] for item in self.config["platforms"]))
        expected = self.config["canonicalContract"]["requiredCapabilities"]
        for profile in self.config["platforms"]:
            self.assertEqual(expected, profile["adapterRoute"]["provides"])
            self.assertFalse(profile["adapterRoute"]["externalEffectRequired"])
            self.assertEqual("A1", profile["adapterRoute"]["authorityCeiling"])

    def test_four_local_courts_pass_through_bubbles_and_cfbe(self) -> None:
        scorecard = run_certification(self.config)
        self.assertEqual("LOCAL_COURTS_4_OF_4_PASS", scorecard["certificationState"])
        self.assertEqual(4, scorecard["comparison"]["courtPassCount"])
        self.assertEqual(0, scorecard["comparison"]["liveCanaryPassCount"])
        self.assertTrue(scorecard["comparison"]["profileSymmetry"])
        self.assertEqual(4, len(scorecard["bubblesWave"]["selectedWorkIds"]))
        self.assertFalse(scorecard["bubblesWave"]["providerEffectAuthorized"])
        self.assertTrue(all(item["courtPass"] for item in scorecard["courts"]))

    def test_live_read_canaries_bind_to_exact_contract_hashes(self) -> None:
        scorecard = run_certification(self.config, observations=observations(self.config))
        self.assertEqual(
            "LIVE_READ_CANARIES_4_OF_4_AND_LOCAL_COURTS_4_OF_4_PASS",
            scorecard["certificationState"],
        )
        self.assertEqual(4, scorecard["comparison"]["liveCanaryPassCount"])
        self.assertEqual("SUPPLIED_PUBLIC_SAFE", scorecard["connectorObservation"]["state"])
        receipt = verify_scorecard(scorecard)
        self.assertEqual("VERIFIED", receipt["decision"])
        self.assertEqual(0, receipt["externalEffects"])

    def test_certification_is_deterministic_for_fixed_inputs(self) -> None:
        first = run_certification(self.config, observations=observations(self.config))
        second = run_certification(self.config, observations=observations(self.config))
        self.assertEqual(first["receiptSha256"], second["receiptSha256"])
        self.assertEqual(first, second)

    def test_canonical_control_dilution_fails_all_courts_before_route_use(self) -> None:
        candidate = deepcopy(self.config["canonicalContract"])
        candidate["controls"]["providerMutationAllowed"] = True
        scorecard = run_certification(self.config, candidate_contract=candidate)
        self.assertEqual("COURT_FAILURE", scorecard["certificationState"])
        self.assertEqual(0, scorecard["comparison"]["courtPassCount"])
        for court in scorecard["courts"]:
            self.assertEqual("REJECT_DILUTION", court["resultState"])
            self.assertEqual([], court["selectedAdapters"])

    def test_effectful_profile_is_rejected_before_execution(self) -> None:
        changed = deepcopy(self.config)
        changed["platforms"][0]["adapterRoute"]["externalEffectRequired"] = True
        with self.assertRaisesRegex(CertificationError, "EXTERNAL_EFFECT_INVALID:github"):
            run_certification(changed)

    def test_observation_contract_drift_and_effects_fail_closed(self) -> None:
        changed = observations(self.config)
        changed["platforms"][2]["connectorContractSha256"] = "0" * 64
        with self.assertRaisesRegex(CertificationError, "OBSERVATION_PROFILE_CONTRACT_MISMATCH:gmail"):
            run_certification(self.config, observations=changed)
        changed = observations(self.config)
        changed["externalEffects"] = 1
        with self.assertRaisesRegex(CertificationError, "OBSERVATION_EXTERNAL_EFFECT_PRESENT"):
            run_certification(self.config, observations=changed)

    def test_independent_verifier_rejects_tampering_and_private_keys(self) -> None:
        scorecard = run_certification(self.config, observations=observations(self.config))
        tampered = deepcopy(scorecard)
        tampered["comparison"]["providerWrites"] = 1
        with self.assertRaisesRegex(VerificationError, "SCORECARD_RECEIPT_MISMATCH"):
            verify_scorecard(tampered)
        tampered = deepcopy(scorecard)
        tampered["connectorObservation"]["payload"]["platforms"][0]["email"] = "hidden"
        body = deepcopy(tampered)
        body.pop("receiptSha256")
        import hashlib

        tampered["receiptSha256"] = hashlib.sha256(
            json.dumps(body, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest()
        with self.assertRaisesRegex(VerificationError, "FORBIDDEN_OBSERVATION_KEY:email"):
            verify_scorecard(tampered)

        tampered = deepcopy(scorecard)
        tampered["connectorObservation"]["payload"]["platforms"][0]["proofRefs"] = [
            "github:read:user@example.com"
        ]
        observation_payload = tampered["connectorObservation"]["payload"]
        tampered["connectorObservation"]["sha256"] = hashlib.sha256(
            json.dumps(
                observation_payload,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        ).hexdigest()
        body = deepcopy(tampered)
        body.pop("receiptSha256")
        tampered["receiptSha256"] = hashlib.sha256(
            json.dumps(body, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest()
        with self.assertRaisesRegex(VerificationError, "EMAIL_LIKE_VALUE_IN_OBSERVATION"):
            verify_scorecard(tampered)

    def test_cli_atomically_writes_scorecard_and_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            observation_path = root / "observations.json"
            scorecard_path = root / "scorecard.json"
            verification_path = root / "verification.json"
            observation_path.write_text(json.dumps(observations(self.config)), encoding="utf-8")
            run = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "benchmarking.cfbe_omega.fidelity_adapter_certification",
                    "--observations",
                    str(observation_path),
                    "--output",
                    str(scorecard_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, run.returncode, run.stderr)
            verify = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "benchmarking.cfbe_omega.fidelity_adapter_certification.verify",
                    str(scorecard_path),
                    "--output",
                    str(verification_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, verify.returncode, verify.stderr)
            self.assertEqual("VERIFIED", json.loads(verification_path.read_text())["decision"])
            self.assertEqual([], list(root.glob(".*.tmp")))


if __name__ == "__main__":
    unittest.main()

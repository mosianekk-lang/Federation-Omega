from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "mobile" / "fuse-mobile" / "lab"
PROBE = LAB / "probe_android_connectivity.py"
SMOKE = LAB / "run_android_smoke.sh"

SPEC = importlib.util.spec_from_file_location("fuse_mobile_connectivity_probe", PROBE)
assert SPEC is not None and SPEC.loader is not None
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)

ONLINE = """\
NetworkProviders for:
Active default network: 101

Current Networks:
  NetworkAgentInfo{network{101} ni{WIFI CONNECTED} nc{[ Transports: WIFI Capabilities: NOT_METERED&INTERNET&NOT_RESTRICTED&TRUSTED&NOT_VPN&VALIDATED&FOREGROUND ]}}
"""
OFFLINE = """\
NetworkProviders for:
Active default network: none

Current Networks:
"""
STALE_NONDEFAULT = """\
Active default network: 102
Current Networks:
  NetworkAgentInfo{network{101} nc{[ Transports: WIFI Capabilities: INTERNET&VALIDATED ]}}
  NetworkAgentInfo{network{102} nc{[ Transports: CELLULAR Capabilities: INTERNET&NOT_RESTRICTED ]}}
"""
WRAPPED = """\
Active default network: 105
Current Networks:
  NetworkAgentInfo{network{105} ni{WIFI CONNECTED}
    Score(60)
    nc{[ Transports: WIFI Capabilities: NOT_METERED&INTERNET&TRUSTED&VALIDATED&FOREGROUND ]}
  }
"""


class FuseMobileMdtafConnectivityProbeTests(unittest.TestCase):
    def test_validated_internet_default_network_is_online(self) -> None:
        result = probe.inspect_connectivity(ONLINE)
        self.assertEqual(result["active_default_network"], "101")
        self.assertEqual(result["state"], "VALIDATED_ONLINE")

    def test_no_active_default_network_is_offline(self) -> None:
        result = probe.inspect_connectivity(OFFLINE)
        self.assertEqual(result["active_default_network"], "none")
        self.assertEqual(result["state"], "UNVALIDATED_OR_ABSENT")

    def test_stale_validated_nondefault_network_cannot_satisfy_baseline(self) -> None:
        result = probe.inspect_connectivity(STALE_NONDEFAULT)
        self.assertEqual(result["active_default_network"], "102")
        self.assertFalse(result["validated_capability"])
        self.assertNotEqual(result["state"], "VALIDATED_ONLINE")

    def test_validated_without_internet_capability_fails_closed(self) -> None:
        text = "Active default network: 7\nCurrent Networks:\n NetworkAgentInfo{network{7} nc{[ Capabilities: VALIDATED&NOT_RESTRICTED ]}}\n"
        result = probe.inspect_connectivity(text)
        self.assertTrue(result["validated_capability"])
        self.assertFalse(result["internet_capability"])
        self.assertNotEqual(result["state"], "VALIDATED_ONLINE")

    def test_unvalidated_token_does_not_match_validated(self) -> None:
        text = "Active default network: 7\nCurrent Networks:\n NetworkAgentInfo{network{7} nc{[ Capabilities: INTERNET&UNVALIDATED ]}}\n"
        result = probe.inspect_connectivity(text)
        self.assertFalse(result["validated_capability"])

    def test_wrapped_network_agent_is_supported(self) -> None:
        result = probe.inspect_connectivity(WRAPPED)
        self.assertEqual(result["state"], "VALIDATED_ONLINE")

    def test_unknown_format_fails_closed(self) -> None:
        result = probe.inspect_connectivity("garbled\n")
        self.assertEqual(result["active_default_network"], "UNKNOWN")
        self.assertNotEqual(result["state"], "VALIDATED_ONLINE")

    def test_smoke_uses_validated_default_network_for_baseline_loss_and_recovery(self) -> None:
        source = SMOKE.read_text(encoding="utf-8")
        self.assertIn("capture_connectivity_state baseline online", source)
        self.assertIn("capture_connectivity_state offline offline", source)
        self.assertIn("capture_connectivity_state recovery online", source)
        self.assertIn("ANDROID_ACTIVE_DEFAULT_NETWORK_INTERNET_VALIDATED", source)
        self.assertIn("offline_validated_default_absent", source)
        self.assertIn("recovery_validated_default_present", source)
        self.assertNotIn("network_reachable()", source)
        self.assertIn("icmp_diagnostic()", source)
        self.assertIn("baseline_ping_diagnostic_only", source)
        self.assertIn("offline_ping_blocked_diagnostic_only", source)
        self.assertIn("recovery_ping_diagnostic_only", source)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPLICATOR = ROOT / "mobile" / "fuse-mobile" / "lab" / "apply_owner_profile.py"


def load_applicator():
    spec = importlib.util.spec_from_file_location("fuse_mobile_mdtaf_apply_owner_profile", APPLICATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load owner-profile applicator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FuseMobileOwnerProfileV2Tests(unittest.TestCase):
    def test_v2_profile_accepts_real_world_variables_with_live_secret_boundary(self) -> None:
        module = load_applicator()
        profile = {
            "schema": "FUSE_OWNER_DEVICE_PROFILE_V2",
            "capture_controls": {
                "credentials_or_tokens_captured": False,
                "live_secret_clone_allowed": False,
                "public_repository_storage_allowed": False,
            },
            "application_ecology": {"installed_packages": [{"package": "example.app"}]},
            "content_structure_counts": {"sms": {"state": "CAPTURED", "count": 42}},
            "consent_bound_real_data": {"samples": {"sms": {"state": "CAPTURED", "records": ["fixture"]}}},
        }
        self.assertTrue(module.profile_secret_boundary_is_safe(profile))

    def test_v2_profile_rejects_live_secret_clone(self) -> None:
        module = load_applicator()
        profile = {
            "schema": "FUSE_OWNER_DEVICE_PROFILE_V2",
            "capture_controls": {
                "credentials_or_tokens_captured": False,
                "live_secret_clone_allowed": True,
                "public_repository_storage_allowed": False,
            },
        }
        self.assertFalse(module.profile_secret_boundary_is_safe(profile))

    def test_v2_applicator_preserves_unreproducible_variables_as_fidelity_gaps(self) -> None:
        source = APPLICATOR.read_text(encoding="utf-8")
        self.assertIn("FUSE_OWNER_DEVICE_PROFILE_V2", source)
        self.assertIn("application_ecology_requires_package_fixture_matrix_or_physical_validation", source)
        self.assertIn("content_structure_requires_fixture_generation_or_physical_validation", source)
        self.assertIn("consent_bound_real_data_requires_private_fixture_injection_or_physical_validation", source)
        self.assertIn('"sensitive_real_data_used_for_generic_avd_application": False', source)
        self.assertIn('"live_secret_material_used": False', source)
        self.assertNotIn("privacy-minimised capture", source)


if __name__ == "__main__":
    unittest.main()

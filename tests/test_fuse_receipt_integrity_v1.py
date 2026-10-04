from __future__ import annotations

import unittest

from federation.fuse_serving_kernel_v1 import EffectReceipt, PolicyDecisionReceipt


class FUSEReceiptIntegrityTests(unittest.TestCase):
    def test_effect_receipt_digest_is_load_bearing(self):
        forged = EffectReceipt(
            state="VERIFIED",
            observed_state={"status": "ok"},
            proof_axes=("PROVIDER_READBACK",),
            proof_refs=("provider://run",),
            provider_ref="run-1",
            receipt_sha256="0" * 64,
        )
        with self.assertRaisesRegex(ValueError, "FUSE_EFFECT_RECEIPT_HASH_MISMATCH"):
            forged.validate()

    def test_policy_receipt_digest_is_load_bearing(self):
        forged = PolicyDecisionReceipt(
            decision="ALLOW",
            policy_ref="git://policy",
            input_sha256="a" * 64,
            result_sha256="b" * 64,
            receipt_sha256="0" * 64,
        )
        with self.assertRaisesRegex(ValueError, "FUSE_POLICY_RECEIPT_HASH_MISMATCH"):
            forged.validate()


if __name__ == "__main__":
    unittest.main()

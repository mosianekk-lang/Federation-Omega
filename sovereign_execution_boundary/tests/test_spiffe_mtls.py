import ssl
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from seb.spiffe_mtls import (
    ExactSVIDAuthorizer, SpiffeAuthorizationError, server_ssl_context,
    validate_spiffe_id,
)


class SpiffeMTLSTests(unittest.TestCase):
    expected = "spiffe://federation.local/ns/seb/sa/mission-client"

    @staticmethod
    def cert(*uris: str) -> dict:
        return {"subjectAltName": tuple(("URI", uri) for uri in uris)}

    def test_exact_svid_is_authorized(self):
        authorizer = ExactSVIDAuthorizer((self.expected,))
        self.assertEqual(authorizer.authorize(self.cert(self.expected)), self.expected)

    def test_rogue_svid_in_same_trust_domain_is_rejected(self):
        authorizer = ExactSVIDAuthorizer((self.expected,))
        rogue = "spiffe://federation.local/ns/rogue/sa/mission-client"
        with self.assertRaises(SpiffeAuthorizationError):
            authorizer.authorize(self.cert(rogue))

    def test_missing_and_ambiguous_svid_are_rejected(self):
        authorizer = ExactSVIDAuthorizer((self.expected,))
        for certificate in (None, {}, self.cert(self.expected, self.expected)):
            with self.subTest(certificate=certificate):
                with self.assertRaises(SpiffeAuthorizationError):
                    authorizer.authorize(certificate)

    def test_noncanonical_ids_are_rejected(self):
        for identity in ("spiffe://FEDERATION.local/a", "spiffe://federation.local/",
                         "spiffe://federation.local/a?b", "https://federation.local/a"):
            with self.subTest(identity=identity):
                with self.assertRaises(ValueError):
                    validate_spiffe_id(identity)

    def test_tls_context_requires_client_certificate_and_trust_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / name for name in ("svid.pem", "key.pem", "bundle.pem")]
            for path in paths:
                path.write_text("test")
            context = Mock()
            with patch("ssl.SSLContext", return_value=context), \
                    patch.object(context, "load_cert_chain") as load_chain, \
                    patch.object(context, "load_verify_locations") as load_bundle:
                result = server_ssl_context(*paths)
            self.assertIs(result, context)
            self.assertEqual(result.verify_mode, ssl.CERT_REQUIRED)
            self.assertEqual(result.minimum_version, ssl.TLSVersion.TLSv1_2)
            load_chain.assert_called_once_with(str(paths[0]), str(paths[1]))
            load_bundle.assert_called_once_with(cafile=str(paths[2]))


if __name__ == "__main__":
    unittest.main()

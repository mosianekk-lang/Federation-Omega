#!/usr/bin/env python3
"""Hosted cryptographic proof: trusted SVID accepted, trusted rogue rejected."""
from __future__ import annotations
import json, ssl, subprocess, tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib import error, request
from seb.spiffe_mtls import ExactSVIDAuthorizer, SpiffeAuthorizationError, server_ssl_context

EXPECTED = "spiffe://federation.local/ns/seb/sa/mission-client"
ROGUE = "spiffe://federation.local/ns/rogue/sa/mission-client"

def run(*args: str, cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def issue(d: Path, name: str, uri: str, server: bool = False) -> None:
    (d / f"{name}.cnf").write_text(f"[v3]\nsubjectAltName=URI:{uri}\nextendedKeyUsage={'serverAuth' if server else 'clientAuth'}\n")
    run("openssl", "req", "-new", "-newkey", "rsa:2048", "-nodes", "-subj", f"/CN={name}", "-keyout", f"{name}.key", "-out", f"{name}.csr", cwd=d)
    run("openssl", "x509", "-req", "-in", f"{name}.csr", "-CA", "ca.pem", "-CAkey", "ca.key", "-CAcreateserial", "-days", "1", "-sha256", "-extfile", f"{name}.cnf", "-extensions", "v3", "-out", f"{name}.pem", cwd=d)

class Handler(BaseHTTPRequestHandler):
    authorizer = ExactSVIDAuthorizer((EXPECTED,))
    def do_GET(self) -> None:
        try:
            self.authorizer.authorize(self.connection.getpeercert())
        except SpiffeAuthorizationError:
            self.send_response(403)
        else:
            self.send_response(204)
        self.end_headers()
    def log_message(self, *_: object) -> None:
        pass

def main() -> None:
    with tempfile.TemporaryDirectory(prefix="seb-spiffe-proof-") as temporary:
        d = Path(temporary)
        run("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=proof-ca", "-keyout", "ca.key", "-out", "ca.pem", cwd=d)
        issue(d, "server", "spiffe://federation.local/ns/seb/sa/api", True)
        issue(d, "client", EXPECTED)
        issue(d, "rogue", ROGUE)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.socket = server_ssl_context(d / "server.pem", d / "server.key", d / "ca.pem").wrap_socket(server.socket, server_side=True)
        thread = Thread(target=server.serve_forever, daemon=True); thread.start()
        outcomes = {}
        try:
            url = f"https://127.0.0.1:{server.server_port}/"
            for name in ("client", "rogue"):
                context = ssl.create_default_context(cafile=str(d / "ca.pem")); context.check_hostname = False
                context.load_cert_chain(d / f"{name}.pem", d / f"{name}.key")
                try:
                    with request.urlopen(url, context=context, timeout=3) as response: outcomes[name] = response.status
                except error.HTTPError as exc: outcomes[name] = exc.code
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=3)
        if outcomes != {"client": 204, "rogue": 403}:
            raise SystemExit("SPIFFE mTLS proof failed: " + json.dumps(outcomes, sort_keys=True))
        print(json.dumps({"result": "SUCCESS", "trusted_client_status": 204, "rogue_same_domain_status": 403}, sort_keys=True))

if __name__ == "__main__": main()

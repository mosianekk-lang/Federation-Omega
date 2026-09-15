from __future__ import annotations

from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
import uuid


def _z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def heavy_task(
    task_id: str = "f273-heavy-001",
    *,
    effect: str = "READ_ONLY",
    parameter_updates: dict[str, object] | None = None,
    issued_delta_seconds: int = -1,
    ttl_seconds: int = 300,
) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    parameters: dict[str, object] = {
        "bytes_per_round": 4096,
        "rounds": 2,
        "requested_workers": 2,
        "requested_memory_mb": 64,
        "max_seconds": 30,
        "seed_hex": "00" * 32,
    }
    if parameter_updates:
        parameters.update(parameter_updates)
    issued = now + timedelta(seconds=issued_delta_seconds)
    return {
        "schema": "FEDERATION-WINDOWS-TASK-V1",
        "task_id": task_id,
        "correlation_id": "corr-f273-hosted",
        "issued_by": "FUSE/FDOF",
        "task_type": "heavy_sha256",
        "issued_at": _z(issued),
        "expires_at": _z(issued + timedelta(seconds=ttl_seconds)),
        "parameters": parameters,
        "effect": effect,
    }


class _RelayState:
    def __init__(self, task: dict[str, object]):
        self.task = task
        self.device_id = "dev_f273_hosted"
        self.public_key = ""
        self.lease_device_id: str | None = None
        self.enrollments: list[dict[str, object]] = []
        self.poll_headers: list[dict[str, str]] = []
        self.completions: list[dict[str, object]] = []
        self.redirect_poll = False


class _RelayHarness:
    def __init__(self, task: dict[str, object]):
        self.state = _RelayState(task)
        state = self.state

        class Handler(BaseHTTPRequestHandler):
            server_version = "F273HostedRelay/1.0"
            sys_version = ""

            def log_message(self, *_args):
                return

            def _read_json(self) -> dict[str, object]:
                length = int(self.headers.get("content-length", "0") or "0")
                body = self.rfile.read(length) if length else b""
                return json.loads(body.decode("utf-8")) if body else {}

            def _send(self, status: int, payload: dict[str, object], *, headers: dict[str, str] | None = None):
                body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(body)))
                if headers:
                    for key, value in headers.items():
                        self.send_header(key, value)
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                if self.path == "/agent/enroll":
                    payload = self._read_json()
                    state.enrollments.append(payload)
                    state.public_key = str(payload.get("public_key_spki_b64") or "")
                    self._send(
                        201,
                        {
                            "schema": "FUSE-WINDOWS-DEVICE-CREDENTIAL-V2",
                            "device_id": state.device_id,
                            "public_key_spki_b64": state.public_key,
                            "enrolled_at": _z(datetime.now(timezone.utc)),
                        },
                    )
                    return

                if self.path == "/agent/poll":
                    _ = self._read_json()
                    state.poll_headers.append({key.lower(): value for key, value in self.headers.items()})
                    if state.redirect_poll:
                        self.send_response(302)
                        self.send_header("location", "http://127.0.0.1/forbidden")
                        self.send_header("content-length", "0")
                        self.end_headers()
                        return
                    self._send(
                        200,
                        {
                            "state": "LEASED",
                            "task": state.task,
                            "lease": {
                                "schema": "FUSE-WINDOWS-RELAY-LEASE-V1",
                                "task_id": state.task["task_id"],
                                "device_id": state.lease_device_id or state.device_id,
                                "lease_token": "lease-" + uuid.uuid4().hex,
                                "leased_at": _z(datetime.now(timezone.utc)),
                                "expires_at": _z(datetime.now(timezone.utc) + timedelta(minutes=2)),
                            },
                        },
                    )
                    return

                if self.path == "/agent/complete":
                    payload = self._read_json()
                    state.completions.append(payload)
                    self._send(200, {"state": "ACCEPTED", "task_id": payload.get("task_id", "")})
                    return

                self._send(404, {"state": "NOT_FOUND"})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


@unittest.skipUnless(os.name == "nt" and os.environ.get("FUSE_NATIVE_EXE"), "hosted Windows native executable required")
class NativeRelayClientHostedCourt(unittest.TestCase):
    def setUp(self):
        self.exe = str(Path(os.environ["FUSE_NATIVE_EXE"]).resolve())
        self.temp = tempfile.TemporaryDirectory(prefix="f273-native-relay-")
        self.root = Path(self.temp.name)
        self.state_dir = self.root / "state"
        self.workspace = self.root / "workspace"
        self.state_dir.mkdir()
        self.workspace.mkdir()
        self.key_name = "FUSE-F273-HOSTED-" + uuid.uuid4().hex

    def tearDown(self):
        self.temp.cleanup()

    def _enrollment_file(self, relay_url: str) -> Path:
        path = self.root / ("enrollment-" + uuid.uuid4().hex + ".json")
        path.write_text(
            json.dumps(
                {
                    "schema": "FUSE-WINDOWS-NATIVE-ENROLLMENT-BOOTSTRAP-V1",
                    "relay_url": relay_url,
                    "enrollment_id": "enr-f273-hosted",
                    "enrollment_token": "token-f273-hosted",
                    "device_label": "f273-hosted-windows",
                },
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        return path

    def _run(self, relay_url: str, *, enrollment: Path | None) -> subprocess.CompletedProcess[str]:
        command = [
            self.exe,
            "agent-once",
            "--relay-url",
            relay_url,
            "--state-dir",
            str(self.state_dir),
            "--workspace",
            str(self.workspace),
            "--key-name",
            self.key_name,
        ]
        if enrollment is not None:
            command.extend(["--enrollment-file", str(enrollment)])
        env = os.environ.copy()
        env["FUSE_TEST_ALLOW_LOOPBACK_HTTP"] = "1"
        return subprocess.run(command, text=True, capture_output=True, timeout=60, env=env)

    def test_heavy_sha256_round_trip_returns_attested_effect_free_receipt(self):
        with _RelayHarness(heavy_task()) as relay:
            result = self._run(relay.url, enrollment=self._enrollment_file(relay.url))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("COMPLETED", result.stdout)
        self.assertEqual(len(relay.state.enrollments), 1)
        self.assertEqual(len(relay.state.completions), 1)
        headers = relay.state.poll_headers[0]
        for header in ("x-fuse-device-id", "x-fuse-timestamp", "x-fuse-nonce", "x-fuse-signature"):
            self.assertTrue(headers.get(header), header)
        receipt = relay.state.completions[0]["receipt"]
        self.assertEqual(receipt["schema"], "FEDERATION-WINDOWS-RECEIPT-V1")
        self.assertEqual(receipt["task_type"], "heavy_sha256")
        self.assertEqual(receipt["effect"], "READ_ONLY")
        self.assertEqual(receipt["runner"]["os"], "Windows")
        self.assertEqual(receipt["runner"]["device_id"], relay.state.device_id)
        self.assertEqual(receipt["task"]["parameters"]["requested_workers"], 2)
        self.assertEqual(receipt["result"]["operation"], "heavy_sha256")
        self.assertEqual(receipt["result"]["total_bytes"], 8192)
        self.assertFalse(receipt["result"]["filesystem_usage"])
        self.assertFalse(receipt["result"]["shell_process_usage"])
        self.assertFalse(receipt["result"]["external_effect"])
        self.assertEqual(len(receipt["result"]["sha256"]), 64)
        attestation = receipt["device_attestation"]
        self.assertEqual(attestation["public_key_spki_b64"], relay.state.public_key)
        self.assertTrue(attestation["payload_b64"])
        self.assertEqual(len(attestation["payload_sha256"]), 64)
        self.assertTrue(attestation["signature_der_b64"])

    def test_unknown_heavy_parameter_fails_closed_without_completion(self):
        task = heavy_task(parameter_updates={"shell": "whoami"})
        with _RelayHarness(task) as relay:
            result = self._run(relay.url, enrollment=self._enrollment_file(relay.url))
        self.assertEqual(result.returncode, 2)
        self.assertIn("UNKNOWN_HEAVY_PARAMETERS", result.stderr)
        self.assertEqual(relay.state.completions, [])

    def test_write_effect_fails_closed_without_completion(self):
        with _RelayHarness(heavy_task(effect="WRITE")) as relay:
            result = self._run(relay.url, enrollment=self._enrollment_file(relay.url))
        self.assertEqual(result.returncode, 2)
        self.assertIn("TASK_EFFECT_NOT_AUTHORIZED", result.stderr)
        self.assertEqual(relay.state.completions, [])

    def test_lease_target_mismatch_fails_closed_without_completion(self):
        with _RelayHarness(heavy_task()) as relay:
            relay.state.lease_device_id = "dev_wrong_target"
            result = self._run(relay.url, enrollment=self._enrollment_file(relay.url))
        self.assertEqual(result.returncode, 2)
        self.assertIn("RELAY_LEASE_BINDING_MISMATCH", result.stderr)
        self.assertEqual(relay.state.completions, [])

    def test_redirect_is_forbidden(self):
        with _RelayHarness(heavy_task()) as relay:
            relay.state.redirect_poll = True
            result = self._run(relay.url, enrollment=self._enrollment_file(relay.url))
        self.assertEqual(result.returncode, 2)
        self.assertIn("RELAY_REDIRECT_FORBIDDEN", result.stderr)
        self.assertEqual(relay.state.completions, [])

    def test_same_task_id_changed_semantics_is_rejected_without_second_completion(self):
        first = heavy_task(task_id="f273-collision")
        with _RelayHarness(first) as relay:
            initial = self._run(relay.url, enrollment=self._enrollment_file(relay.url))
            self.assertEqual(initial.returncode, 0, initial.stderr)
            self.assertEqual(len(relay.state.completions), 1)
            relay.state.task = heavy_task(task_id="f273-collision", parameter_updates={"seed_hex": "11" * 32})
            second = self._run(relay.url, enrollment=None)
        self.assertEqual(second.returncode, 2)
        self.assertIn("RELAY_TASK_ID_COLLISION", second.stderr)
        self.assertEqual(len(relay.state.completions), 1)


if __name__ == "__main__":
    unittest.main()

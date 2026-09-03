from __future__ import annotations

"""No-effect browser runtime canary for the Bubbles execution surface.

The canary proves only that the current host can launch a real headless browser,
navigate to a loopback-only fixture, execute JavaScript, and read back the
rendered DOM. It does not prove arbitrary desktop/computer-use automation,
external website authority, account login, or provider mutation.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
from typing import Sequence


SCHEMA = "BUBBLES-BROWSER-RUNTIME-CANARY-1"
EXPECTED_MARKER = "BUBBLES_BROWSER_CANARY_OK"
EXPECTED_STATE = 'data-state="executed"'


@dataclass(frozen=True, slots=True)
class BrowserCanaryReceipt:
    schema: str
    state: str
    browser_binary: str | None
    browser_exit_code: int | None
    browser_runtime_verified: bool
    javascript_execution_verified: bool
    dom_readback_verified: bool
    loopback_only: bool
    external_network_target_requested: bool
    provider_mutation_attempted: bool
    secret_values_recorded: bool
    dom_sha256: str | None
    stderr_sha256: str | None
    truth_boundary: str
    receipt_sha256: str | None = None

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["receipt_sha256"] = None
        unsigned = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        payload["receipt_sha256"] = sha256(unsigned.encode("utf-8")).hexdigest()
        return payload


def _candidate_browsers() -> Sequence[str]:
    return (
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
    )


def find_browser() -> str | None:
    for candidate in _candidate_browsers():
        path = shutil.which(candidate)
        if path:
            return path
    return None


def verify_dom(dom: str) -> tuple[bool, bool]:
    return EXPECTED_MARKER in dom, EXPECTED_STATE in dom


def _fixture_html() -> str:
    return """<!doctype html>
<html>
<head><meta charset=\"utf-8\"><title>Bubbles Browser Canary</title></head>
<body data-state=\"boot\">
<div id=\"result\">PENDING</div>
<script>
  document.body.setAttribute('data-state', 'executed');
  document.getElementById('result').textContent = 'BUBBLES_BROWSER_CANARY_OK';
</script>
</body>
</html>
"""


def run_canary() -> dict:
    browser = find_browser()
    if browser is None:
        receipt = BrowserCanaryReceipt(
            schema=SCHEMA,
            state="BROWSER_BINARY_NOT_FOUND",
            browser_binary=None,
            browser_exit_code=None,
            browser_runtime_verified=False,
            javascript_execution_verified=False,
            dom_readback_verified=False,
            loopback_only=True,
            external_network_target_requested=False,
            provider_mutation_attempted=False,
            secret_values_recorded=False,
            dom_sha256=None,
            stderr_sha256=None,
            truth_boundary=(
                "No browser binary was found on this host. Source presence does not prove browser runtime capability."
            ),
        )
        return receipt.to_dict()

    with tempfile.TemporaryDirectory(prefix="bubbles-browser-canary-") as temp_dir:
        root = Path(temp_dir)
        (root / "index.html").write_text(_fixture_html(), encoding="utf-8")

        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, _format: str, *_args) -> None:
                return

        handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(root), **kwargs)
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/index.html"
            command = [
                browser,
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-background-networking",
                "--disable-component-update",
                "--disable-default-apps",
                "--disable-sync",
                "--metrics-recording-only",
                "--no-first-run",
                "--no-default-browser-check",
                "--dump-dom",
                url,
            ]
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    dom = result.stdout or ""
    stderr = result.stderr or ""
    marker_ok, state_ok = verify_dom(dom)
    runtime_ok = result.returncode == 0 and bool(dom)
    verified = runtime_ok and marker_ok and state_ok
    receipt = BrowserCanaryReceipt(
        schema=SCHEMA,
        state="HOSTED_BROWSER_RUNTIME_VERIFIED" if verified else "BROWSER_RUNTIME_CANARY_FAILED",
        browser_binary=Path(browser).name,
        browser_exit_code=result.returncode,
        browser_runtime_verified=runtime_ok,
        javascript_execution_verified=marker_ok and state_ok,
        dom_readback_verified=marker_ok,
        loopback_only=True,
        external_network_target_requested=False,
        provider_mutation_attempted=False,
        secret_values_recorded=False,
        dom_sha256=sha256(dom.encode("utf-8")).hexdigest() if dom else None,
        stderr_sha256=sha256(stderr.encode("utf-8")).hexdigest() if stderr else None,
        truth_boundary=(
            "A successful receipt proves bounded browser launch, loopback navigation, JavaScript execution and DOM readback "
            "on this host only. It does not prove arbitrary computer-use automation, external-site authority, login, "
            "or provider mutation."
        ),
    )
    return receipt.to_dict()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Bubbles no-effect browser runtime canary")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    receipt = run_canary()
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "state": receipt["state"],
        "browser_runtime_verified": receipt["browser_runtime_verified"],
        "javascript_execution_verified": receipt["javascript_execution_verified"],
        "dom_readback_verified": receipt["dom_readback_verified"],
        "receipt_sha256": receipt["receipt_sha256"],
    }, sort_keys=True))
    return 0 if receipt["state"] == "HOSTED_BROWSER_RUNTIME_VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())

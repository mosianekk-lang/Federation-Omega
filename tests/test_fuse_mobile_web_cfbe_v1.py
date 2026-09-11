from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile" / "fuse-mobile"


def read(relative: str) -> str:
    return (MOBILE / relative).read_text(encoding="utf-8")


def test_web_export_and_static_host_contract() -> None:
    package = json.loads(read("package.json"))
    app = json.loads(read("app.json"))
    assert package["version"] == "0.3.0"
    assert package["scripts"]["export:web"] == "expo export --platform web"
    assert package["scripts"]["verify:web"] == "expo export --platform web --output-dir dist-web"
    assert app["expo"]["web"] == {"bundler": "metro", "output": "static"}
    assert app["expo"]["orientation"] == "default"


def test_platform_specific_owner_identity_and_session_are_present() -> None:
    web_iap = read("src/iap.web.ts")
    web_session = read("src/session.web.ts")
    native_iap = read("src/iap.ts")
    native_session = read("src/session.ts")
    assert "accounts.google.com/gsi/client" in web_iap
    assert "sessionStorage" in web_iap
    assert "sessionStorage" in web_session
    assert "localStorage" not in web_session
    assert "@react-native-google-signin/google-signin" in native_iap
    assert "expo-secure-store" in native_session


def test_pwa_shell_never_caches_authorized_api_traffic() -> None:
    html = read("app/+html.tsx")
    manifest = json.loads(read("public/manifest.webmanifest"))
    sw = read("public/sw.js").lower()
    assert "serviceworker.register('/sw.js')" in html.lower()
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/"
    assert "authorization" in sw
    assert "x-fuse-authorization" in sw
    assert "request.method !== 'get'" in sw
    assert "url.origin !== self.location.origin" in sw


def test_abort_signal_reaches_gateway_transport() -> None:
    federation = read("src/federation.ts")
    owner = read("src/ownerConnection.ts")
    home = read("app/index.tsx")
    assert "externalSignal?: AbortSignal" in federation
    assert "sendFuseMessage" in federation and "signal?: AbortSignal" in federation
    assert "sendOwnerFuseMessage" in owner and "signal?: AbortSignal" in owner
    assert "AbortController" in home
    assert "handleStop" in home


def test_cfbe_capability_passport_is_exact_and_complete() -> None:
    passport = read("src/cfbeCapabilityPassport.ts")
    ids = re.findall(r"id: 'FM-CFBE-(\d{3})'", passport)
    assert len(ids) == 100
    assert len(set(ids)) == 100
    assert ids == [f"{number:03d}" for number in range(1, 101)]
    assert "WORK_PACKAGE_CREATED" in passport


def test_proof_visible_ui_contract() -> None:
    home = read("app/index.tsx")
    required = [
        "LIVE DIAGNOSTICS",
        "PROVIDER READBACK",
        "ACTION TIMELINE",
        "Authority preview",
        "source_refs",
        "trace_id",
        "Proof-before-claim",
        "CFBE {passport.total}",
    ]
    for marker in required:
        assert marker in home
    assert "EXECUTE" in home
    assert "PRIVATE" in home


def test_no_web_identity_or_session_secret_is_hardcoded() -> None:
    joined = "\n".join([read("src/iap.web.ts"), read("src/session.web.ts")])
    lowered = joined.lower()
    assert "client_secret" not in lowered
    assert "private_key" not in lowered
    assert "refresh_token" not in lowered
    assert "sk-" not in lowered

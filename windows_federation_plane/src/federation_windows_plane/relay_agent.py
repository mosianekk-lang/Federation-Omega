from __future__ import annotations

import argparse
import base64
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import uuid

import requests

from .executor import WindowsPlane
from .models import TaskEnvelope
from .relay_protocol import signing_payload


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _blob(data: bytes):
    buffer = ctypes.create_string_buffer(data)
    return DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))), buffer


def _dpapi(data: bytes, *, protect: bool) -> bytes:
    if os.name != "nt":
        raise RuntimeError("WINDOWS_DPAPI_REQUIRED")
    source, source_buffer = _blob(data); target = DATA_BLOB(); crypt32 = ctypes.windll.crypt32; kernel32 = ctypes.windll.kernel32
    crypt32.CryptProtectData.argtypes = [ctypes.POINTER(DATA_BLOB), wintypes.LPCWSTR, ctypes.POINTER(DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DATA_BLOB)]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    crypt32.CryptUnprotectData.argtypes = [ctypes.POINTER(DATA_BLOB), ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DATA_BLOB)]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]; kernel32.LocalFree.restype = ctypes.c_void_p
    if protect:
        ok = crypt32.CryptProtectData(ctypes.byref(source), "FUSE Windows Relay", None, None, None, 1, ctypes.byref(target))
    else:
        description = wintypes.LPWSTR(); ok = crypt32.CryptUnprotectData(ctypes.byref(source), ctypes.byref(description), None, None, None, 1, ctypes.byref(target))
        if description: kernel32.LocalFree(description)
    _ = source_buffer
    if not ok: raise ctypes.WinError()
    try: return ctypes.string_at(target.pbData, target.cbData)
    finally: kernel32.LocalFree(target.pbData)


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64u(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _new_software_key() -> tuple[str, str]:
    """Lower-assurance portable fallback. P2 trusted-owner promotion still prefers CNG/TPM."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    key = ec.generate_private_key(ec.SECP256R1())
    private_der = key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    public_der = key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return _b64u(private_der), _b64u(public_der)


def _save_credential(path: Path, value: dict[str, str]) -> None:
    protected = _dpapi(json.dumps(value, sort_keys=True).encode(), protect=True)
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(base64.b64encode(protected).decode("ascii"), encoding="ascii")


def _load_credential(path: Path) -> dict[str, str]:
    protected = base64.b64decode(path.read_text(encoding="ascii")); value = json.loads(_dpapi(protected, protect=False))
    if "private_key_pkcs8_b64" not in value:
        raise RuntimeError("LEGACY_HMAC_CREDENTIAL_REENROLL_REQUIRED")
    return {"device_id": str(value["device_id"]), "private_key_pkcs8_b64": str(value["private_key_pkcs8_b64"]), "public_key_spki_b64": str(value["public_key_spki_b64"]), "assurance": str(value.get("assurance") or "SOFTWARE_DPAPI")}


def _signed_headers(credential: dict[str, str], *, method: str, path: str, body: bytes) -> dict[str, str]:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"); nonce = "nonce-" + uuid.uuid4().hex
    payload = signing_payload(method=method, path=path, timestamp=timestamp, nonce=nonce, body=body)
    key = serialization.load_der_private_key(_unb64u(credential["private_key_pkcs8_b64"]), password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey): raise RuntimeError("DEVICE_PRIVATE_KEY_INVALID")
    signature = _b64u(key.sign(payload, ec.ECDSA(hashes.SHA256())))
    return {"x-fuse-device-id": credential["device_id"], "x-fuse-timestamp": timestamp, "x-fuse-nonce": nonce, "x-fuse-signature": signature, "content-type": "application/json"}


def enroll(client: requests.Session, *, base_url: str, enrollment_id: str, enrollment_token: str, device_label: str, credential_path: Path) -> dict[str, str]:
    private_b64, public_b64 = _new_software_key()
    response = client.post(base_url + "/agent/enroll", json={"enrollment_id": enrollment_id, "enrollment_token": enrollment_token, "device_label": device_label, "public_key_spki_b64": public_b64}, timeout=30)
    response.raise_for_status(); data = response.json()
    credential = {"device_id": str(data["device_id"]), "private_key_pkcs8_b64": private_b64, "public_key_spki_b64": public_b64, "assurance": "SOFTWARE_DPAPI_LOWER_ASSURANCE"}
    _save_credential(credential_path, credential); return credential


def run_once(client: requests.Session, *, base_url: str, workspace: Path, credential: dict[str, str]) -> str:
    poll_path = "/agent/poll"; poll_body = b""
    response = client.post(base_url + poll_path, data=poll_body, headers=_signed_headers(credential, method="POST", path=poll_path, body=poll_body), timeout=30)
    response.raise_for_status(); item = response.json()
    if item.get("state") == "EMPTY": return "EMPTY"
    task = TaskEnvelope.from_mapping(item["task"]); receipt = WindowsPlane(workspace).execute(task).to_dict()
    payload = json.dumps({"task_id": task.task_id, "lease_token": item["lease"]["lease_token"], "receipt": receipt}, sort_keys=True, separators=(",", ":")).encode(); complete_path = "/agent/complete"
    completed = client.post(base_url + complete_path, data=payload, headers=_signed_headers(credential, method="POST", path=complete_path, body=payload), timeout=30)
    completed.raise_for_status(); return "COMPLETED"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="federation-windows-agent"); parser.add_argument("--relay-url", default=os.environ.get("FUSE_RELAY_URL")); parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--credential-file", type=Path, default=Path(os.environ.get("LOCALAPPDATA", ".")) / "FUSE" / "relay-credential.dpapi")
    parser.add_argument("--enrollment-id", default=os.environ.get("FUSE_ENROLLMENT_ID")); parser.add_argument("--enrollment-token", default=os.environ.get("FUSE_ENROLLMENT_TOKEN")); parser.add_argument("--device-label", default=os.environ.get("COMPUTERNAME", "owner-windows")); parser.add_argument("--once", action="store_true"); parser.add_argument("--poll-seconds", type=float, default=5.0); args = parser.parse_args(argv)
    if not args.relay_url: parser.error("--relay-url or FUSE_RELAY_URL is required")
    base_url = args.relay_url.rstrip("/")
    with requests.Session() as client:
        if args.credential_file.exists(): credential = _load_credential(args.credential_file)
        else:
            if not args.enrollment_id or not args.enrollment_token: parser.error("one-time enrollment credentials are required for first run")
            credential = enroll(client, base_url=base_url, enrollment_id=args.enrollment_id, enrollment_token=args.enrollment_token, device_label=args.device_label, credential_path=args.credential_file)
        while True:
            run_once(client, base_url=base_url, workspace=args.workspace, credential=credential)
            if args.once: return 0
            time.sleep(max(1.0, args.poll_seconds))


if __name__ == "__main__": raise SystemExit(main())

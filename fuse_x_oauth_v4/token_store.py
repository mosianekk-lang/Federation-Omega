from __future__ import annotations
import json, os, sys
from pathlib import Path

class TokenStoreError(RuntimeError):
    pass

def _require_windows():
    if os.name != "nt":
        raise TokenStoreError("DPAPI token custody requires Windows current-user context")

def protect_current_user(data: bytes) -> bytes:
    _require_windows()
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]
    CryptProtectData = ctypes.windll.crypt32.CryptProtectData
    LocalFree = ctypes.windll.kernel32.LocalFree

    buf = ctypes.create_string_buffer(data)
    in_blob = DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))
    out_blob = DATA_BLOB()
    if not CryptProtectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
        raise TokenStoreError("CryptProtectData failed")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        LocalFree(out_blob.pbData)

def unprotect_current_user(data: bytes) -> bytes:
    _require_windows()
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]
    CryptUnprotectData = ctypes.windll.crypt32.CryptUnprotectData
    LocalFree = ctypes.windll.kernel32.LocalFree

    buf = ctypes.create_string_buffer(data)
    in_blob = DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))
    out_blob = DATA_BLOB()
    if not CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
        raise TokenStoreError("CryptUnprotectData failed")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        LocalFree(out_blob.pbData)

class DPAPITokenStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def save(self, token_doc: dict) -> None:
        raw = json.dumps(token_doc, sort_keys=True, separators=(",", ":")).encode("utf-8")
        enc = protect_current_user(raw)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_bytes(enc)
        os.replace(tmp, self.path)

    def load(self) -> dict:
        if not self.path.exists():
            raise TokenStoreError("token store missing")
        return json.loads(unprotect_current_user(self.path.read_bytes()).decode("utf-8"))

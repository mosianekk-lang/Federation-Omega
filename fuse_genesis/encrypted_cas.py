from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass, asdict
import sqlite3, hashlib, json, os, tempfile
from typing import Protocol
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def sha256_bytes(b:bytes)->str: return hashlib.sha256(b).hexdigest()
def canon(x): return json.dumps(x,sort_keys=True,separators=(",",":"))

class KeyProvider(Protocol):
    def get_key(self,key_ref:str)->bytes: ...

class InMemoryKeyProvider:
    def __init__(self,keys:dict[str,bytes]): self.keys=dict(keys)
    def get_key(self,key_ref):
        if key_ref not in self.keys: raise KeyError(key_ref)
        k=self.keys[key_ref]
        if len(k)!=32: raise ValueError("AES256 key must be 32 bytes")
        return k

@dataclass(frozen=True)
class ObjectReceipt:
    object_id:str
    plaintext_sha256:str
    ciphertext_sha256:str
    size:int
    media_type:str
    privacy_class:str
    logical_role:str
    key_ref:str

class EncryptedCAS:
    def __init__(self,root,key_provider:KeyProvider):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
        self.blobs=self.root/"blobs"; self.blobs.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.root/"objects.db")
        self.db.row_factory=sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS objects(
          object_id TEXT PRIMARY KEY,
          plaintext_sha256 TEXT UNIQUE NOT NULL,
          ciphertext_sha256 TEXT NOT NULL,
          size INTEGER NOT NULL,
          media_type TEXT NOT NULL,
          privacy_class TEXT NOT NULL,
          logical_role TEXT NOT NULL,
          key_ref TEXT NOT NULL,
          nonce_hex TEXT NOT NULL,
          source_ref TEXT,
          mission_id TEXT,
          created_at TEXT NOT NULL
        )""")
        self.db.commit(); self.keys=key_provider

    def close(self): self.db.close()

    def _path(self,ph):
        return self.blobs/ph[:2]/ph[2:4]/ph

    def _aad(self, ph, media_type, privacy_class, logical_role):
        return canon({"plaintext_sha256":ph,"media_type":media_type,"privacy_class":privacy_class,"logical_role":logical_role}).encode()

    def put(self,data:bytes,*,media_type,privacy_class,logical_role,key_ref,source_ref="",mission_id="",created_at=""):
        ph=sha256_bytes(data); oid=f"sha256:{ph}"
        row=self.db.execute("SELECT * FROM objects WHERE plaintext_sha256=?",(ph,)).fetchone()
        if row:
            if row["key_ref"]!=key_ref: raise ValueError("existing object bound to different key_ref")
            return ObjectReceipt(oid,ph,row["ciphertext_sha256"],row["size"],row["media_type"],row["privacy_class"],row["logical_role"],row["key_ref"])
        key=self.keys.get_key(key_ref)
        nonce=os.urandom(12)
        aad=self._aad(ph,media_type,privacy_class,logical_role)
        ct=AESGCM(key).encrypt(nonce,data,aad)
        ch=sha256_bytes(ct)
        p=self._path(ph); p.parent.mkdir(parents=True,exist_ok=True)
        fd,tmp=tempfile.mkstemp(dir=str(p.parent),prefix=".tmp-")
        try:
            with os.fdopen(fd,"wb") as f:
                f.write(ct); f.flush(); os.fsync(f.fileno())
            os.replace(tmp,p)
        finally:
            if os.path.exists(tmp): os.remove(tmp)
        self.db.execute("""INSERT INTO objects VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (oid,ph,ch,len(data),media_type,privacy_class,logical_role,key_ref,nonce.hex(),source_ref,mission_id,created_at))
        self.db.commit()
        return ObjectReceipt(oid,ph,ch,len(data),media_type,privacy_class,logical_role,key_ref)

    def _row(self,oid):
        r=self.db.execute("SELECT * FROM objects WHERE object_id=?",(oid,)).fetchone()
        if not r: raise KeyError(oid)
        return r

    def get(self,oid):
        r=self._row(oid); ct=self._path(r["plaintext_sha256"]).read_bytes()
        if sha256_bytes(ct)!=r["ciphertext_sha256"]: raise IOError("ciphertext corruption")
        key=self.keys.get_key(r["key_ref"])
        aad=self._aad(r["plaintext_sha256"],r["media_type"],r["privacy_class"],r["logical_role"])
        pt=AESGCM(key).decrypt(bytes.fromhex(r["nonce_hex"]),ct,aad)
        if sha256_bytes(pt)!=r["plaintext_sha256"] or len(pt)!=r["size"]: raise IOError("plaintext integrity mismatch")
        return pt

    def verify(self,oid):
        try: self.get(oid); return True
        except Exception: return False

    def manifest(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM objects ORDER BY object_id")]

    def manifest_digest(self):
        m=self.manifest()
        return hashlib.sha256(canon(m).encode()).hexdigest()

    def replicate_to(self,oid,replica_root):
        r=self._row(oid)
        src=self._path(r["plaintext_sha256"])
        dst=Path(replica_root)/"blobs"/r["plaintext_sha256"][:2]/r["plaintext_sha256"][2:4]/r["plaintext_sha256"]
        dst.parent.mkdir(parents=True,exist_ok=True)
        data=src.read_bytes()
        fd,tmp=tempfile.mkstemp(dir=str(dst.parent),prefix=".tmp-")
        try:
            with os.fdopen(fd,"wb") as f:
                f.write(data); f.flush(); os.fsync(f.fileno())
            os.replace(tmp,dst)
        finally:
            if os.path.exists(tmp): os.remove(tmp)
        if sha256_bytes(dst.read_bytes())!=r["ciphertext_sha256"]: raise IOError("replica mismatch")
        return {"object_id":oid,"replica_path":str(dst),"ciphertext_sha256":r["ciphertext_sha256"]}

    def export_metadata(self,path):
        payload={"schema":"FUSE-ENCRYPTED-CAS-METADATA-V2","objects":self.manifest(),"manifest_digest":self.manifest_digest()}
        Path(path).write_text(json.dumps(payload,indent=2),encoding="utf-8")
        return payload

    @classmethod
    def restore_from_metadata_and_replica(cls,root,key_provider,metadata_path,replica_root):
        meta=json.loads(Path(metadata_path).read_text(encoding="utf-8"))
        s=cls(root,key_provider)
        for row in meta["objects"]:
            p=s._path(row["plaintext_sha256"]); p.parent.mkdir(parents=True,exist_ok=True)
            rp=Path(replica_root)/"blobs"/row["plaintext_sha256"][:2]/row["plaintext_sha256"][2:4]/row["plaintext_sha256"]
            if not rp.exists(): raise FileNotFoundError(rp)
            data=rp.read_bytes()
            if sha256_bytes(data)!=row["ciphertext_sha256"]: raise IOError("replica corruption")
            p.write_bytes(data)
            s.db.execute("""INSERT OR REPLACE INTO objects VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                         tuple(row[k] for k in ("object_id","plaintext_sha256","ciphertext_sha256","size","media_type","privacy_class",
                                                "logical_role","key_ref","nonce_hex","source_ref","mission_id","created_at")))
        s.db.commit()
        if s.manifest_digest()!=meta["manifest_digest"]: raise IOError("metadata restore digest mismatch")
        return s

from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import base64, json, hashlib, sqlite3, os, tempfile
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey,Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding,PrivateFormat,PublicFormat,NoEncryption
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def b64u(b:bytes)->str: return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
def ub64u(s:str)->bytes: return base64.urlsafe_b64decode(s + "="*((4-len(s)%4)%4))
def canon(x): return json.dumps(x,sort_keys=True,separators=(",",":"))

@dataclass(frozen=True)
class PublicKeyRecord:
    key_id:str
    subject_id:str
    public_key_b64:str
    state:str
    created_at:int

class SigningKeyStore:
    def __init__(self):
        self.private={}
        self.public={}
        self.active_by_subject={}
    def create(self,subject_id,key_id,now):
        if key_id in self.private: raise ValueError("duplicate key")
        sk=Ed25519PrivateKey.generate()
        self.private[key_id]=sk
        pk=sk.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
        self.public[key_id]=PublicKeyRecord(key_id,subject_id,b64u(pk),"ACTIVE",now)
        self.active_by_subject[subject_id]=key_id
        return self.public[key_id]
    def rotate(self,subject_id,new_key_id,now):
        old=self.active_by_subject.get(subject_id)
        if old:
            r=self.public[old]; self.public[old]=PublicKeyRecord(r.key_id,r.subject_id,r.public_key_b64,"RETIRED",r.created_at)
        return self.create(subject_id,new_key_id,now)
    def revoke(self,key_id):
        r=self.public[key_id]; self.public[key_id]=PublicKeyRecord(r.key_id,r.subject_id,r.public_key_b64,"REVOKED",r.created_at)
        if self.active_by_subject.get(r.subject_id)==key_id: self.active_by_subject.pop(r.subject_id,None)
    def sign(self,subject_id,message:bytes):
        kid=self.active_by_subject.get(subject_id)
        if not kid: raise PermissionError("no active signing key")
        return kid,self.private[kid].sign(message)
    def verify(self,key_id,message,signature,allow_retired=True):
        r=self.public.get(key_id)
        if not r or r.state=="REVOKED" or (r.state=="RETIRED" and not allow_retired): return False
        pk=Ed25519PublicKey.from_public_bytes(ub64u(r.public_key_b64))
        try: pk.verify(signature,message); return True
        except Exception: return False
    def public_manifest(self):
        return [asdict(self.public[k]) for k in sorted(self.public)]

class SignedTokenIssuer:
    def __init__(self,keys:SigningKeyStore,revoked_jtis:set[str]|None=None):
        self.keys=keys; self.revoked_jtis=revoked_jtis if revoked_jtis is not None else set()
    def issue(self,subject_id,audience,now,ttl=300,claims=None,jti=""):
        if ttl<=0 or ttl>3600: raise ValueError("ttl")
        jti=jti or hashlib.sha256(f"{subject_id}:{audience}:{now}".encode()).hexdigest()[:24]
        body={"sub":subject_id,"aud":audience,"iat":now,"exp":now+ttl,"jti":jti,"claims":claims or {}}
        msg=canon(body).encode()
        kid,sig=self.keys.sign(subject_id,msg)
        return {"header":{"alg":"EdDSA","kid":kid},"body":body,"sig":b64u(sig)}
    def revoke(self,jti): self.revoked_jtis.add(jti)
    def verify(self,token,audience,now):
        b=token["body"]
        if b["jti"] in self.revoked_jtis or b["aud"]!=audience or not (b["iat"]<=now<b["exp"]): return False
        return self.keys.verify(token["header"]["kid"],canon(b).encode(),ub64u(token["sig"]))

class MasterKeyProvider:
    def __init__(self,keys:dict[str,bytes]): self.keys=dict(keys)
    def get(self,key_ref):
        k=self.keys[key_ref]
        if len(k)!=32: raise ValueError("master key must be 32 bytes")
        return k

class SecretVault:
    def __init__(self,path,key_provider:MasterKeyProvider):
        self.path=Path(path); self.path.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.path/"vault.db"); self.db.row_factory=sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL"); self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS secrets(
          secret_id TEXT NOT NULL,version INTEGER NOT NULL,state TEXT NOT NULL,key_ref TEXT NOT NULL,
          nonce_hex TEXT NOT NULL,ciphertext_b64 TEXT NOT NULL,ciphertext_sha256 TEXT NOT NULL,
          created_at INTEGER NOT NULL, PRIMARY KEY(secret_id,version))""")
        self.db.commit(); self.keys=key_provider
    def close(self): self.db.close()
    def put(self,secret_id,plaintext:bytes,key_ref,now):
        r=self.db.execute("SELECT MAX(version) v FROM secrets WHERE secret_id=?",(secret_id,)).fetchone()
        v=(r["v"] or 0)+1
        key=self.keys.get(key_ref); nonce=os.urandom(12)
        aad=canon({"secret_id":secret_id,"version":v,"key_ref":key_ref}).encode()
        ct=AESGCM(key).encrypt(nonce,plaintext,aad)
        ch=hashlib.sha256(ct).hexdigest()
        self.db.execute("INSERT INTO secrets VALUES(?,?,?,?,?,?,?,?)",
                        (secret_id,v,"ACTIVE",key_ref,nonce.hex(),b64u(ct),ch,now)); self.db.commit()
        return {"secret_id":secret_id,"version":v,"key_ref":key_ref,"ciphertext_sha256":ch}
    def get(self,secret_id,version=None):
        if version is None:
            r=self.db.execute("SELECT * FROM secrets WHERE secret_id=? AND state='ACTIVE' ORDER BY version DESC LIMIT 1",(secret_id,)).fetchone()
        else:
            r=self.db.execute("SELECT * FROM secrets WHERE secret_id=? AND version=?",(secret_id,version)).fetchone()
        if not r or r["state"]=="REVOKED": raise KeyError(secret_id)
        ct=ub64u(r["ciphertext_b64"])
        if hashlib.sha256(ct).hexdigest()!=r["ciphertext_sha256"]: raise IOError("ciphertext corruption")
        aad=canon({"secret_id":r["secret_id"],"version":r["version"],"key_ref":r["key_ref"]}).encode()
        return AESGCM(self.keys.get(r["key_ref"])).decrypt(bytes.fromhex(r["nonce_hex"]),ct,aad)
    def revoke(self,secret_id,version):
        self.db.execute("UPDATE secrets SET state='REVOKED' WHERE secret_id=? AND version=?",(secret_id,version)); self.db.commit()
    def rotate(self,secret_id,new_plaintext,key_ref,now):
        self.db.execute("UPDATE secrets SET state='RETIRED' WHERE secret_id=? AND state='ACTIVE'",(secret_id,)); self.db.commit()
        return self.put(secret_id,new_plaintext,key_ref,now)
    def manifest(self):
        return [{k:r[k] for k in ("secret_id","version","state","key_ref","ciphertext_sha256","created_at")}
                for r in self.db.execute("SELECT * FROM secrets ORDER BY secret_id,version")]
    def export_manifest(self,path):
        m={"schema":"FUSE-SECRET-VAULT-MANIFEST-V2","secrets":self.manifest()}
        m["digest"]=hashlib.sha256(canon(m["secrets"]).encode()).hexdigest()
        Path(path).write_text(json.dumps(m,indent=2),encoding="utf-8"); return m

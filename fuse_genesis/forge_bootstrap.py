from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable
import csv, json, hashlib, subprocess, re, os, tempfile, shutil

HEX40=re.compile(r"^[0-9a-f]{40}$")

def run(args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True, stderr=subprocess.STDOUT).strip()

@dataclass(frozen=True)
class TreeEntry:
    path:str
    mode:str
    type:str
    object_sha:str
    size:int|None
    source_tree_sha:str

class TreeManifest:
    def __init__(self, entries:list[TreeEntry]):
        self.entries=entries

    @classmethod
    def from_csv(cls,path):
        rows=[]
        with open(path,newline="",encoding="utf-8") as f:
            r=csv.DictReader(f)
            required={"Path","Mode","Type","Git_Object_SHA","Size_Bytes","Source_Tree_SHA"}
            if set(r.fieldnames or [])!=required:
                raise ValueError(f"manifest columns mismatch: {r.fieldnames}")
            for x in r:
                rows.append(TreeEntry(
                    x["Path"],x["Mode"],x["Type"],x["Git_Object_SHA"],
                    int(x["Size_Bytes"]) if x["Size_Bytes"] else None,x["Source_Tree_SHA"]))
        return cls(rows)

    def validate(self, *, expected_tree=None, expected_total=None, expected_blobs=None, expected_trees=None):
        if not self.entries: raise ValueError("empty manifest")
        paths=set()
        for e in self.entries:
            if not e.path or e.path.startswith("/") or ".." in Path(e.path).parts:
                raise ValueError("unsafe path")
            if e.path in paths: raise ValueError("duplicate path")
            paths.add(e.path)
            if e.type not in {"blob","tree","commit"}: raise ValueError("invalid type")
            if e.mode not in {"040000","100644","100755","120000","160000"}: raise ValueError("invalid mode")
            if not HEX40.fullmatch(e.object_sha): raise ValueError("invalid object sha")
            if not HEX40.fullmatch(e.source_tree_sha): raise ValueError("invalid source tree sha")
            if e.type=="blob" and e.size is None: raise ValueError("blob size missing")
            if e.type=="tree" and e.size is not None: raise ValueError("tree size should be empty")
        trees={e.source_tree_sha for e in self.entries}
        if len(trees)!=1: raise ValueError("mixed source trees")
        tree=next(iter(trees))
        if expected_tree and tree!=expected_tree: raise ValueError("root tree mismatch")
        stats=self.stats()
        for label,want,got in [
            ("total",expected_total,stats["total"]),
            ("blobs",expected_blobs,stats["blobs"]),
            ("trees",expected_trees,stats["trees"]),
        ]:
            if want is not None and want!=got: raise ValueError(f"{label} mismatch {got}!={want}")
        return {"tree":tree,**stats}

    def stats(self):
        return {
            "total":len(self.entries),
            "blobs":sum(e.type=="blob" for e in self.entries),
            "trees":sum(e.type=="tree" for e in self.entries),
            "commits":sum(e.type=="commit" for e in self.entries),
            "blob_bytes":sum(e.size or 0 for e in self.entries if e.type=="blob")
        }

    def digest(self):
        material=[asdict(e) for e in sorted(self.entries,key=lambda e:e.path)]
        return hashlib.sha256(json.dumps(material,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def git_commit_tree(repo,commit):
    return run(["git","rev-parse",f"{commit}^{{tree}}"],cwd=repo)

def git_object_exists(repo,sha):
    p=subprocess.run(["git","cat-file","-e",f"{sha}^{{object}}"],cwd=repo)
    return p.returncode==0

def git_show_refs(repo):
    out=run(["git","show-ref"],cwd=repo)
    refs={}
    if not out: return refs
    for line in out.splitlines():
        sha,ref=line.split(" ",1); refs[ref]=sha
    return refs

def compare_refs(a:dict,b:dict):
    keys=sorted(set(a)|set(b))
    return [{"ref":k,"left":a.get(k),"right":b.get(k),"match":a.get(k)==b.get(k)} for k in keys]

def clone_local_mirror(source,dest):
    src=Path(source).resolve()
    if not src.exists(): raise FileNotFoundError(src)
    subprocess.check_call(["git","clone","--mirror",str(src),str(dest)],
                          stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return Path(dest)

def make_bundle(source,bundle_path,refs="--all"):
    src=Path(source).resolve()
    subprocess.check_call(["git","bundle","create",str(bundle_path),refs],
                          cwd=src,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return Path(bundle_path)

def verify_bundle(bundle_path):
    tmp=Path(tempfile.mkdtemp(prefix="fuse-bundle-verify-"))
    try:
        subprocess.check_call(["git","init","--bare","-q",str(tmp)])
        out=subprocess.check_output(["git","bundle","verify",str(Path(bundle_path).resolve())],
                                    cwd=tmp,text=True,stderr=subprocess.STDOUT)
        low=out.lower()
        return ("is okay" in low) or ("complete history" in low) or ("complete history" in low.replace("the bundle records a ",""))
    finally:
        shutil.rmtree(tmp,ignore_errors=True)

def clone_bundle_mirror(bundle_path,dest):
    subprocess.check_call(["git","clone","--mirror",str(bundle_path),str(dest)],
                          stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return Path(dest)

def ls_tree_entries(repo,commit):
    out=run(["git","ls-tree","-r","-t","-l",commit],cwd=repo)
    rows=[]
    for line in out.splitlines():
        left,path=line.split("\t",1)
        parts=left.split()
        mode,typ,sha=parts[:3]
        size=None if len(parts)<4 or parts[3]=="-" else int(parts[3])
        rows.append((path,mode,typ,sha,size))
    return rows

def compare_manifest_to_repo(manifest:TreeManifest,repo,commit):
    expected={e.path:(e.mode,e.type,e.object_sha,e.size) for e in manifest.entries}
    actual={path:(mode,typ,sha,size) for path,mode,typ,sha,size in ls_tree_entries(repo,commit)}
    keys=sorted(set(expected)|set(actual))
    mismatches=[{"path":k,"expected":expected.get(k),"actual":actual.get(k)} for k in keys if expected.get(k)!=actual.get(k)]
    return {"match":not mismatches,"mismatches":mismatches,"expected_count":len(expected),"actual_count":len(actual)}

REQUIRED_GATES=("AIRLOCK","BUBBLES","LEAK_GUARD","PROOFOS")

@dataclass(frozen=True)
class GateResult:
    gate:str
    status:str
    evidence_ref:str

class GateCourt:
    def __init__(self,results:Iterable[GateResult]):
        self.results={r.gate:r for r in results}
    def verdict(self):
        missing=[g for g in REQUIRED_GATES if g not in self.results]
        failed=[g for g,r in self.results.items() if g in REQUIRED_GATES and r.status!="PASS"]
        no_evidence=[g for g in REQUIRED_GATES if g in self.results and not self.results[g].evidence_ref]
        return {"pass":not missing and not failed and not no_evidence,
                "missing":missing,"failed":failed,"no_evidence":no_evidence}

@dataclass(frozen=True)
class ForgeBootstrapPlan:
    expected_main:str
    expected_tree:str
    expected_entries:int
    object_bytes_available:bool
    fdof_source_write_authorized:bool
    private_primary_cutover_authorized:bool

    def stage(self):
        if not self.object_bytes_available:
            return "MANIFEST_PARITY_READY_OBJECT_BYTES_OPEN"
        if not self.fdof_source_write_authorized:
            return "PRIVATE_MIRROR_CAN_BUILD_SOURCE_MUTATION_HELD"
        if not self.private_primary_cutover_authorized:
            return "PRIVATE_MIRROR_SOURCE_GATES_READY_CUTOVER_HELD"
        return "CUTOVER_ELIGIBLE_PENDING_JUDGE"

def source_parity_receipt(repo,commit,expected_main,expected_tree):
    actual_commit=run(["git","rev-parse",commit],cwd=repo)
    actual_tree=git_commit_tree(repo,commit)
    return {
        "expected_main":expected_main,
        "actual_main":actual_commit,
        "expected_tree":expected_tree,
        "actual_tree":actual_tree,
        "commit_match":actual_commit==expected_main,
        "tree_match":actual_tree==expected_tree,
        "refs":git_show_refs(repo),
    }

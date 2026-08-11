#!/usr/bin/env python3
"""Finalize an EvidenceOps PST v2 corpus with direct shard retrieval mappings."""
from __future__ import annotations
import argparse, csv, json, sqlite3, zipfile
from collections import Counter
from pathlib import Path

def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))

def finalize(corpus: Path) -> dict:
    index_dir, shards_dir, control_dir = corpus / "04_INDEX", corpus / "06_RETRIEVAL_SHARDS", corpus / "00_CONTROL"
    map_rows=[]
    for shard in sorted(shards_dir.glob("*.zip")):
        with zipfile.ZipFile(shard) as archive:
            bad=archive.testzip()
            if bad: raise RuntimeError(f"zip_crc_failure:{shard.name}:{bad}")
            for info in archive.infolist():
                if not info.is_dir():
                    map_rows.append({"member_relpath":info.filename,"shard_name":shard.name,"member_size_bytes":info.file_size,"compressed_size_bytes":info.compress_size,"crc32":f"{info.CRC:08x}"})
    if not map_rows: raise RuntimeError("zero_shard_members")
    counts=Counter(r["member_relpath"] for r in map_rows); duplicates=sorted(n for n,c in counts.items() if c != 1)
    fields=["member_relpath","shard_name","member_size_bytes","compressed_size_bytes","crc32"]
    with (index_dir/"retrieval_map.csv").open("w",encoding="utf-8-sig",newline="") as h:
        w=csv.DictWriter(h,fieldnames=fields); w.writeheader(); w.writerows(map_rows)
    with (index_dir/"retrieval_map.jsonl").open("w",encoding="utf-8") as h:
        for row in map_rows: h.write(json.dumps(row,sort_keys=True)+"\n")
    messages=read_csv(index_dir/"messages.csv"); attachments=read_csv(index_dir/"attachments.csv")
    required=[]
    for r in messages: required.extend([r["stored_relpath"],r["body_text_relpath"]])
    for r in attachments:
        required.append(r["stored_relpath"])
        if r.get("text_relpath"): required.append(r["text_relpath"])
    missing=sorted(set(required)-set(counts)); by_member={r["member_relpath"]:r for r in map_rows}
    db=sqlite3.connect(index_dir/"corpus_search.db")
    try:
        db.executescript("""
        DROP TABLE IF EXISTS retrieval_map;
        CREATE TABLE retrieval_map(member_relpath TEXT PRIMARY KEY,shard_name TEXT NOT NULL,member_size_bytes INTEGER NOT NULL,compressed_size_bytes INTEGER NOT NULL,crc32 TEXT NOT NULL);
        DROP TABLE IF EXISTS occurrence_retrieval;
        CREATE TABLE occurrence_retrieval(occurrence_id TEXT NOT NULL,evidence_role TEXT NOT NULL,member_relpath TEXT NOT NULL,shard_name TEXT NOT NULL,member_size_bytes INTEGER NOT NULL,crc32 TEXT NOT NULL,PRIMARY KEY(occurrence_id,evidence_role));
        """)
        db.executemany("INSERT INTO retrieval_map VALUES(?,?,?,?,?)",[(r["member_relpath"],r["shard_name"],r["member_size_bytes"],r["compressed_size_bytes"],r["crc32"]) for r in map_rows])
        occurrence_rows=[]
        for r in messages:
            for role,member in (("message",r["stored_relpath"]),("message_body",r["body_text_relpath"])):
                if member in by_member:
                    x=by_member[member]; occurrence_rows.append((r["occurrence_id"],role,member,x["shard_name"],x["member_size_bytes"],x["crc32"]))
        for r in attachments:
            for role,member in (("attachment",r["stored_relpath"]),("attachment_text",r.get("text_relpath") or "")):
                if member and member in by_member:
                    x=by_member[member]; occurrence_rows.append((r["occurrence_id"],role,member,x["shard_name"],x["member_size_bytes"],x["crc32"]))
        db.executemany("INSERT INTO occurrence_retrieval VALUES(?,?,?,?,?,?)",occurrence_rows)
        db.executescript("""
        DROP VIEW IF EXISTS message_retrieval;
        CREATE VIEW message_retrieval AS SELECT m.occurrence_id,m.folder_path,m.date_utc,m.sender,m.recipients,m.subject,r.member_relpath,r.shard_name,r.crc32,r.member_size_bytes FROM messages_meta m LEFT JOIN occurrence_retrieval r ON r.occurrence_id=m.occurrence_id AND r.evidence_role='message';
        DROP VIEW IF EXISTS attachment_retrieval;
        CREATE VIEW attachment_retrieval AS SELECT a.occurrence_id,a.message_occurrence_id,a.filename,a.mime_type,r.member_relpath,r.shard_name,r.crc32,r.member_size_bytes FROM attachments_meta a LEFT JOIN occurrence_retrieval r ON r.occurrence_id=a.occurrence_id AND r.evidence_role='attachment';
        """); db.commit()
        integrity=db.execute("PRAGMA integrity_check").fetchone()[0]
        unresolved_messages=db.execute("SELECT count(*) FROM message_retrieval WHERE shard_name IS NULL").fetchone()[0]
        unresolved_attachments=db.execute("SELECT count(*) FROM attachment_retrieval WHERE shard_name IS NULL").fetchone()[0]
    finally: db.close()
    problems=[]
    if duplicates: problems.append({"duplicate_members":duplicates[:100],"count":len(duplicates)})
    if missing: problems.append({"missing_required_members":missing[:100],"count":len(missing)})
    if integrity != "ok": problems.append({"sqlite_integrity":integrity})
    if unresolved_messages: problems.append({"unresolved_messages":unresolved_messages})
    if unresolved_attachments: problems.append({"unresolved_attachments":unresolved_attachments})
    report={"schema":"EVIDENCEOPS-PST-CORPUS-V2-FINALIZATION-1","status":"FINALIZATION_COMPLETE_VERIFIED" if not problems else "INCOMPLETE","shard_count":len(list(shards_dir.glob('*.zip'))),"shard_member_count":len(map_rows),"message_occurrences":len(messages),"attachment_occurrences":len(attachments),"required_member_references":len(required),"problems":problems}
    write_json(control_dir/"FINALIZATION_VERIFICATION.json",report)
    if problems: raise RuntimeError(json.dumps(report,sort_keys=True))
    return report

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--corpus",required=True); a=p.parse_args(); print(json.dumps(finalize(Path(a.corpus)),indent=2,sort_keys=True)); return 0
if __name__ == "__main__": raise SystemExit(main())

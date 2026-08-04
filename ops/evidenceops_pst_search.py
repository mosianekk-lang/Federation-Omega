#!/usr/bin/env python3
"""Search an EvidenceOps PST Corpus v2 SQLite FTS index."""
from __future__ import annotations
import argparse, json, sqlite3
from pathlib import Path

def search(db_path: Path, query: str, limit: int, kind: str) -> list[dict]:
    db=sqlite3.connect(db_path); db.row_factory=sqlite3.Row
    try:
        rows=[]
        if kind in ('messages','all'):
            sql="""SELECT m.occurrence_id,m.date_utc,m.sender,m.recipients,m.subject,m.folder_path,m.message_id_header,r.shard_name,r.crc32,snippet(messages_fts,6,'[',']',' … ',24) AS snippet,bm25(messages_fts) AS rank FROM messages_fts JOIN messages_meta m USING(occurrence_id) LEFT JOIN occurrence_retrieval r ON r.occurrence_id=m.occurrence_id AND r.evidence_role='message' WHERE messages_fts MATCH ? ORDER BY rank LIMIT ?"""
            for row in db.execute(sql,(query,limit)):
                item=dict(row); item['kind']='message'; rows.append(item)
        if kind in ('attachments','all'):
            sql="""SELECT a.occurrence_id,a.message_occurrence_id,a.filename,a.mime_type,r.shard_name,r.crc32,snippet(attachments_fts,4,'[',']',' … ',24) AS snippet,bm25(attachments_fts) AS rank FROM attachments_fts JOIN attachments_meta a USING(occurrence_id) LEFT JOIN occurrence_retrieval r ON r.occurrence_id=a.occurrence_id AND r.evidence_role='attachment' WHERE attachments_fts MATCH ? ORDER BY rank LIMIT ?"""
            for row in db.execute(sql,(query,limit)):
                item=dict(row); item['kind']='attachment'; rows.append(item)
        return sorted(rows,key=lambda x:x.get('rank',0))[:limit]
    finally: db.close()

def main() -> None:
    p=argparse.ArgumentParser(); p.add_argument('--db',required=True); p.add_argument('--query',required=True); p.add_argument('--limit',type=int,default=25); p.add_argument('--kind',choices=['messages','attachments','all'],default='all')
    a=p.parse_args(); print(json.dumps({'query':a.query,'results':search(Path(a.db),a.query,a.limit,a.kind)},indent=2,ensure_ascii=False))
if __name__=='__main__': main()

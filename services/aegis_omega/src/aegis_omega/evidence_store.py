from __future__ import annotations
import json
from .schemas import SealedEvent


class NullEvidenceStore:
    def persist(self, sealed: SealedEvent) -> str:
        return sealed.digest_sha256


class GcsEvidenceStore:
    def __init__(self, bucket_name: str):
        from google.cloud import storage
        self.bucket = storage.Client().bucket(bucket_name)

    def persist(self, sealed: SealedEvent) -> str:
        # Normalized/minimized event only. Raw forensic objects belong in separately authorized acquisition workflows.
        key = f"events/{sealed.event.timestamp:%Y/%m/%d}/{sealed.digest_sha256}.json"
        blob = self.bucket.blob(key)
        payload = json.dumps(sealed.model_dump(mode="json"), sort_keys=True)
        try:
            # Immutable/content-addressed write. The same digest may be retried,
            # but an existing object is never overwritten.
            blob.upload_from_string(payload, content_type="application/json", if_generation_match=0)
        except Exception as exc:
            if type(exc).__name__ != "PreconditionFailed":
                raise
        return key


def build_evidence_store(bucket_name: str):
    return GcsEvidenceStore(bucket_name) if bucket_name else NullEvidenceStore()

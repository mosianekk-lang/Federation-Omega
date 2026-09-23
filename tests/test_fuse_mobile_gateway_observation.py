from __future__ import annotations
import hashlib
import struct
import zlib
from pathlib import Path
from services.fuse_mobile_gateway.observation import ObservationCache, classify_ui_signal


def _png() -> bytes:
    sig=b'\x89PNG\r\n\x1a\n'
    def chunk(kind,data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    raw=b'\x00'+b'\x01\x02\x03'
    return sig+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')


def test_context_limit_classification():
    x=classify_ui_signal("You've hit max weighted tokens for this chat")
    assert x.category=='CONTEXT_LIMIT'
    assert x.recommended_action=='CHECKPOINT_DETACH_REJOIN'


def test_frame_cache_is_ephemeral_and_hash_bound(tmp_path: Path):
    c=ObservationCache(tmp_path/'obs',ttl_seconds=60)
    data=_png(); s=c.ingest_frame(data,content_type='image/png',source='court')
    assert s['available'] and s['fresh']
    assert s['sha256']==hashlib.sha256(data).hexdigest()
    assert 'NO_MISSION_STATE' in s['truth_boundary']
    assert c.image_path().read_bytes()==data
    assert c.clear()['mission_state_changed'] is False


def test_rejects_bad_media(tmp_path: Path):
    c=ObservationCache(tmp_path/'obs')
    try:
        c.ingest_frame(b'nope',content_type='image/png',source='court')
        assert False
    except ValueError as exc:
        assert str(exc)=='VISION_IMAGE_SIGNATURE_INVALID'

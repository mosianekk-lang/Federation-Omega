#pragma once
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <bcrypt.h>
#include "status.h"
namespace fuse {
struct Sha256Stream{BCRYPT_ALG_HANDLE alg{};BCRYPT_HASH_HANDLE hash{};PUCHAR object{};DWORD object_size{};bool active{};};
Status sha256(ByteSpan,Digest256*);Status sha256_stream_begin(Sha256Stream*);Status sha256_stream_update(Sha256Stream*,ByteSpan);Status sha256_stream_finish(Sha256Stream*,Digest256*);void sha256_stream_abort(Sha256Stream*);Status random_bytes(MutableByteSpan);
}
